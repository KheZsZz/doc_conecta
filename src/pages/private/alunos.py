import streamlit as st
from datetime import date, datetime
from src.config.database import supabase

st.title("🎓 Cadastro Individual de Alunos")
st.markdown(
    "Matricule alunos manualmente em turmas com documentação **pendente**."
)


def formatar_data_br(data_str) -> str:
    if not data_str:
        return "—"
    s = str(data_str).strip()[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return s


# ==========================================
# 1. BUSCAR TURMAS PENDENTES (não emitidas)
# ==========================================
turmas_dict = {}
turmas_info_completa = {}

try:
    res_turmas = (
        supabase.table("turmas")
        .select("*")
        .order("data_treinamento", desc=True)
        .execute()
    )

    if res_turmas and res_turmas.data:
        for t in res_turmas.data:
            doc_emitido = bool(t.get("documento_emitido", False))
            # Empresas/turmas já emitidas não aparecem
            if doc_emitido:
                continue

            tid = t.get("id")
            titulo = t.get("titulo", "Sem título")
            data_t = t.get("data_treinamento")
            data_br = formatar_data_br(data_t)

            rotulo = f"{data_br} | {titulo} (⚠️ Pendente)"
            turmas_dict[rotulo] = tid
            turmas_info_completa[tid] = t

except Exception as e:
    st.error(f"Erro ao buscar turmas: {e}")

# ==========================================
# 2. INTERFACE DE CADASTRO
# ==========================================
if not turmas_dict:
    st.success(
        "🎉 Não há turmas pendentes de documentação no momento."
    )
else:
    st.subheader("1. Selecione a Turma")

    turma_selecionada_rotulo = st.selectbox(
        "Turmas disponíveis",
        options=list(turmas_dict.keys()),
        help="Somente turmas com documentação pendente.",
    )

    turma_id_escolhida = turmas_dict[turma_selecionada_rotulo]
    dados_turma = turmas_info_completa[turma_id_escolhida]

    # Carga e empresa herdadas da turma (sem seção extra na UI)
    carga_padrao = (dados_turma.get("carga_horaria") or "08 Horas").strip()
    client_id_turma = dados_turma.get("client_id")

    st.markdown("---")
    st.subheader("2. Dados do Aluno")

    with st.form("form_cadastro_aluno", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            nome_aluno = st.text_input("Nome Completo do Aluno*")
            cpf_aluno = st.text_input("CPF* (Apenas números)", max_chars=14)
            data_nasc = st.date_input(
                "Data de Nascimento",
                value=None,
                min_value=date(1940, 1, 1),
                max_value=date.today(),
                format="DD/MM/YYYY",
            )

        with col2:
            rg_aluno = st.text_input("RG (Apenas números)", max_chars=11)
            email_aluno = st.text_input("E-mail (Opcional)")
            telefone_aluno = st.text_input("Telefone (Opcional)")

        submit_aluno = st.form_submit_button(
            "💾 Salvar Aluno e Matricular",
            type="primary",
            use_container_width=True,
        )

        if submit_aluno:
            cpf_limpo = (
                cpf_aluno.replace(".", "").replace("-", "").strip()
                if cpf_aluno
                else ""
            )
            rg_limpo = (
                rg_aluno.replace(".", "").replace("-", "").strip()
                if rg_aluno
                else None
            )

            if not nome_aluno or not cpf_limpo:
                st.warning("⚠️ Os campos Nome e CPF são obrigatórios!")
            elif len(cpf_limpo) != 11:
                st.warning("⚠️ O CPF deve conter 11 dígitos numéricos.")
            else:
                try:
                    with st.spinner("Processando matrícula..."):
                        aluno_id = None
                        aluno_existente = (
                            supabase.table("alunos")
                            .select("id")
                            .eq("cpf", cpf_limpo)
                            .execute()
                        )

                        if aluno_existente and aluno_existente.data:
                            aluno_id = aluno_existente.data[0].get("id")
                            payload_update = {"name": nome_aluno.strip()}
                            if rg_limpo:
                                payload_update["rg"] = rg_limpo
                            if data_nasc:
                                payload_update["data_nasc"] = data_nasc.isoformat()
                            if email_aluno:
                                payload_update["email"] = email_aluno.strip()
                            if telefone_aluno:
                                payload_update["phone"] = telefone_aluno.strip()
                            supabase.table("alunos").update(payload_update).eq(
                                "id", aluno_id
                            ).execute()
                        else:
                            payload_novo = {
                                "name": nome_aluno.strip(),
                                "cpf": cpf_limpo,
                                "rg": rg_limpo,
                                "data_nasc": data_nasc.isoformat()
                                if data_nasc
                                else None,
                                "email": email_aluno.strip()
                                if email_aluno
                                else None,
                                "phone": telefone_aluno.strip()
                                if telefone_aluno
                                else None,
                            }
                            res_novo = (
                                supabase.table("alunos")
                                .insert(payload_novo)
                                .execute()
                            )
                            aluno_id = res_novo.data[0].get("id")

                        payload_matricula = {
                            "aluno_id": aluno_id,
                            "turma_id": turma_id_escolhida,
                            "client_id": client_id_turma,
                            "carga_horaria": carga_padrao,
                            "data_treinamento": dados_turma.get(
                                "data_treinamento"
                            ),
                        }
                        supabase.table("matriculas").insert(
                            payload_matricula
                        ).execute()

                        st.success(
                            f"✅ Aluno **{nome_aluno}** cadastrado e matriculado "
                            f"com sucesso na turma!"
                        )
                        st.balloons()

                except Exception as e:
                    st.error(f"❌ Erro ao processar o cadastro do aluno: {e}")
