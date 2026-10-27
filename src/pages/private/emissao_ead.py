import io
import re
import zipfile
from collections import defaultdict
from datetime import datetime

import pandas as pd
import streamlit as st

from src.utils.emissao_ead import (
    buscar_curso_por_sigla,
    buscar_ct_conecta,
    buscar_empresa_por_cnpj,
    ler_planilha_ead,
    listar_assinantes,
    nome_arquivo_certificado,
)
from src.utils.certificado_ead import gerar_certificado_ead_pdf
from src.utils.certificado_empresa import gerar_certificado_empresa_pdf
from src.auth.permissions import exigir_permissao

exigir_permissao("emissao_ead")

st.title("🎓 Emissão EAD")
st.markdown(
    "Envie a planilha de conclusões, confira o vínculo **CNPJ → empresa** e "
    "**sigla → curso**, escolha o assinante e baixe o ZIP com os "
    "**certificados dos alunos** e os **certificados da empresa**."
)

with st.expander("Formato da planilha", expanded=False):
    st.markdown(
        """
Colunas esperadas:

| CNPJ | Nome | E-mail | CPF | SIGLA CURSO | CARGA | Progresso | Data de Inicio | Data de Finalização |

- Empresa buscada pelo **CNPJ** (tabela `clients`)
- Curso buscado pela **SIGLA CURSO** (tabela `cursos`)
- Só emite linhas com **Progresso ≥ 0,96**
- Certificados de aluno: `NOME DO ALUNO - SIGLA.pdf`
- Certificados de empresa: **1 por combinação CNPJ + SIGLA** (somente assinatura do RT)
        """
    )

    modelo = pd.DataFrame(
        [
            {
                "CNPJ": "42365296001085",
                "Nome": "NOME COMPLETO",
                "E-mail": "email@empresa.com",
                "CPF": "00000000000",
                "SIGLA CURSO": "NR34",
                "CARGA": "08 Horas",
                "Progresso": 1,
                "Data de Inicio": "2026-09-30",
                "Data de Finalização": "2026-09-30",
            }
        ]
    )
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        modelo.to_excel(writer, index=False, sheet_name="EAD")
    st.download_button(
        "📥 Baixar modelo de planilha",
        data=buf.getvalue(),
        file_name="modelo_emissao_ead.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

uploaded = st.file_uploader("Planilha (.xlsx)", type=["xlsx", "xls"])

if not uploaded:
    st.info("Faça o upload da planilha para continuar.")
    st.stop()

linhas, erros_leitura = ler_planilha_ead(uploaded.getvalue())

if erros_leitura:
    with st.expander(f"Avisos da leitura ({len(erros_leitura)})", expanded=False):
        for e in erros_leitura:
            st.write(f"- {e}")

if not linhas:
    st.error("Nenhuma linha válida para emissão.")
    st.stop()

# Resolve empresa e curso
empresas_cache: dict[str, dict | None] = {}
cursos_cache: dict[str, dict | None] = {}
problemas: list[str] = []

for L in linhas:
    if L["cnpj"] not in empresas_cache:
        empresas_cache[L["cnpj"]] = buscar_empresa_por_cnpj(L["cnpj"])
    if L["sigla"] not in cursos_cache:
        cursos_cache[L["sigla"]] = buscar_curso_por_sigla(L["sigla"])

    if not empresas_cache[L["cnpj"]]:
        problemas.append(f"CNPJ {L['cnpj']} não encontrado em clientes.")
    if not cursos_cache[L["sigla"]]:
        problemas.append(f"Sigla **{L['sigla']}** não encontrada em cursos.")

problemas = sorted(set(problemas))

st.subheader(f"Pré-visualização — {len(linhas)} certificado(s) de aluno")

preview = []
for L in linhas:
    emp = empresas_cache.get(L["cnpj"])
    cur = cursos_cache.get(L["sigla"])
    preview.append(
        {
            "Aluno": L["nome"],
            "CPF": L["cpf"],
            "Empresa": (emp or {}).get("name") or f"⚠️ CNPJ {L['cnpj']}",
            "Curso": (cur or {}).get("name") or f"⚠️ {L['sigla']}",
            "Sigla": L["sigla"],
            "Carga": L["carga"] or "—",
            "Início": str(L["data_inicio"])[:10],
            "Fim": str(L["data_fim"])[:10],
        }
    )

st.dataframe(preview, use_container_width=True, hide_index=True)

# Agrupa por empresa + curso para certificado corporativo
grupos: dict[tuple[str, str], list] = defaultdict(list)
for L in linhas:
    grupos[(L["cnpj"], L["sigla"])].append(L)

st.caption(
    f"Também serão gerados **{len(grupos)}** certificado(s) da **empresa** "
    f"(1 por CNPJ + sigla do curso, somente assinatura do RT)."
)

if problemas:
    st.error("Corrija os cadastros antes de emitir:\n\n- " + "\n- ".join(problemas))
    st.stop()

# Assinante + CT
ct = buscar_ct_conecta()
if ct:
    st.caption(f"CT / fundo: **{ct.get('name') or ct.get('full_name')}**")")
else:
    st.warning("CT Conecta não encontrado — será usado o fundo padrão Conecta.")

assinantes = listar_assinantes()
if not assinantes:
    st.error("Nenhum instrutor ou responsável técnico ativo para assinar.")
    st.stop()

labels = []
for a in assinantes:
    re_v = (a.get("re") or "").strip()
    lab = f"{a.get('nome')} ({a.get('tipo')}"
    if re_v:
        lab += f" · RE {re_v}"
    lab += ")"
    labels.append(lab)

idx_default = next(
    (i for i, a in enumerate(assinantes) if a.get("tipo") == "responsavel"), 0
)
escolha = st.selectbox("Assinante (Instrutor/Resp. Técnico)", labels, index=idx_default)
assinante = assinantes[labels.index(escolha)]


def _fmt_data_br(val) -> str:
    if val is None:
        return ""
    if hasattr(val, "strftime"):
        try:
            return val.strftime("%d/%m/%Y")
        except Exception:
            pass
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "nat"):
        return ""
    s10 = s.split("T")[0][:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s10 if fmt.startswith("%Y") else s[:10], fmt).strftime(
                "%d/%m/%Y"
            )
        except Exception:
            continue
    return s


