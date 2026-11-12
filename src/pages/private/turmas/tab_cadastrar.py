from datetime import datetime
import streamlit as st
from src.config.database import supabase


def _label_empresa(e: dict) -> str:
    nome = (e.get("name") or "Sem nome").strip()
    unidade = (e.get("sigla") or "").strip()
    cnpj = (e.get("cnpj") or "Sem CNPJ").strip()
    if unidade:
        return f"{nome} · {unidade} ({cnpj})"
    return f"{nome} ({cnpj})"


def render_tab_cadastrar():
    st.subheader("Formulário de Abertura de Turma")

    try:
        cursos_res = supabase.table("cursos").select("id, name").execute()
        instrutores_res = supabase.table("instrutores").select("id, name").execute()
        empresas_res = supabase.table("clients").select("id, name, cnpj, sigla").execute()
        cts_res = supabase.table("cts").select("id, name").execute()

        cursos_dict = {c["name"]: c["id"] for c in cursos_res.data} if cursos_res.data else {}
        instrutores_dict = (
            {i["name"]: i["id"] for i in instrutores_res.data} if instrutores_res.data else {}
        )

        empresas_dict = {}
        if empresas_res.data:
            ordenadas = sorted(
                empresas_res.data,
                key=lambda e: (
                    (e.get("name") or "").strip().lower(),
                    (e.get("sigla") or "").strip().lower(),
                ),
            )
            for e in ordenadas:
                label = _label_empresa(e)
                if label in empresas_dict:
                    label = f"{label} [{str(e.get('id', ''))[:8]}]"
                empresas_dict[label] = e["id"]

        cts_dict = {c["name"]: c["id"] for c in cts_res.data} if cts_res.data else {}

    except Exception as e:
        st.error(f"Erro ao carregar dados auxiliares: {e}")
        cursos_dict, instrutores_dict, empresas_dict, cts_dict = {}, {}, {}, {}

    with st.form("form_nova_turma", clear_on_submit=True):
        titulo = st.text_input(
            "Título Identificador da Turma*",
            placeholder="Ex: Turma CIPA - Outubro 2026 - Empresa XPTO",
        )

        col1, col2, col3 = st.columns(3)
        with col1:
            data_treinamento = st.date_input("Data do Treinamento*", value=datetime.today())
        with col2:
            curso_selecionado = st.selectbox(
                "Curso / Treinamento*",
                ["(Nenhum curso cadastrado)"] if not cursos_dict else list(cursos_dict.keys()),
            )
        with col3:
            instrutor_selecionado = st.selectbox(
                "Instrutor Titular*",
                ["(Nenhum instrutor cadastrado)"]
                if not instrutores_dict
                else list(instrutores_dict.keys()),
            )

        col4, col5 = st.columns(2)
        with col4:
            empresa_selecionada = st.selectbox(
                "Empresa Contratante (Cliente)*",
                ["Nenhuma Empresa"] + list(empresas_dict.keys()),
                help="Formato: Razão social · Unidade (CNPJ).",
            )
        with col5:
            ct_selecionado = st.selectbox(
                "CT Responsável / Local*",
                ["(Nenhum CT cadastrado)"] if not cts_dict else list(cts_dict.keys()),
            )

        st.markdown("#### Especificações do Treinamento")
        st.caption(
            "O **Nível** fica gravado na **turma** e é o que aparece nos certificados "
            "(não vem do cadastro do curso)."
        )
        col6, col7, col8 = st.columns(3)
        with col6:
            modalidade = st.selectbox(
                "Modalidade",
                ["In Company", "Presencial (Centro de Treinamento)", "EAD", "Semipresencial", "Online", "In Company - Centro de treinamento"],
            )
        with col7:
            nivel = st.selectbox(
                "Nível",
                ["Formação", "Básico", "Intermediário", "Avançado", "Reciclagem", "Palestra"],
            )
        with col8:
            carga_horaria_num = st.number_input(
                "Carga Horária (Apenas números)", min_value=1, value=8, step=1
            )

        submit_turma = st.form_submit_button("Cadastrar", type="primary")

        if submit_turma:
            if not titulo.strip():
                st.warning("⚠️ O título da turma é obrigatório.")
            elif (
                "(Nenhum" in curso_selecionado
                or "(Nenhum" in instrutor_selecionado
                or "(Nenhum" in ct_selecionado
            ):
                st.warning(
                    "⚠️ Você precisa ter cursos, instrutores e CTs cadastrados antes de abrir uma turma."
                )
            else:
                try:
                    client_id_val = (
                        empresas_dict.get(empresa_selecionada)
                        if empresa_selecionada and "Nenhuma" not in empresa_selecionada
                        else None
                    )
                    carga_final_str = (
                        f"{carga_horaria_num} Horas" if carga_horaria_num > 1 else "8 Hora"
                    )

                    nova_turma = {
                        "titulo": titulo.strip(),
                        "modalidade": modalidade,
                        "nivel": nivel,
                        "carga_horaria": carga_final_str,
                        "data_treinamento": data_treinamento.isoformat(),
                        "curso_id": cursos_dict[curso_selecionado],
                        "instrutor_id": instrutores_dict[instrutor_selecionado],
                        "client_id": client_id_val,
                        "ct_id": cts_dict[ct_selecionado],
                    }
                    supabase.table("turmas").insert(nova_turma).execute()
                    st.success("✅ Turma aberta com sucesso!")
                    st.balloons()
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Erro ao abrir turma: {e}")
