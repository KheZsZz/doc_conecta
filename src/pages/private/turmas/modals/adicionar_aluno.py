import re
from datetime import date
import streamlit as st
from src.config.database import supabase

@st.dialog("👥 Adicionar Aluno Manualmente", width="medium")
def modal_adicionar_aluno(turma_id, titulo_turma, client_id, data_treinamento, carga_horaria):
    st.write(f"**Turma:** {titulo_turma}")
    st.caption("Os alunos adicionados aqui serão vinculados à empresa desta turma.")

    with st.form(f"form_add_aluno_{turma_id}"):
        nome_aluno = st.text_input("Nome Completo*")

        col1, col2 = st.columns(2)
        with col1:
            cpf_aluno = st.text_input("CPF")
        with col2:
            rg_aluno = st.text_input("RG")

        col_nasc, _ = st.columns(2)
        with col_nasc:
            data_nasc_input = st.date_input(
                "Data de Nascimento", value=None, min_value=date(1920, 1, 1)
            )

        submit_aluno = st.form_submit_button(
            "💾 Salvar Aluno e Matricular", type="primary", use_container_width=True
        )

        if submit_aluno:
            if not nome_aluno.strip():
                st.warning("⚠️ O nome do aluno é obrigatório.")
                return

            try:
                st.info("Buscando se o aluno já existe (pelo CPF ou Nome)...")
                aluno_id = None

                if cpf_aluno.strip():
                    cpf_limpo = re.sub(r"[^0-9]", "", cpf_aluno)
                    if cpf_limpo:
                        aluno_res = (
                            supabase.table("alunos")
                            .select("id")
                            .eq("cpf", cpf_aluno.strip())
                            .execute()
                        )
                        if aluno_res and aluno_res.data:
                            aluno_id = aluno_res.data[0]["id"]

                if not aluno_id:
                    aluno_res = (
                        supabase.table("alunos")
                        .select("id")
                        .ilike("name", nome_aluno.strip())
                        .execute()
                    )
                    if aluno_res and aluno_res.data:
                        aluno_id = aluno_res.data[0]["id"]

                data_nasc_str = data_nasc_input.isoformat() if data_nasc_input else None

                if not aluno_id:
                    novo_aluno = {
                        "name": nome_aluno.strip().upper(),
                        "cpf": cpf_aluno.strip() or None,
                        "rg": rg_aluno.strip() or None,
                        "client_id": client_id,
                        "data_nasc": data_nasc_str,
                    }
                    insert_res = supabase.table("alunos").insert(novo_aluno).execute()
                    if insert_res and insert_res.data:
                        aluno_id = insert_res.data[0]["id"]

                if aluno_id:
                    matricula_res = (
                        supabase.table("matriculas")
                        .select("id")
                        .eq("turma_id", turma_id)
                        .eq("aluno_id", aluno_id)
                        .execute()
                    )
                    if matricula_res and matricula_res.data:
                        st.warning("⚠️ Este aluno já está matriculado nesta turma!")
                    else:
                        nova_matricula = {
                            "turma_id": turma_id,
                            "aluno_id": aluno_id,
                            "data_treinamento": data_treinamento,
                            "carga_horaria": carga_horaria,
                        }
                        supabase.table("matriculas").insert(nova_matricula).execute()
                        st.success(f"✅ Aluno {nome_aluno} adicionado e matriculado com sucesso!")
                        st.rerun()

            except Exception as e:
                st.error(f"❌ Erro ao adicionar/matricular aluno: {e}")