def _slug_arquivo(texto: str) -> str:
    s = re.sub(r"[^A-Za-z0-9 _-]", "", (texto or "").strip())
    s = re.sub(r"\s+", "_", s)
    return s[:80] or "arquivo"


def _assinante_como_resp(a: dict) -> dict:
    return {
        "nome": a.get("nome") or a.get("name") or "",
        "cpf": re.sub(r"\D", "", str(a.get("cpf") or "")),
        "re": (a.get("re") or "").strip(),
        "formacao": (a.get("formacao") or a.get("cargo") or "").strip(),
        "assinatura_url": a.get("assinatura_url") or a.get("assinatura") or "",
    }


ss_key = "ead_zip_bytes"
ss_meta = "ead_zip_meta"

if st.session_state.get(ss_key):
    meta = st.session_state.get(ss_meta) or {}
    st.success(
        f"✅ {meta.get('ok_alunos', 0)} certificado(s) de aluno e "
        f"{meta.get('ok_empresas', 0)} da empresa gerado(s)."
    )
    if meta.get("falhas"):
        with st.expander("Falhas", expanded=False):
            for f in meta["falhas"]:
                st.write(f"- {f}")
    st.download_button(
        "📥 Baixar ZIP (alunos + empresas)",
        data=st.session_state[ss_key],
        file_name=meta.get("nome_zip") or "certificados_ead.zip",
        mime="application/zip",
        use_container_width=True,
        key="dl_ead_zip_persist",
    )

