import streamlit as st
import pandas as pd

from src.config.database import supabase

try:
    from src.utils.lista_lote import (
        gerar_template_excel,
        gerar_template_excel_chave,
        gerar_export_turmas_excel,  
        processar_lista_lote,
        processar_lista_lote_por_chave,
        COLUNAS_MODELO,
        COLUNAS_MODELO_CHAVE,
    )
except Exception as e:
    st.error(f"Erro ao carregar modulo de listas: {type(e).__name__}: {e}")
    st.stop()

MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

st.title("Subir Listas")


tab_id, tab_chave = st.tabs(
    ["ID da turma", "CNPJ + Data + Unidade"]
)


def _bloco_upload_e_processar(processar_fn, key_prefix: str):
    arquivo = st.file_uploader(
        "Arquivo Excel (.xlsx, .xls ou .xlsm)",
        type=["xlsx", "xls", "xlsm"],
        key=f"upload_{key_prefix}",
    )
    if not arquivo:
        return

    try:
        df_preview = pd.read_excel(arquivo)
        st.write("Pré-visualização (primeiras linhas):")
        st.dataframe(df_preview.head(10), use_container_width=True)
        st.info(
            f"**{len(df_preview)}** linha(s). Colunas: "
            + ", ".join(str(c) for c in df_preview.columns)
        )

        if st.button(
            "🚀 Processar e matricular em lote",
            type="primary",
            use_container_width=True,
            key=f"btn_{key_prefix}",
        ):
            with st.spinner("Processando planilha e matriculando alunos..."):
                resultado = processar_fn(
                    arquivo_bytes=arquivo.getvalue(),
                    nome_arquivo=arquivo.name,
                )

            if resultado["sucesso"]:
                st.success(resultado["mensagem"])
                c1, c2 = st.columns(2)
                c1.metric("Alunos processados", resultado["alunos_processados"])
                c2.metric("Novas matrículas", resultado["matriculas_criadas"])
                st.balloons()
            else:
                st.error(resultado["mensagem"])

            if resultado.get("erros"):
                with st.expander(
                    f"⚠️ Avisos / linhas ignoradas ({len(resultado['erros'])})",
                    expanded=True,
                ):
                    for err in resultado["erros"]:
                        st.write(f"- {err}")
    except Exception as e:
        st.error(f"Erro ao ler o arquivo: {e}")


# ==========================================================================
# ID TURMA
# ==========================================================================
with tab_id:
    st.subheader("Vínculo pelo ID da turma")

    try:
        st.download_button(
            label="Baixar modelo Excel (.xlsx)",
            data=gerar_template_excel(),
            file_name="modelo_lista_alunos_id_turma.xlsx",
            mime=MIME_XLSX,
            use_container_width=True,
            key="dl_modelo_id",
        )
    except Exception as e:
        st.error(f"Não foi possível gerar o modelo: {e}")

    st.markdown("---")
    st.subheader("Envie a planilha")
    _bloco_upload_e_processar(processar_lista_lote, "id_turma")


# ==========================================================================
# CNPJ + DATA + UNIDADE
# ==========================================================================
with tab_chave:
    st.subheader("Vínculo por CNPJ + data + unidade")
    st.markdown(
        "Ideal quando as turmas foram abertas em lote: a planilha de alunos "
        "não precisa do UUID — usa os mesmos dados da empresa/unidade."
    )

    try:
        st.download_button(
            label="Baixar modelo Excel (CNPJ + Data + Unidade)",
            data=gerar_template_excel_chave(),
            file_name="modelo_lista_alunos_cnpj_unidade.xlsx",
            mime=MIME_XLSX,
            use_container_width=True,
            key="dl_modelo_chave",
        )
    except Exception as e:
        st.error(f"Não foi possível gerar o modelo: {e}")
        
    st.subheader("Envie a planilha")
    _bloco_upload_e_processar(processar_lista_lote_por_chave, "chave")
