from datetime import date, datetime
import re

import streamlit as st

from src.config.database import supabase


def _parse_carga_num(carga: str | None) -> int:
    if not carga:
        return 8
    match = re.search(r"\d+", str(carga))
    return int(match.group()) if match else 8


def _parse_data(data_str) -> date:
    if not data_str:
        return date.today()
    try:
        s = str(data_str).split("T")[0]
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return date.today()


@st.dialog("✏️ Editar Turma", width="large")
def modal_editar_turma(tid: str):
    try:
        t_res = supabase.table("turmas").select("*").eq("id", tid).single().execute()
        turma = t_res.data if t_res and t_res.data else None
    except Exception as e:
        st.error(f"Erro ao carregar turma: {e}")
        return

    if not turma:
        st.error("Turma não encontrada.")
        return

    try:
        cursos_res = supabase.table("cursos").select("id, name").execute()
        instrutores_res = supabase.table("instrutores").select("id, name").execute()
        empresas_res = supabase.table("clients").select("id, name, cnpj").execute()
        cts_res = supabase.table("cts").select("id, name").execute()

        cursos_dict = {c["name"]: c["id"] for c in (cursos_res.data or [])}
        instrutores_dict = {i["name"]: i["id"] for i in (instrutores_res.data or [])}

        empresas_dict: dict[str, str | None] = {"Nenhuma Empresa": None}
        for e in empresas_res.data or []:
            cnpj_fmt = e.get("cnpj", "Sem CNPJ")
            empresas_dict[f"{e['name']} ({cnpj_fmt})"] = e["id"]

        cts_dict = {c["name"]: c["id"] for c in (cts_res.data or [])}
    except Exception as e:
        st.error(f"Erro ao carregar dados auxiliares: {e}")
        return

    def _idx_por_id(opcoes: dict, valor_id) -> int:
        if valor_id is None:
            return 0
        keys = list(opcoes.keys())
        for i, k in enumerate(keys):
            if opcoes[k] == valor_id:
                return i
        return 0

    modalidades = ["In Company", "Presencial (No CT)", "EAD", "Semipresencial"]
    niveis = ["Formação", "Básico", "Intermediário", "Avançado", "Reciclagem"]

    with st.form(f"form_editar_turma_{tid}"):
        titulo = st.text_input(
            "Título Identificador da Turma*",
            value=turma.get("titulo") or "",
        )

        col1, col2, col3 = st.columns(3)
        with col1:
            data_treinamento = st.date_input(
                "Data do Treinamento*",
                value=_parse_data(turma.get("data_treinamento")),
            )
        with col2:
            curso_keys = list(cursos_dict.keys()) or ["(Nenhum curso cadastrado)"]
            curso_selecionado = st.selectbox(
                "Curso / Treinamento*",
                curso_keys,
                index=_idx_por_id(cursos_dict, turma.get("curso_id")) if cursos_dict else 0,
            )
        with col3:
            inst_keys = list(instrutores_dict.keys()) or ["(Nenhum instrutor cadastrado)"]
            instrutor_selecionado = st.selectbox(
                "Instrutor Titular*",
                inst_keys,
                index=_idx_por_id(instrutores_dict, turma.get("instrutor_id"))
                if instrutores_dict
                else 0,
            )

        col4, col5 = st.columns(2)
        with col4:
            emp_keys = list(empresas_dict.keys())
            empresa_selecionada = st.selectbox(
                "Empresa Contratante (Cliente)*",
                emp_keys,
                index=_idx_por_id(empresas_dict, turma.get("client_id")),
            )
        with col5:
            ct_keys = list(cts_dict.keys()) or ["(Nenhum CT cadastrado)"]
            ct_selecionado = st.selectbox(
                "CT Responsável / Local*",
                ct_keys,
                index=_idx_por_id(cts_dict, turma.get("ct_id")) if cts_dict else 0,
            )

        st.markdown("#### Especificações do Treinamento")
        st.caption(
            "O **Nível** é da **turma** e é o valor impresso nos certificados."
        )
        col6, col7, col8 = st.columns(3)
        with col6:
            mod_atual = turma.get("modalidade") or modalidades[0]
            modalidade = st.selectbox(
                "Modalidade",
                modalidades,
                index=modalidades.index(mod_atual) if mod_atual in modalidades else 0,
            )
        with col7:
            nivel_atual = turma.get("nivel") or "Formação"
            nivel = st.selectbox(
                "Nível",
                niveis,
                index=niveis.index(nivel_atual) if nivel_atual in niveis else 0,
            )
        with col8:
            carga_horaria_num = st.number_input(
                "Carga Horária (Apenas números)",
                min_value=1,
                value=_parse_carga_num(turma.get("carga_horaria")),
                step=1,
            )

        salvar = st.form_submit_button("💾 Salvar Alterações", type="primary", use_container_width=True)

        if salvar:
            if not titulo.strip():
                st.warning("⚠️ O título da turma é obrigatório.")
            elif not cursos_dict or not instrutores_dict or not cts_dict:
                st.warning("⚠️ Cursos, instrutores e CTs precisam estar cadastrados.")
            elif curso_selecionado not in cursos_dict or instrutor_selecionado not in instrutores_dict or ct_selecionado not in cts_dict:
                st.warning("⚠️ Selecione curso, instrutor e CT válidos.")
            else:
                try:
                    carga_final_str = (
                        f"{carga_horaria_num} Horas" if carga_horaria_num > 1 else "8 Hora"
                    )
                    payload = {
                        "titulo": titulo.strip(),
                        "modalidade": modalidade,
                        "nivel": nivel,
                        "carga_horaria": carga_final_str,
                        "data_treinamento": data_treinamento.isoformat(),
                        "curso_id": cursos_dict[curso_selecionado],
                        "instrutor_id": instrutores_dict[instrutor_selecionado],
                        "client_id": empresas_dict.get(empresa_selecionada),
                        "ct_id": cts_dict[ct_selecionado],
                    }
                    supabase.table("turmas").update(payload).eq("id", tid).execute()
                    st.success("✅ Turma atualizada com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Erro ao atualizar turma: {e}")
