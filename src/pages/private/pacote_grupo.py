"""Pacote por periodo.

Geracao em LOTES: cada execucao do Streamlit processa poucas turmas (em
paralelo), grava no ZIP em DISCO (arquivo temporario), atualiza a barra de
progresso e dispara st.rerun(). Nenhuma requisicao fica aberta por minutos.

As turmas so sao marcadas como "emitidas" quando o usuario clica em baixar
o ZIP — se a aba fechar no meio, nada fica marcado sem ter sido entregue.
"""
import os
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from datetime import datetime as _dt

import streamlit as st

from src.auth.permissions import exigir_permissao
from src.utils.pacote_grupo import (
    empresas_do_grupo,
    empresas_por_ids,
    gerar_docs_turma,
    listar_cts_completo,
    listar_grupos,
    marcar_turmas_emitidas,
    responsavel_padrao,
    turmas_do_periodo,
)
from src.utils.imprimir_documentacao import _prefetch_maps

exigir_permissao("pacote_grupo")

TURMAS_POR_LOTE = 3  # turmas processadas por execucao (em paralelo)
MAX_WORKERS = 3
JOB = "pkg_job"

st.title("📦 Pacote por Período")
st.markdown(
    "Gera um **ZIP** com a documentação de turmas em um intervalo de datas.\n\n"
    "Pode filtrar por **todas as empresas** ou por um **grupo empresarial**.\n\n"
    "As turmas com pelo menos um documento gerado são marcadas como "
    "**documentação emitida** automaticamente."
)

# ---------- Escopo ----------
escopo = st.radio(
    "Escopo*",
    options=["Todas as empresas", "Grupo empresarial"],
    horizontal=True,
    help="Todas as empresas = qualquer turma no período, independente de grupo.",
)

empresas: list[dict] = []
grupo_nome = "Todas_Empresas"
client_ids: list[str] | None = None

if escopo == "Grupo empresarial":
    grupos = listar_grupos()
    if not grupos:
        st.warning(
            "Nenhum grupo empresarial cadastrado. "
            "Crie um em **Empresas → Grupos Empresariais** ou use **Todas as empresas**."
        )
        st.stop()

    nome_para_id = {g.get("nome") or str(g.get("id")): g["id"] for g in grupos}
    grupo_nome = st.selectbox("Grupo empresarial*", options=list(nome_para_id.keys()))
    grupo_id = nome_para_id[grupo_nome]
    empresas = empresas_do_grupo(grupo_id)
    if not empresas:
        st.warning(f"O grupo **{grupo_nome}** não tem empresas vinculadas.")
        st.stop()
    client_ids = [e["id"] for e in empresas if e.get("id")]
    with st.expander(f"Empresas do grupo ({len(empresas)})", expanded=False):
        for e in empresas:
            unidade = e.get("sigla") or ""
            extra = f" · {unidade}" if unidade else ""
            st.caption(f"- {e.get('name')}{extra} — CNPJ {e.get('cnpj') or '—'}")
else:
    st.caption("Serão consideradas turmas de **todas as empresas** no período.")

# ---------- Período (atalhos + datas) ----------
st.markdown("**Período**")
hoje = date.today()

inicio_semana = hoje - timedelta(days=hoje.weekday())
fim_semana = inicio_semana + timedelta(days=6)
inicio_mes = date(hoje.year, hoje.month, 1)
if hoje.month == 12:
    fim_mes = date(hoje.year, 12, 31)
else:
    fim_mes = date(hoje.year, hoje.month + 1, 1) - timedelta(days=1)

c1, c2, c3, c4 = st.columns(4)
with c1:
    if st.button("Hoje", use_container_width=True):
        st.session_state["pkg_di"] = hoje
        st.session_state["pkg_df"] = hoje
        st.rerun()
with c2:
    if st.button("Esta semana", use_container_width=True):
        st.session_state["pkg_di"] = inicio_semana
        st.session_state["pkg_df"] = fim_semana
        st.rerun()
with c3:
    if st.button("Este mês", use_container_width=True):
        st.session_state["pkg_di"] = inicio_mes
        st.session_state["pkg_df"] = fim_mes
        st.rerun()
with c4:
    if st.button("Este ano", use_container_width=True):
        st.session_state["pkg_di"] = date(hoje.year, 1, 1)
        st.session_state["pkg_df"] = hoje
        st.rerun()

def_di = st.session_state.get("pkg_di", hoje)
def_df = st.session_state.get("pkg_df", hoje)

col_a, col_b = st.columns(2)
with col_a:
    data_inicio = st.date_input(
        "Data início*", value=def_di, format="DD/MM/YYYY", key="pkg_di_input"
    )
with col_b:
    data_fim = st.date_input(
        "Data fim*", value=def_df, format="DD/MM/YYYY", key="pkg_df_input"
    )

st.session_state["pkg_di"] = data_inicio
st.session_state["pkg_df"] = data_fim

