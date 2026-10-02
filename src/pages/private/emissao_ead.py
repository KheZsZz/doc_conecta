import io
import zipfile

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
from src.auth.permissions import exigir_permissao

exigir_permissao("emissao_ead")

st.title("🎓 Emissão EAD")
st.markdown(
    "Envie a planilha de conclusões, confira o vínculo **CNPJ → empresa** e "
    "**sigla → curso**, escolha o assinante e baixe o ZIP dos certificados."
)

with st.expander("Formato da planilha", expanded=False):
    st.markdown(
        """
Colunas esperadas:

| CNPJ | Nome | E-mail | CPF | SIGLA CURSO | CARGA | Progresso | Data de Inicio | Data de Finalização |

- Empresa buscada pelo **CNPJ** (tabela `clients`)
- Curso buscado pela **SIGLA CURSO** (tabela `cursos`)
- Só emite linhas com **Progresso ≥ 0,96**
- Nome do arquivo: `NOME DO ALUNO - SIGLA.pdf`
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

st.subheader(f"Pré-visualização — {len(linhas)} certificado(s)")

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

if problemas:
    st.error("Corrija os cadastros antes de emitir:\n\n- " + "\n- ".join(problemas))
    st.stop()

# Assinante + CT
ct = buscar_ct_conecta()
if ct:
    st.caption(f"CT / fundo: **{ct.get('name') or ct.get('full_name')}**")
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

ss_key = "ead_zip_bytes"
ss_meta = "ead_zip_meta"

if st.session_state.get(ss_key):
    meta = st.session_state.get(ss_meta) or {}
    st.success(f"✅ {meta.get('ok', 0)} certificado(s) gerado(s).")
    if meta.get("falhas"):
        with st.expander("Falhas", expanded=False):
            for f in meta["falhas"]:
                st.write(f"- {f}")
    st.download_button(
        "📥 Baixar ZIP dos certificados",
        data=st.session_state[ss_key],
        file_name=meta.get("nome_zip") or "certificados_ead.zip",
        mime="application/zip",
        use_container_width=True,
        key="dl_ead_zip_persist",
    )

if st.button("🚀 Gerar certificados EAD (ZIP)", type="primary", use_container_width=True):
    falhas: list[str] = []
    ok = 0
    zip_buf = io.BytesIO()

    with st.spinner("Gerando certificados..."):
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            usados: dict[str, int] = {}
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
                    # evita colisao de nomes
                    if fname in usados:
                        usados[fname] += 1
                        base, ext = fname.rsplit(".", 1)
                        fname = f"{base}_{usados[fname]}.{ext}"
                    else:
                        usados[fname] = 1
                    zf.writestr(fname, pdf)
                    ok += 1
                except Exception as e:
                    falhas.append(f"{L['nome']} / {L['sigla']}: {e}")

    if ok == 0:
        st.error("Nenhum certificado gerado.\n" + "\n".join(falhas))
    else:
        zip_buf.seek(0)
        st.session_state[ss_key] = zip_buf.getvalue()
        st.session_state[ss_meta] = {
            "ok": ok,
            "falhas": falhas,
            "nome_zip": "certificados_ead.zip",
        }
        st.success(f"✅ {ok} certificado(s) gerado(s).")
        if falhas:
            with st.expander("Falhas", expanded=True):
                for f in falhas:
                    st.write(f"- {f}")
        st.download_button(
            "📥 Baixar ZIP dos certificados",
            data=st.session_state[ss_key],
            file_name="certificados_ead.zip",
            mime="application/zip",
            use_container_width=True,
            key="dl_ead_zip_new",
        )
