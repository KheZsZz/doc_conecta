import streamlit as st
import pandas as pd
from src.config.database import supabase
from src.utils.import_helper import processar_planilha_alunos

@st.dialog("📤 Importar Alunos (Excel)", width="large")
def modal_importar_excel(tid, titulo_turma, client_id, data_treinamento_str, carga_horaria_str):
    st.subheader("Importar Lista de Presença para a Turma")
    st.write(f"**Turma:** {titulo_turma}")

    st.info("""
    Para facilitar o processo, você pode usar a nossa ferramenta de Extração Automática via OCR 
    na página "Leitor de PDF/Imagens" para converter a sua lista assinada em um arquivo Excel (.xlsx).

    A planilha deve conter preferencialmente as colunas: **NOME, RG, CPF**.
    """)

    arquivo_upload = st.file_uploader(
        "Selecione o arquivo Excel (.xlsx ou .xls)",
        type=["xlsx", "xls"],
        key=f"up_excel_{tid}",
    )

    if not arquivo_upload:
        return

    try:
        df_temp = pd.read_excel(arquivo_upload)
        st.write("📊 Pré-visualização das Colunas Encontradas:")
        st.dataframe(df_temp.head(3), use_container_width=True)

        colunas_disp = ["(Nenhuma)"] + list(df_temp.columns)

        st.markdown("### Mapeamento de Colunas")
        col1, col2, col3 = st.columns(3)
        with col1:
            col_nome = st.selectbox(
                "Coluna de NOME*",
                options=colunas_disp,
                index=colunas_disp.index("NOME") if "NOME" in colunas_disp else 0,
            )
        with col2:
            col_cpf = st.selectbox(
                "Coluna de CPF",
                options=colunas_disp,
                index=colunas_disp.index("CPF") if "CPF" in colunas_disp else 0,
            )
        with col3:
            col_rg = st.selectbox(
                "Coluna de RG",
                options=colunas_disp,
                index=colunas_disp.index("RG") if "RG" in colunas_disp else 0,
            )

        if st.button(
            "🚀 Processar e Matricular Alunos",
            type="primary",
            use_container_width=True,
            key=f"btn_proc_excel_{tid}",
        ):
            if col_nome == "(Nenhuma)":
                st.error("⚠️ Você deve selecionar qual é a coluna que contém o NOME dos alunos.")
                st.stop()

            mapa_colunas = {
                "NOME": col_nome,
                "CPF": col_cpf if col_cpf != "(Nenhuma)" else None,
                "RG": col_rg if col_rg != "(Nenhuma)" else None,
            }

            with st.spinner(
                "A analisar a planilha e matricular os alunos no sistema... (Isto pode levar alguns segundos)"
            ):
                resultado = processar_planilha_alunos(
                    arquivo_bytes=arquivo_upload.getvalue(),
                    nome_arquivo=arquivo_upload.name,
                    mapeamento_colunas=mapa_colunas,
                    turma_id=tid,
                    client_id=client_id,
                    data_treinamento=data_treinamento_str,
                    carga_horaria=carga_horaria_str,
                )

                if resultado["sucesso"]:
                    st.success(resultado["mensagem"])

                    col_met1, col_met2 = st.columns(2)
                    col_met1.metric("Alunos Inseridos/Encontrados", resultado["alunos_processados"])
                    col_met2.metric("Novas Matrículas", resultado["matriculas_criadas"])

                    if resultado["erros"]:
                        st.warning("Algumas linhas tiveram erros ou alunos já estavam matriculados:")
                        for err in resultado["erros"]:
                            st.write(f"- {err}")

                    st.balloons()
                else:
                    st.error(f"Falha no processamento: {resultado['mensagem']}")

    except Exception as e:
        st.error(f"Erro ao ler o arquivo Excel: {e}")