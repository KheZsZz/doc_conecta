from datetime import date, datetime, timedelta

import streamlit as st

from src.config.database import supabase
from src.pages.private.turmas.modals import (
    modal_adicionar_aluno,
    modal_editar_matriculas,
    modal_editar_turma,
    modal_emitir_documentacao,
)


def _fmt_data_br(data_str) -> str:
    if not data_str:
        return "—"
    s = str(data_str)[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return s


def _parse_iso(data_str):
    if not data_str:
        return None
    try:
        return datetime.strptime(str(data_str)[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def render_tab_listar():
    st.subheader("📋 Painel de Turmas e Emissão de Documentos")

    # ---- Filtros ----
    col1, col2 = st.columns(2)
    with col1:
        busca_turma = st.text_input(
            "🔍 Buscar (título ou empresa)", placeholder="Digite para filtrar..."
        )
    with col2:
        filtro_status = st.selectbox(
            "Status dos Documentos", ["Todos", "Pendentes", "Emitidos"]
        )

    col3, col4, col5 = st.columns(3)
    with col3:
        data_de = st.date_input(
            "Data treinamento (de)",
            value=None,
            format="DD/MM/YYYY",
            key="filtro_data_de",
        )
    with col4:
        data_ate = st.date_input(
            "Data treinamento (até)",
            value=None,
            format="DD/MM/YYYY",
            key="filtro_data_ate",
        )
    with col5:
        # Carrega instrutores para o filtro
        opcoes_instrutor = ["Todos"]
        mapa_instrutor: dict[str, str] = {}
        try:
            inst_res = (
                supabase.table("instrutores")
                .select("id, name")
                .order("name")
                .execute()
            )
            if inst_res and inst_res.data:
                for i in inst_res.data:
                    nome = i.get("name") or "Sem nome"
                    opcoes_instrutor.append(nome)
                    mapa_instrutor[nome] = i.get("id")
        except Exception:
            pass

        filtro_instrutor = st.selectbox("Instrutor", opcoes_instrutor)

    try:
        query = supabase.table("turmas").select(
            "id, titulo, modalidade, nivel, carga_horaria, data_treinamento, "
            "documento_emitido, created_at, instrutor_id, "
            "cursos(name), instrutores(id, name), clients(id, name), cts(id, name)"
        )

        if filtro_status == "Pendentes":
            query = query.eq("documento_emitido", False)
        elif filtro_status == "Emitidos":
            query = query.eq("documento_emitido", True)

        if filtro_instrutor != "Todos" and filtro_instrutor in mapa_instrutor:
            query = query.eq("instrutor_id", mapa_instrutor[filtro_instrutor])

        # Busca ampla; ordenação fina e filtros de data no Python
        # (Supabase order multi-coluna + nulls varia por versão)
        try:
            res_turmas = query.order("created_at", desc=True).execute()
        except Exception:
            res_turmas = query.order("data_treinamento", desc=True).execute()

        if not res_turmas or not res_turmas.data:
            st.info("Nenhuma turma encontrada.")
            return

        turmas_exibir = list(res_turmas.data)

        # Filtro por texto
        if busca_turma.strip():
            busca_lower = busca_turma.lower()
            turmas_exibir = [
                t
                for t in turmas_exibir
                if busca_lower in str(t.get("titulo", "")).lower()
                or busca_lower in str((t.get("clients") or {}).get("name", "")).lower()
                or busca_lower in str(t.get("id", "")).lower()
            ]

        # Filtro por intervalo de data do treinamento
        if data_de or data_ate:
            filtradas = []
            for t in turmas_exibir:
                d = _parse_iso(t.get("data_treinamento"))
                if d is None:
                    continue
                if data_de and d < data_de:
                    continue
                if data_ate and d > data_ate:
                    continue
                filtradas.append(t)
            turmas_exibir = filtradas

        # Ordenação:
        # 1) Pendentes (documento_emitido=False) no topo
        # 2) Dentro de cada grupo: ordem de inclusão (created_at) — mais recentes primeiro
        def _sort_key(t):
            pendente = 0 if not t.get("documento_emitido") else 1
            created = t.get("created_at") or ""
            data_t = str(t.get("data_treinamento") or "")
            # pendente primeiro; depois mais recente (string ISO ordena bem invertendo)
            return (pendente, created or data_t)

        turmas_exibir.sort(key=_sort_key, reverse=False)
        # Dentro do mesmo status, queremos created_at DESC:
        pendentes = [t for t in turmas_exibir if not t.get("documento_emitido")]
        emitidos = [t for t in turmas_exibir if t.get("documento_emitido")]

        def _mais_recente_primeiro(lista):
            return sorted(
                lista,
                key=lambda t: (t.get("created_at") or t.get("data_treinamento") or ""),
                reverse=True,
            )

        turmas_exibir = _mais_recente_primeiro(pendentes) + _mais_recente_primeiro(emitidos)

        if not turmas_exibir:
            st.info("Nenhuma turma encontrada com os filtros aplicados.")
            return

        st.caption(
            f"Exibindo **{len(turmas_exibir)}** turma(s) — "
            "pendentes de documento no topo; mais recentes primeiro."
        )

        for t in turmas_exibir:
            tid = t.get("id")
            titulo = t.get("titulo", "Turma Sem Título")
            data_trein = str(t.get("data_treinamento", ""))[:10]
            data_br = _fmt_data_br(data_trein)
            status_doc = t.get("documento_emitido", False)
            curso_nome = (t.get("cursos") or {}).get("name", "N/A")
            empresa_nome = (t.get("clients") or {}).get("name", "Sem Empresa Vinculada")
            empresa_id = (t.get("clients") or {}).get("id")
            ct_id = (t.get("cts") or {}).get("id")
            instrutor_nome = (t.get("instrutores") or {}).get("name", "N/A")

            icon_status = "✅" if status_doc else "⚠️"
            cor_status = "green" if status_doc else "orange"

            # Card FECHADO: só data + empresa
            label_expander = f"{icon_status} **{data_br}** · {empresa_nome}"

            with st.expander(label_expander):
                st.markdown(
                    f"""
**ID da Turma:** `{tid}`

**📝 Detalhes:**
* **Título:** {titulo}
* **Curso:** {curso_nome}
* **Instrutor:** {instrutor_nome}
* **Empresa:** {empresa_nome}
* **Data treinamento:** {data_br}
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
                    if st.button(
                        "✏️ Editar Turma", key=f"edt_turma_{tid}", use_container_width=True
                    ):
                        modal_editar_turma(tid)

                with col_btn2:
                    if st.button(
                        "➕ Adicionar Aluno", key=f"add_{tid}", use_container_width=True
                    ):
                        modal_adicionar_aluno(
                            tid, titulo, empresa_id, data_trein, t.get("carga_horaria")
                        )

                with col_btn3:
                    if st.button(
                        "👥 Ver / Editar Alunos", key=f"edit_{tid}", use_container_width=True
                    ):
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
