from datetime import date

import streamlit as st

from src.auth.permissions import (
    ct_id_atual,
    exigir_permissao,
    is_consulta,
)
from src.utils.imprimir_documentacao import (
    gerar_pdf_tipo,
    listar_cts,
    turmas_do_ct_na_data,
)
from src.pages.private.turmas.modals.emitir_documentos.data import fetch_ct

exigir_permissao("imprimir_documentacao")

st.title("🖨️ Imprimir Documentação")
st.markdown(
    "Gera um **PDF único** com o tipo de documento escolhido para **todas as "
    "empresas/turmas do CT na data selecionada**.\n\n"
    "Atestados só entram quando o **curso exige atestado** no cadastro."
)

cts = listar_cts()
if not cts:
    st.error("Nenhum CT cadastrado.")
    st.stop()

mapa_ct = {c["id"]: c for c in cts if c.get("id")}
nome_por_id = {
    c["id"]: (c.get("name") or c.get("full_name") or str(c["id"]))
    for c in cts
    if c.get("id")
}

# CT: consulta fixo; admin/operacional escolhe
ct_fix = ct_id_atual() if is_consulta() else None

if is_consulta():
    if not ct_fix:
        st.error(
            "Seu usuário **Consulta** não está vinculado a um CT. "
            "Peça ao administrador para definir o CT no cadastro de usuários."
        )
        st.stop()
    if ct_fix not in mapa_ct:
        st.warning("CT vinculado não encontrado na lista — tentando carregar mesmo assim.")
    st.info(f"CT: **{nome_por_id.get(ct_fix, ct_fix)}** (vinculado ao seu usuário)")
else:
    opcoes = list(nome_por_id.keys())
    labels = [nome_por_id[i] for i in opcoes]
    idx = 0
    escolha = st.selectbox("Centro de Treinamento*", labels, index=idx)
    ct_fix = opcoes[labels.index(escolha)]

data_ref = st.date_input(
    "Data do treinamento*",
    value=date.today(),
    format="DD/MM/YYYY",
)

tipo_label = st.radio(
    "Tipo de documento*",
    options=[
        "Certificados dos alunos",
        "Certificados da empresa",
        "Atestados (somente cursos que exigem)",
        "Carteirinhas",
    ],
    horizontal=False,
)

TIPO_MAP = {
    "Certificados dos alunos": "cert_alunos",
    "Certificados da empresa": "cert_empresa",
    "Atestados (somente cursos que exigem)": "atestado",
    "Carteirinhas": "carteirinhas",
}
tipo = TIPO_MAP[tipo_label]

turmas = turmas_do_ct_na_data(ct_fix, data_ref)

st.subheader(
    f"Turmas em **{data_ref.strftime('%d/%m/%Y')}**: **{len(turmas)}**"
)

if not turmas:
    st.info("Nenhuma turma neste CT na data selecionada.")
    st.stop()

preview = []
for t in turmas:
    preview.append(
        {
            "Turma": t.get("titulo") or "",
            "Empresa ID": str(t.get("client_id") or "")[:8] + "…",
            "Curso ID": str(t.get("curso_id") or "")[:8] + "…",
            "Emitido": "Sim" if t.get("documento_emitido") else "Não",
        }
    )
# enriquece nomes se possível
try:
    from src.config.database import supabase

    emp_ids = list({t.get("client_id") for t in turmas if t.get("client_id")})
    emp_map = {}
    if emp_ids:
        res = (
            supabase.table("clients")
            .select("id, name")
            .in_("id", emp_ids)
            .execute()
        )
        if res and res.data:
            emp_map = {r["id"]: r.get("name") for r in res.data}
    for i, t in enumerate(turmas):
        preview[i]["Empresa"] = emp_map.get(t.get("client_id")) or "—"
        preview[i].pop("Empresa ID", None)
        preview[i].pop("Curso ID", None)
except Exception:
    pass

st.dataframe(preview, use_container_width=True, hide_index=True)

ss_key = "imp_doc_pdf"
ss_nome = "imp_doc_nome"
ss_meta = "imp_doc_meta"

if st.session_state.get(ss_key):
    meta = st.session_state.get(ss_meta) or {}
    st.success(meta.get("msg") or "PDF pronto.")
    if meta.get("avisos"):
        with st.expander("Avisos", expanded=False):
            for a in meta["avisos"]:
                st.write(f"- {a}")
    if meta.get("erros"):
        with st.expander("Falhas", expanded=False):
            for e in meta["erros"]:
                st.write(f"- {e}")
    st.download_button(
        "📥 Baixar PDF",
        data=st.session_state[ss_key],
        file_name=st.session_state.get(ss_nome) or "documentacao.pdf",
        mime="application/pdf",
        use_container_width=True,
        key="dl_imp_persist",
    )

if st.button("🖨️ Gerar PDF consolidado", type="primary", use_container_width=True):
    ct = fetch_ct(ct_fix) or mapa_ct.get(ct_fix) or {}
    with st.spinner("Gerando PDF de todas as turmas do dia..."):
        pdf, avisos, erros = gerar_pdf_tipo(
            tipo=tipo,
            turmas=turmas,
            ct=ct,
        )

    if not pdf:
        st.error("Nenhum documento gerado.")
        for e in erros:
            st.write(f"- {e}")
        for a in avisos:
            st.write(f"- {a}")
        st.stop()

    slug_ct = (nome_por_id.get(ct_fix) or "ct").replace(" ", "_")[:40]
    nome_arq = (
        f"{tipo}_{slug_ct}_{data_ref.strftime('%Y%m%d')}.pdf"
    )
    st.session_state[ss_key] = pdf
    st.session_state[ss_nome] = nome_arq
    st.session_state[ss_meta] = {
        "msg": f"PDF gerado com documentos de **{len(turmas)}** turma(s).",
        "avisos": avisos,
        "erros": erros,
    }
    st.success(st.session_state[ss_meta]["msg"])
    if avisos:
        with st.expander("Avisos", expanded=False):
            for a in avisos:
                st.write(f"- {a}")
    if erros:
        with st.expander("Falhas parciais", expanded=True):
            for e in erros:
                st.write(f"- {e}")
    st.download_button(
        "📥 Baixar PDF",
        data=pdf,
        file_name=nome_arq,
        mime="application/pdf",
        use_container_width=True,
        key="dl_imp_new",
    )
