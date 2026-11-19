import streamlit as st

from src.utils.lista_presenca_excel import gerar_lista_presenca_xlsx

from .data import fetch_empresa, fetch_matriculas, fetch_turma
from .alunos import alunos_para_lista_presenca


def gerar_lista_presenca(tid: str, titulo_turma: str) -> None:
    if not st.button(
        "Processar e Gerar Lista", type="primary", use_container_width=True
    ):
        return

    try:
        with st.spinner("Buscando alunos matriculados..."):
            turma = fetch_turma(tid)
            matriculas = fetch_matriculas(tid)

            if not matriculas:
                st.warning("Nenhum aluno matriculado para gerar a lista.")
                return

            client_id = turma.get("client_id")
            # se matrícula tiver client próprio, ainda usa empresa da turma no cabeçalho
            empresa = fetch_empresa(client_id)
            alunos = alunos_para_lista_presenca(matriculas)

            xlsx_bytes = gerar_lista_presenca_xlsx(
                alunos=alunos,
                empresa=empresa,
                data_treinamento=str(turma.get("data_treinamento") or ""),
            )

            st.success("Lista gerada com sucesso!")
            st.download_button(
                label="Baixar Lista de Presença (.xlsx)",
                data=xlsx_bytes,
                file_name=f"lista_presenca_{titulo_turma.replace(' ', '_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key=f"dl_lista_{tid}",
            )
    except Exception as e:
        st.error(f"Erro ao gerar a lista de presença: {e}")
