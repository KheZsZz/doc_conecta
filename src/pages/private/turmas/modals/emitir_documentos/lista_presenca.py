import io

import pandas as pd
import streamlit as st

from .data import fetch_matriculas
from .alunos import alunos_para_lista_presenca


def gerar_lista_presenca(tid: str, titulo_turma: str) -> None:
    if not st.button(
        "🚀 Processar e Gerar Lista", type="primary", use_container_width=True
    ):
        return

    try:
        with st.spinner("Buscando alunos matriculados..."):
            matriculas = fetch_matriculas(tid)

            if not matriculas:
                st.warning("⚠️ Nenhum aluno matriculado para gerar a lista.")
                return

            alunos = alunos_para_lista_presenca(matriculas)
            df = pd.DataFrame(alunos)

            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="Lista de Presença")

            st.success("✅ Lista gerada com sucesso!")
            st.download_button(
                label="📥 Baixar Lista de Presença (.xlsx)",
                data=buffer.getvalue(),
                file_name=f"lista_presenca_{titulo_turma.replace(' ', '_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key=f"dl_lista_{tid}",
            )
    except Exception as e:
        st.error(f"❌ Erro ao gerar a lista de presença: {e}")