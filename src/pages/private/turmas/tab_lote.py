"""Aba: cadastro de turmas em lote via planilha."""
from __future__ import annotations

import streamlit as st

from src.config.database import supabase
from src.utils.turmas_lote import (
    gerar_modelo_planilha,
    importar_turmas_lote,
    ler_planilha_turmas,
)


def render_tab_lote():
    st.subheader("Cadastro de turmas em lote")
    st.markdown(
        "Envie uma planilha com os dados das turmas. "
        "Se o **CNPJ** ainda não existir, a **empresa é cadastrada automaticamente**."
    )

    with st.expander("Formato da planilha / modelo", expanded=False):
        st.markdown(
            """
**Colunas principais**

| Coluna | Obrigatório | Observação |
|--------|-------------|------------|
| CNPJ | sim | só números ou formatado |
| NOME EMPRESA | sim | razão social |
| DATA TREINAMENTO | sim | `YYYY-MM-DD` ou `DD/MM/YYYY` |
| SIGLA CURSO ou CURSO | sim | deve existir no cadastro de cursos |
| ENDERECO | não | usado se criar empresa |
| RESPONSAVEL | não | contato da empresa |
| TELEFONE / EMAIL | não | |
| UNIDADE | não | campo unidade da empresa |
| CARGA HORARIA | não | padrão 8 Horas |
| MODALIDADE | não | padrão In Company |
| NIVEL | não | padrão Formação |
| INSTRUTOR | não | usa o padrão da tela se vazio |
| CT | não | usa o padrão da tela se vazio |
| TITULO | não | gerado automaticamente se vazio |
            """
        )
        st.download_button(
            "📥 Baixar modelo .xlsx",
            data=gerar_modelo_planilha(),
            file_name="modelo_turmas_lote.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_modelo_turmas_lote",
        )

    # Padrões para linhas sem instrutor/CT
    try:
        inst_res = (
            supabase.table("instrutores")
            .select("id, name")
            .eq("is_active", True)
            .order("name")
            .execute()
        )
        cts_res = supabase.table("cts").select("id, name").order("name").execute()
        instrutores = inst_res.data or []
        cts = cts_res.data or []
    except Exception as e:
        st.error(f"Erro ao carregar instrutores/CTs: {e}")
        return

    if not instrutores:
        st.warning("Cadastre ao menos um instrutor ativo antes do lote.")
        return
    if not cts:
        st.warning("Cadastre ao menos um CT antes do lote.")
        return

    col_p1, col_p2 = st.columns(2)
    with col_p1:
        labels_i = [i["name"] for i in instrutores]
        idx_i = next(
            (i for i, x in enumerate(instrutores) if "conecta" in (x.get("name") or "").lower()),
            0,
        )
        inst_label = st.selectbox(
            "Instrutor padrão (se a planilha não trouxer)",
            labels_i,
            index=min(idx_i, len(labels_i) - 1),
            key="lote_inst_padrao",
        )
        inst_id = next(i["id"] for i in instrutores if i["name"] == inst_label)
    with col_p2:
        labels_ct = [c["name"] for c in cts]
        idx_ct = next(
            (i for i, x in enumerate(cts) if "conecta" in (x.get("name") or "").lower()),
            0,
        )
        ct_label = st.selectbox(
            "CT padrão (se a planilha não trouxer)",
            labels_ct,
            index=min(idx_ct, len(labels_ct) - 1),
            key="lote_ct_padrao",
        )
        ct_id = next(c["id"] for c in cts if c["name"] == ct_label)

    uploaded = st.file_uploader(
        "Planilha de turmas (.xlsx)",
        type=["xlsx", "xls"],
        key="up_turmas_lote",
    )
    if not uploaded:
        st.info("Faça o upload da planilha para continuar.")
        return

    linhas, erros_leitura = ler_planilha_turmas(uploaded.getvalue())

    if erros_leitura:
        with st.expander(f"Avisos da leitura ({len(erros_leitura)})", expanded=True):
            for e in erros_leitura:
                st.write(f"- {e}")

    if not linhas:
        st.error("Nenhuma linha válida para importar.")
        return

    st.success(f"**{len(linhas)}** linha(s) pronta(s) para importação.")
    preview = [
        {
            "Linha": L["linha"],
            "CNPJ": L["cnpj"],
            "Empresa": L["nome_empresa"],
            "Curso": L.get("sigla_curso") or L.get("curso_nome"),
            "Data": L["data_treinamento"],
            "Carga": L["carga_horaria"],
            "Modalidade": L["modalidade"],
            "Nível": L["nivel"],
        }
        for L in linhas
    ]
    st.dataframe(preview, use_container_width=True, hide_index=True)

    if st.button(
        "🚀 Importar turmas",
        type="primary",
        use_container_width=True,
        key="btn_import_turmas_lote",
    ):
        with st.spinner("Importando turmas e empresas..."):
            result = importar_turmas_lote(
                linhas,
                instrutor_padrao_id=inst_id,
                ct_padrao_id=ct_id,
            )

        st.success(
            f"✅ **{result['criadas']}** turma(s) criada(s). "
            f"**{result['empresas_novas']}** empresa(s) nova(s)."
        )

        if result.get("detalhes"):
            st.dataframe(result["detalhes"], use_container_width=True, hide_index=True)

        if result.get("erros"):
            with st.expander(f"Erros ({len(result['erros'])})", expanded=True):
                for e in result["erros"]:
                    st.write(f"- {e}")

        if result["criadas"]:
            st.info("Atualize a aba **Turmas Abertas** para ver as novas turmas.")