if st.button(
    "🚀 Gerar certificados EAD (ZIP)",
    type="primary",
    use_container_width=True,
):
    falhas: list[str] = []
    ok_alunos = 0
    ok_empresas = 0
    zip_buf = io.BytesIO()
    resp_payload = _assinante_como_resp(assinante)

    with st.spinner("Gerando certificados de alunos e de empresas..."):
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            usados: dict[str, int] = {}

            # --- Certificados individuais ---
            for L in linhas:
                emp = empresas_cache[L["cnpj"]]
                cur = cursos_cache[L["sigla"]]
                try:
                    pdf = gerar_certificado_ead_pdf(
                        aluno={
                            "name": L["nome"],
                            "cpf": L["cpf"],
                            "email": L.get("email"),
                        },
                        empresa=emp,
                        curso=cur,
                        assinante=assinante,
                        data_inicio=L["data_inicio"],
                        data_termino=L["data_fim"],
                        carga_horaria=L.get("carga") or "",
                        modalidade="EAD",
                        ct=ct,
                    )
                    fname = nome_arquivo_certificado(L["nome"], L["sigla"])
                    path = f"certificados_alunos/{fname}"
                    if path in usados:
                        usados[path] += 1
                        base, ext = fname.rsplit(".", 1)
                        path = f"certificados_alunos/{base}_{usados[path]}.{ext}"
                    else:
                        usados[path] = 1
                    zf.writestr(path, pdf)
                    ok_alunos += 1
                except Exception as e:
                    falhas.append(f"Aluno {L['nome']} / {L['sigla']}: {e}")

            # --- Certificados da empresa (1 por CNPJ + SIGLA) — só RT ---
            for (cnpj, sigla), grupo in grupos.items():
                emp = empresas_cache.get(cnpj)
                cur = cursos_cache.get(sigla)
                if not emp or not cur:
                    falhas.append(
                        f"Empresa {cnpj} / {sigla}: cadastro incompleto — ignorado."
                    )
                    continue

                try:
                    cargas = [g.get("carga") for g in grupo if g.get("carga")]
                    carga = cargas[0] if cargas else (cur.get("carga_horaria") or "08 Horas")

                    datas_fim = [g.get("data_fim") for g in grupo if g.get("data_fim") is not None]
                    data_ref = datas_fim[-1] if datas_fim else None
                    cidade_data = _fmt_data_br(data_ref)

                    alunos_grupo = [
                        {"name": g["nome"], "cpf": g["cpf"]} for g in grupo
                    ]

                    turma_cert = {
                        "modalidade": "EAD",
                        "nivel": "Formação",
                        "carga_horaria": str(carga).strip() or "08 Horas",
                        "resp_tecnico": resp_payload.get("nome", ""),
                        "cpf_resp_tecnico": resp_payload.get("cpf", ""),
                        "re_resp_tecnico": resp_payload.get("re", ""),
                        "formacao_resp_tecnico": resp_payload.get("formacao", ""),
                        "assinatura_resp_url": resp_payload.get("assinatura_url"),
                        "curso_nome": cur.get("name") or sigla,
                        "curso_sigla": sigla,
                        "dizeres_certificado_empresa": cur.get(
                            "dizeres_certificado_empresa", ""
                        ),
                    }

                    # EAD empresa: somente assinatura do Responsável Técnico
                    pdf_emp = gerar_certificado_empresa_pdf(
                        turma=turma_cert,
                        instrutor={},  # sem bloco de instrutor no template
                        empresa=emp,
                        ct=ct or None,
                        alunos=alunos_grupo,
                        normativa=cur.get("normativa") or "",
                        cidade_data=cidade_data,
                    )

                    emp_nome = _slug_arquivo(emp.get("name") or cnpj)
                    fname_emp = f"certificado_empresa_{emp_nome}_{sigla}.pdf"
                    path_emp = f"certificados_empresa/{fname_emp}"
                    if path_emp in usados:
                        usados[path_emp] += 1
                        path_emp = (
                            f"certificados_empresa/"
                            f"certificado_empresa_{emp_nome}_{sigla}_{usados[path_emp]}.pdf"
                        )
                    else:
                        usados[path_emp] = 1

                    zf.writestr(path_emp, pdf_emp)
                    ok_empresas += 1
                except Exception as e:
                    falhas.append(f"Empresa {cnpj} / {sigla}: {e}")

    if ok_alunos == 0 and ok_empresas == 0:
        st.error("Nenhum certificado gerado.\n" + "\n".join(falhas))
    else:
        zip_buf.seek(0)
        st.session_state[ss_key] = zip_buf.getvalue()
        st.session_state[ss_meta] = {
            "ok_alunos": ok_alunos,
            "ok_empresas": ok_empresas,
            "falhas": falhas,
            "nome_zip": "certificados_ead.zip",
        }
        st.success(
            f"✅ {ok_alunos} certificado(s) de aluno e "
            f"{ok_empresas} da empresa gerado(s)."
        )
        if falhas:
            with st.expander("Falhas", expanded=True):
                for f in falhas:
                    st.write(f"- {f}")
        st.download_button(
            "📥 Baixar ZIP (alunos + empresas)",
            data=st.session_state[ss_key],
            file_name="certificados_ead.zip",
            mime="application/zip",
            use_container_width=True,
            key="dl_ead_zip_new",
        )
