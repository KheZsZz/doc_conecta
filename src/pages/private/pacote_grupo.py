from datetime import date, timedelta
from datetime import datetime as _dt

import streamlit as st

from src.auth.permissions import exigir_permissao
from src.utils.pacote_grupo import (
    empresas_do_grupo,
    empresas_por_ids,
    gerar_pacote_grupo,
    listar_grupos,
    listar_todas_empresas,
    responsavel_padrao,
    turmas_do_periodo,
)

exigir_permissao("pacote_grupo")

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
        st.warning(
            f"O grupo **{grupo_nome}** não tem empresas vinculadas."
        )
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

# segunda-feira da semana atual
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
        "Data início*",
        value=def_di,
        format="DD/MM/YYYY",
        key="pkg_di_input",
    )
with col_b:
    data_fim = st.date_input(
        "Data fim*",
        value=def_df,
        format="DD/MM/YYYY",
        key="pkg_df_input",
    )

# sincroniza session com os inputs
st.session_state["pkg_di"] = data_inicio
st.session_state["pkg_df"] = data_fim

if data_inicio > data_fim:
    st.error("A data início não pode ser maior que a data fim.")
    st.stop()

# ---------- Filtro de status ----------
filtro_status = st.selectbox(
    "Status das turmas",
    options=[
        "Todas",
        "Somente pendentes (não emitidas)",
        "Somente já emitidas",
    ],
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

# ---------- Busca turmas ----------
turmas = turmas_do_periodo(client_ids, data_inicio, data_fim)

if filtro_status == "Somente pendentes (não emitidas)":
    turmas = [t for t in turmas if not t.get("documento_emitido")]
elif filtro_status == "Somente já emitidas":
    turmas = [t for t in turmas if t.get("documento_emitido")]

# Resolve empresas para preview / geração
ids_clientes = list({t.get("client_id") for t in turmas if t.get("client_id")})
if escopo == "Todas as empresas":
    empresas_por_id = empresas_por_ids(ids_clientes)
else:
    empresas_por_id = {e["id"]: e for e in empresas if e.get("id")}
    # completa faltantes
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

ss_zip = "pacote_grupo_zip"
ss_meta = "pacote_grupo_meta"
ss_nome = "pacote_grupo_nome"

if st.session_state.get(ss_zip):
    meta = st.session_state.get(ss_meta) or {}
    st.success(
        f"✅ Pacote pronto: **{meta.get('total_docs', 0)}** documento(s) "
        f"em **{meta.get('total_turmas', 0)}** turma(s)."
    )
    marcadas = meta.get("turmas_marcadas") or []
    if marcadas:
        st.success(
            f"✅ **{len(marcadas)}** turma(s) marcada(s) como documentação emitida."
        )
    if meta.get("erros"):
        with st.expander("Avisos / falhas", expanded=False):
            for e in meta["erros"]:
                st.write(f"- {e}")
    st.download_button(
        "📥 Baixar pacote (ZIP)",
        data=st.session_state[ss_zip],
        file_name=st.session_state.get(ss_nome) or "pacote_periodo.zip",
        mime="application/zip",
        use_container_width=True,
        key="dl_pacote_persist",
    )

if st.button(
    "🚀 Gerar pacote de documentação",
    type="primary",
    use_container_width=True,
):
    with st.spinner(
        f"Gerando documentação de {len(turmas)} turma(s)... pode levar alguns minutos."
    ):
        try:
            zip_bytes, meta = gerar_pacote_grupo(
                grupo_nome=grupo_nome if escopo == "Grupo empresarial" else "Todas_Empresas",
                turmas=turmas,
                empresas_por_id=empresas_por_id,
                dados_resp=responsavel_padrao(),
                incluir_atestado=opt_atestado,
                incluir_cert_empresa=opt_cert_emp,
                incluir_cert_alunos=opt_cert_alunos,
                incluir_carteirinhas=opt_carteirinhas,
                incluir_lista=opt_lista,
            )
        except Exception as e:
            st.error(f"Erro ao gerar pacote: {e}")
            st.stop()

    if meta.get("total_docs", 0) == 0:
        st.error("Nenhum documento foi gerado.")
        if meta.get("erros"):
            for e in meta["erros"]:
                st.write(f"- {e}")
        st.stop()

    rotulo = grupo_nome.replace(" ", "_") if escopo == "Grupo empresarial" else "todas_empresas"
    nome_zip = (
        f"pacote_{rotulo}_"
        f"{data_inicio.strftime('%Y%m%d')}_{data_fim.strftime('%Y%m%d')}.zip"
    )
    st.session_state[ss_zip] = zip_bytes
    st.session_state[ss_meta] = meta
    st.session_state[ss_nome] = nome_zip

    st.success(
        f"✅ **{meta['total_docs']}** documento(s) gerados "
        f"para **{meta['total_turmas']}** turma(s)."
    )

    marcadas = meta.get("turmas_marcadas") or []
    if marcadas:
        st.success(
            f"✅ **{len(marcadas)}** turma(s) marcada(s) como **documentação emitida**."
        )

    if meta.get("resumo"):
        st.dataframe(meta["resumo"], use_container_width=True, hide_index=True)
    if meta.get("erros"):
        with st.expander("Avisos / falhas", expanded=True):
            for e in meta["erros"]:
                st.write(f"- {e}")

    st.download_button(
        "📥 Baixar pacote (ZIP)",
        data=zip_bytes,
        file_name=nome_zip,
        mime="application/zip",
        use_container_width=True,
        key="dl_pacote_new",
    )
