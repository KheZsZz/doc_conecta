from datetime import date

import pandas as pd
import streamlit as st

from src.auth.permissions import (
    ct_id_atual,
    exigir_permissao,
    is_consulta,
)
from src.utils.imprimir_documentacao import (
    gerar_pdf_tipo,
    gerar_zip_documentacao_completa,
    listar_cts,
    turmas_do_ct_na_data,
)
from src.pages.private.turmas.helpers import label_empresa
from src.pages.private.turmas.modals.emitir_documentos.data import fetch_ct

exigir_permissao("imprimir_documentacao")

st.title("Imprimir Documentação")

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
        "Documentação completa (ZIP com 1 PDF de cada tipo)",
        "Certificados dos alunos",
        "Certificados da empresa",
        "Atestados (somente cursos que exigem)",
        "Carteirinhas",
    ],
    horizontal=False,
)

TIPO_COMPLETA = "completa"
TIPO_MAP = {
    "Documentação completa (ZIP com 1 PDF de cada tipo)": TIPO_COMPLETA,
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

# Nomes das empresas (Nome (CNPJ) - Unidade) para a tabela
emp_map: dict = {}
try:
    from src.config.database import supabase

    emp_ids = list({t.get("client_id") for t in turmas if t.get("client_id")})
    if emp_ids:
        res = (
            supabase.table("clients")
            .select("id, name, cnpj, sigla")
            .in_("id", emp_ids)
            .execute()
        )
        if res and res.data:
            emp_map = {r["id"]: label_empresa(r) for r in res.data}
except Exception:
    pass

# Seleção de turmas: por padrão todas marcadas; recomeça ao trocar CT/data
_base = (str(ct_fix), data_ref.isoformat())
_cfg = st.session_state.get("imp_sel_cfg")
if not _cfg or _cfg.get("base") != _base:
    _cfg = {"base": _base, "ver": 0, "padrao": True}
    st.session_state["imp_sel_cfg"] = _cfg

c_sel1, c_sel2, _ = st.columns([1, 1, 3])
with c_sel1:
    if st.button("Marcar todas", use_container_width=True):
        _cfg["ver"] += 1
        _cfg["padrao"] = True
        st.rerun()
with c_sel2:
    if st.button("Desmarcar todas", use_container_width=True):
        _cfg["ver"] += 1
        _cfg["padrao"] = False
        st.rerun()

preview = pd.DataFrame(
    [
        {
            "Incluir": _cfg["padrao"],
            "Empresa": emp_map.get(t.get("client_id")) or "—",
            "Turma": t.get("titulo") or "",
            "Emitido": "Sim" if t.get("documento_emitido") else "Não",
        }
        for t in turmas
    ]
)
editado = st.data_editor(
    preview,
    use_container_width=True,
    hide_index=True,
    disabled=["Empresa", "Turma", "Emitido"],
    column_config={
        "Incluir": st.column_config.CheckboxColumn(
            "Incluir", help="Desmarque para não gerar os documentos desta turma."
        ),
    },
    key=f"imp_sel_{_base[0]}_{_base[1]}_{_cfg['ver']}",
)
turmas_sel = [turmas[i] for i in editado.index[editado["Incluir"]]]
st.caption(f"**{len(turmas_sel)}** de **{len(turmas)}** turma(s) selecionada(s).")

ss_key = "imp_doc_pdf"
ss_nome = "imp_doc_nome"
ss_meta = "imp_doc_meta"
ss_mime = "imp_doc_mime"

if st.session_state.get(ss_key):
    meta = st.session_state.get(ss_meta) or {}
    st.success(meta.get("msg") or "Arquivo pronto.")
    if meta.get("avisos"):
        with st.expander("Avisos", expanded=False):
            for a in meta["avisos"]:
                st.write(f"- {a}")
    if meta.get("erros"):
        with st.expander("Falhas", expanded=False):
            for e in meta["erros"]:
                st.write(f"- {e}")
    _eh_zip = st.session_state.get(ss_mime) == "application/zip"
    st.download_button(
        "Baixar ZIP" if _eh_zip else "Baixar PDF",
        data=st.session_state[ss_key],
        file_name=st.session_state.get(ss_nome) or "documentacao.pdf",
        mime=st.session_state.get(ss_mime) or "application/pdf",
        use_container_width=True,
        key="dl_imp_persist",
    )

completa = tipo == TIPO_COMPLETA
if st.button(
    "Gerar documentação completa (ZIP)" if completa else "Gerar PDF consolidado",
    type="primary",
    use_container_width=True,
    disabled=not turmas_sel,
):
    ct = fetch_ct(ct_fix) or mapa_ct.get(ct_fix) or {}
    if completa:
        with st.spinner("Gerando os 4 PDFs das turmas selecionadas (pode levar alguns minutos)..."):
            pdf, avisos, erros = gerar_zip_documentacao_completa(
                turmas=turmas_sel,
                ct=ct,
                data_ref=data_ref,
            )
    else:
        with st.spinner("Gerando PDF das turmas selecionadas..."):
            pdf, avisos, erros = gerar_pdf_tipo(
                tipo=tipo,
                turmas=turmas_sel,
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
    ext = "zip" if completa else "pdf"
    mime = "application/zip" if completa else "application/pdf"
    nome_arq = (
        f"{'documentacao_completa' if completa else tipo}_{slug_ct}_{data_ref.strftime('%Y%m%d')}.{ext}"
    )
    st.session_state[ss_key] = pdf
    st.session_state[ss_nome] = nome_arq
    st.session_state[ss_mime] = mime
    st.session_state[ss_meta] = {
        "msg": (
            f"ZIP gerado com os documentos de **{len(turmas_sel)}** turma(s)."
            if completa
            else f"PDF gerado com documentos de **{len(turmas_sel)}** turma(s)."
        ),
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
        "Baixar ZIP" if completa else "Baixar PDF",
        data=pdf,
        file_name=nome_arq,
        mime=mime,
        use_container_width=True,
        key="dl_imp_new",
    )