if data_inicio > data_fim:
    st.error("A data início não pode ser maior que a data fim.")
    st.stop()

# ---------- Filtro de status ----------
filtro_status = st.selectbox(
    "Status das turmas",
    options=["Todas", "Somente pendentes (não emitidas)", "Somente já emitidas"],
    index=1,
    help="Ao gerar o pacote, as turmas com documento gerado passam a **emitidas**.",
)

# ---------- Documentos ----------
st.markdown("**Documentos a incluir**")
ocol1, ocol2, ocol3 = st.columns(3)
with ocol1:
    opt_atestado = st.checkbox("Atestado (se o curso exigir)", value=True)
    opt_cert_emp = st.checkbox("Certificado da empresa", value=True)
with ocol2:
    opt_cert_alunos = st.checkbox("Certificados individuais", value=True)
    opt_carteirinhas = st.checkbox("Carteirinhas", value=True)
with ocol3:
    opt_lista = st.checkbox("Lista de presença", value=True)

# =====================================================================
# JOB EM LOTES (processamento / resultado) — fica ANTES do st.stop()
# para continuar visível mesmo quando as turmas passam a "emitidas".
# =====================================================================
job = st.session_state.get(JOB)


def _processar_lote(job: dict) -> None:
    ini = job["idx"]
    lote = job["turmas"][ini : ini + TURMAS_POR_LOTE]
    opts = job["opts"]

    # dados do lote inteiro em poucas consultas (em vez de 5+ por turma)
    try:
        cursos, instrutores, empresas_lote, mats = _prefetch_maps(lote)
    except Exception:
        cursos, instrutores, empresas_lote, mats = {}, {}, {}, {}

    def _um(turma):
        try:
            tid = str(turma.get("id") or "")
            pre = {
                "curso": cursos.get(str(turma.get("curso_id") or "")),
                "instrutor": instrutores.get(str(turma.get("instrutor_id") or "")),
                "empresa": empresas_lote.get(str(turma.get("client_id") or "")),
                "matriculas": mats.get(tid) or [],
            }
            if job["cts"]:
                pre["ct"] = job["cts"].get(str(turma.get("ct_id") or ""), {})
            return gerar_docs_turma(
                grupo_nome=job["grupo_nome"],
                turma=turma,
                empresas_por_id=job["empresas_por_id"],
                dados_resp=job["dados_resp"],
                pre=pre,
                marcar=False,  # marcacao so no download
                **opts,
            )
        except Exception as e:  # nunca derruba o lote inteiro
            titulo = turma.get("titulo") or "Turma"
            return [], {
                "titulo": titulo,
                "gerados": [],
                "erros": [f"{titulo}: {e}"],
                "marcado": False,
                "erro_marca": None,
                "resumo": {
                    "turma": titulo,
                    "data": str(turma.get("data_treinamento") or "")[:10],
                    "empresa": "",
                    "docs": 0,
                    "status": "falhou",
                    "marcado": False,
                },
            }

    workers = min(MAX_WORKERS, len(lote))
    if workers <= 1:
        resultados = [_um(t) for t in lote]
    else:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            resultados = list(ex.map(_um, lote))  # mantém a ordem

    with zipfile.ZipFile(job["zip_path"], "a", zipfile.ZIP_DEFLATED) as zf:
        for arquivos, info in resultados:
            for caminho, dados in arquivos:
                zf.writestr(caminho, dados)
            job["gerados"].extend(info["gerados"])
            job["erros"].extend(info["erros"])
            job["resumo"].append(info["resumo"])
            if info.get("docs_ok") and info.get("tid"):
                job["tids_ok"].append(str(info["tid"]))

    job["idx"] = ini + len(lote)
    if job["idx"] >= len(job["turmas"]):
        job["done"] = True


def _ao_baixar() -> None:
    """on_click do download: marca as turmas entregues como emitidas (1x)."""
    j = st.session_state.get(JOB)
    if not j or j.get("marcado_ok") is not None:
        return
    ok, falhas = marcar_turmas_emitidas(j["tids_ok"])
    j["marcado_ok"] = ok
    j["falha_marca"] = falhas


def _limpar_job() -> None:
    j = st.session_state.pop(JOB, None)
    if j:
        try:
            os.remove(j["zip_path"])
        except OSError:
            pass


if job and not job["done"]:
    total = len(job["turmas"])
    st.subheader("⏳ Gerando pacote…")
    st.progress(
        min(job["idx"] / total, 1.0),
        text=f"{job['idx']} de {total} turma(s) processada(s)",
    )
    st.caption(
        "Mantenha esta aba aberta. O processamento é feito em etapas curtas "
        "para não estourar o tempo limite."
    )
    if st.button("⛔ Cancelar e baixar o que já foi gerado", key="pkg_cancel"):
        job["done"] = True
        job["cancelado"] = True
        st.rerun()
    else:
        _processar_lote(job)
        st.rerun()

