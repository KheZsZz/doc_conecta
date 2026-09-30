import streamlit as st
from src.config.database import supabase
from src.pages.private.turmas.modals import (
    modal_adicionar_aluno,
    modal_editar_matriculas,
    modal_editar_turma,
    modal_emitir_documentacao,
)


def render_tab_listar():
    st.subheader("📋 Painel de Turmas e Emissão de Documentos")

    col_filtro1, col_filtro2 = st.columns(2)
    with col_filtro1:
        busca_turma = st.text_input(
            "🔍 Buscar turma (Nome ou Empresa)", placeholder="Digite para filtrar..."
        )
    with col_filtro2:
        filtro_status = st.selectbox("Status dos Documentos", ["Todos", "Pendentes", "Emitidos"])

    try:
        query = supabase.table("turmas").select(
            "id, titulo, modalidade, nivel, carga_horaria, data_treinamento, "
            "documento_emitido, cursos(name), instrutores(name), clients(id, name), cts(id, name)"
        )

        if filtro_status == "Pendentes":
            query = query.eq("documento_emitido", False)
        elif filtro_status == "Emitidos":
            query = query.eq("documento_emitido", True)

        res_turmas = query.order("data_treinamento", desc=True).execute()

        if not res_turmas or not res_turmas.data:
            st.info("Nenhuma turma encontrada.")
            return

        turmas_exibir = res_turmas.data

        if busca_turma.strip():
            busca_lower = busca_turma.lower()
            turmas_exibir = [
                t
                for t in turmas_exibir
                if busca_lower in str(t.get("titulo", "")).lower()
                or busca_lower in str((t.get("clients") or {}).get("name", "")).lower()
            ]

        for t in turmas_exibir:
            tid = t.get("id")
            titulo = t.get("titulo", "Turma Sem Título")
            data_trein = str(t.get("data_treinamento", ""))[:10]
            status_doc = t.get("documento_emitido", False)
            curso_nome = (t.get("cursos") or {}).get("name", "N/A")
            empresa_nome = (t.get("clients") or {}).get("name", "Sem Empresa Vinculada")
            empresa_id = (t.get("clients") or {}).get("id")
            ct_id = (t.get("cts") or {}).get("id")

            icon_status = "✅" if status_doc else "⚠️"
            cor_status = "green" if status_doc else "orange"

            label_expander = f"{icon_status} **{data_trein}** | {titulo} | {empresa_nome} | {curso_nome}"

            with st.expander(label_expander):
                st.markdown(
                    f"""
                    **📝 Detalhes da Turma:**
                    * **Curso:** {curso_nome}
                    * **Instrutor:** {(t.get('instrutores') or {}).get('name', 'N/A')}
                    * **Modalidade:** {t.get('modalidade')} | **Nível:** {t.get('nivel')} | **Carga:** {t.get('carga_horaria')}
                    * **Status de Emissão:** <span style="color:{cor_status}">{'Emitidos' if status_doc else 'Pendentes'}</span>
                    """,
                    unsafe_allow_html=True,
                )

                mat_count_res = (
                    supabase.table("matriculas")
                    .select("id", count="exact")
                    .eq("turma_id", tid)
                    .execute()
                )
                qtd_alunos = mat_count_res.count if mat_count_res else 0
                st.info(f"👥 **Alunos Matriculados:** {qtd_alunos}")

                col_btn1, col_btn2, col_btn3, col_btn4 = st.columns(4)

                with col_btn1:
                    if st.button("✏️ Editar Turma", key=f"edt_turma_{tid}", use_container_width=True):
                        modal_editar_turma(tid)

                with col_btn2:
                    if st.button("➕ Adicionar Aluno", key=f"add_{tid}", use_container_width=True):
                        modal_adicionar_aluno(
                            tid, titulo, empresa_id, data_trein, t.get("carga_horaria")
                        )

                with col_btn3:
                    if st.button("👥 Ver / Editar Alunos", key=f"edit_{tid}", use_container_width=True):
                        modal_editar_matriculas(tid, titulo)

                with col_btn4:
                    if st.button(
                        "📄 Gerar Documentos",
                        key=f"doc_{tid}",
                        type="primary",
                        use_container_width=True,
                    ):
                        modal_emitir_documentacao(tid, titulo, empresa_id, ct_id)

    except Exception as e:
        st.error(f"Erro ao carregar turmas: {e}")