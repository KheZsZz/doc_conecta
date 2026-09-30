import pandas as pd
import streamlit as st
from src.config.database import supabase

@st.dialog("📝 Visualizar / Editar Matrículas", width="large")
def modal_editar_matriculas(tid, titulo_turma):
    st.subheader(f"Matrículas: {titulo_turma}")

    try:
        mat_res = (
            supabase.table("matriculas")
            .select("id, aluno_id, carga_horaria, alunos(name, cpf, rg)")
            .eq("turma_id", tid)
            .execute()
        )

        if not mat_res or not mat_res.data:
            st.info("Nenhum aluno matriculado nesta turma até o momento.")
            return

        matriculas_lista = []
        for m in mat_res.data:
            aluno_info = m.get("alunos") or {}
            matriculas_lista.append({
                "matricula_id": m.get("id"),
                "aluno_id": m.get("aluno_id"),
                "Nome": aluno_info.get("name", "Sem Nome"),
                "CPF": aluno_info.get("cpf", ""),
                "RG": aluno_info.get("rg", ""),
                "Carga Horária": m.get("carga_horaria", ""),
            })

        df_mat = pd.DataFrame(matriculas_lista)

        if not df_mat.empty:
            st.dataframe(
                df_mat[["Nome", "CPF", "RG", "Carga Horária"]],
                use_container_width=True,
                hide_index=True,
            )

            st.markdown("---")
            st.write("⚠️ **Ações de Remoção:**")

            aluno_para_remover = st.selectbox(
                "Selecione um aluno para remover desta turma:",
                options=df_mat.to_dict("records"),
                format_func=lambda x: f"{x['Nome']} (CPF: {x['CPF']})",
                key=f"rem_aluno_{tid}",
            )

            if aluno_para_remover:
                if st.button(
                    f"🗑️ Remover {aluno_para_remover['Nome']} da Turma",
                    type="primary",
                    key=f"btn_rem_{tid}",
                ):
                    try:
                        supabase.table("matriculas").delete().eq(
                            "id", aluno_para_remover["matricula_id"]
                        ).execute()
                        st.success("✅ Matrícula removida com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao remover: {e}")

    except Exception as e:
        st.error(f"Erro ao buscar matrículas: {e}")