if job and job["done"]:
    st.subheader("✅ Pacote pronto" if not job.get("cancelado") else "⛔ Pacote parcial")
    st.success(
        f"**{len(job['gerados'])}** documento(s) em **{job['idx']}** de "
        f"**{len(job['turmas'])}** turma(s)."
    )
    if job.get("marcado_ok"):
        st.success(
            f"✅ **{len(job['marcado_ok'])}** turma(s) marcada(s) como **documentação emitida**."
        )
    elif job["tids_ok"]:
        st.info(
            f"As **{len(job['tids_ok'])}** turma(s) com documentos serão marcadas como "
            "emitidas **quando você clicar em baixar**."
        )
    for f in job.get("falha_marca") or []:
        st.warning(f"⚠️ Status não atualizado — {f}")
    if job["resumo"]:
        st.dataframe(job["resumo"], use_container_width=True, hide_index=True)
    if job["erros"]:
        with st.expander("Avisos / falhas", expanded=False):
            for e in job["erros"]:
                st.write(f"- {e}")
    if job["gerados"] and os.path.exists(job["zip_path"]):
        with open(job["zip_path"], "rb") as fh:
            zip_bytes = fh.read()
        st.download_button(
            "📥 Baixar pacote (ZIP)",
            data=zip_bytes,
            file_name=job["nome_zip"],
            mime="application/zip",
            use_container_width=True,
            key="dl_pacote_job",
            on_click=_ao_baixar,
        )
    else:
        st.error("Nenhum documento foi gerado.")
    if st.button("🗑️ Limpar resultado", key="pkg_clear"):
        _limpar_job()
        st.rerun()
    st.markdown("---")

# ---------- Busca turmas ----------
turmas = turmas_do_periodo(client_ids, data_inicio, data_fim)

if filtro_status == "Somente pendentes (não emitidas)":
    turmas = [t for t in turmas if not t.get("documento_emitido")]
elif filtro_status == "Somente já emitidas":
    turmas = [t for t in turmas if t.get("documento_emitido")]

ids_clientes = list({t.get("client_id") for t in turmas if t.get("client_id")})
if escopo == "Todas as empresas":
    empresas_por_id = empresas_por_ids(ids_clientes)
else:
    empresas_por_id = {e["id"]: e for e in empresas if e.get("id")}
    faltando = [i for i in ids_clientes if i not in empresas_por_id]
    if faltando:
        empresas_por_id.update(empresas_por_ids(faltando))

st.subheader(
    f"Turmas no período: **{len(turmas)}** "
    f"({data_inicio.strftime('%d/%m/%Y')} → {data_fim.strftime('%d/%m/%Y')})"
)

if not turmas:
    st.info("Nenhuma turma encontrada para o filtro selecionado.")
    st.stop()

preview = []
for t in turmas:
    emp = empresas_por_id.get(t.get("client_id")) or {}
    data_raw = str(t.get("data_treinamento") or "")[:10]
    try:
        data_fmt = _dt.strptime(data_raw, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        data_fmt = data_raw
    preview.append(
        {
            "Data": data_fmt,
            "Turma": t.get("titulo") or "",
            "Empresa": emp.get("name") or "",
            "Unidade": emp.get("sigla") or "",
            "Emitido": "Sim" if t.get("documento_emitido") else "Não",
        }
    )

st.dataframe(preview, use_container_width=True, hide_index=True)

def _novo_zip_path() -> str:
    fd, path = tempfile.mkstemp(suffix=".zip", prefix="pacote_")
    os.close(fd)
    os.remove(path)  # ZipFile(mode="a") cria o arquivo do zero
    return path


if st.button(
    "🚀 Gerar pacote de documentação",
    type="primary",
    use_container_width=True,
):
    rotulo = (
        grupo_nome.replace(" ", "_")
        if escopo == "Grupo empresarial"
        else "todas_empresas"
    )
    st.session_state[JOB] = {
        "turmas": list(turmas),
        "idx": 0,
        "done": False,
        "cancelado": False,
        "zip_path": _novo_zip_path(),
        "gerados": [],
        "erros": [],
        "resumo": [],
        "tids_ok": [],
        "marcado_ok": None,
        "falha_marca": [],
        "cts": listar_cts_completo(),
        "grupo_nome": grupo_nome if escopo == "Grupo empresarial" else "Todas_Empresas",
        "empresas_por_id": dict(empresas_por_id),
        "dados_resp": responsavel_padrao(),
        "opts": {
            "incluir_atestado": opt_atestado,
            "incluir_cert_empresa": opt_cert_emp,
            "incluir_cert_alunos": opt_cert_alunos,
            "incluir_carteirinhas": opt_carteirinhas,
            "incluir_lista": opt_lista,
        },
        "nome_zip": (
            f"pacote_{rotulo}_{data_inicio.strftime('%Y%m%d')}_"
            f"{data_fim.strftime('%Y%m%d')}.zip"
        ),
    }
    st.rerun()
