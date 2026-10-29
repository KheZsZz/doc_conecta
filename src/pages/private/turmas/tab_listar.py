from datetime import datetime

import streamlit as st

from src.config.database import supabase
from src.auth.permissions import ct_id_atual, is_consulta
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


def _excluir_turma(tid: str) -> tuple[bool, str]:
    """Remove matrículas da turma e depois a turma."""
    try:
        supabase.table("matriculas").delete().eq("turma_id", tid).execute()
        supabase.table("turmas").delete().eq("id", tid).execute()
        return True, "Turma excluída com sucesso."
    except Exception as e:
        return False, str(e)


@st.dialog("🗑️ Excluir turma", width="small")
def modal_excluir_turma(tid: str, titulo: str, qtd_alunos: int):
    st.warning(
        f"Tem certeza que deseja excluir a turma **{titulo}**?\n\n"
        f"Isso remove também as **{qtd_alunos}** matrícula(s) vinculadas. "
        "Esta ação não pode ser desfeita."
    )
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Cancelar", use_container_width=True, key=f"cancel_del_{tid}"):
            st.rerun()
    with c2:
        if st.button(
            "Excluir definitivamente",
            type="primary",
            use_container_width=True,
            key=f"confirm_del_{tid}",
        ):
            ok, msg = _excluir_turma(tid)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(f"Erro ao excluir: {msg}")


def render_tab_listar():
    st.subheader("📋 Painel de Turmas e Emissão de Documentos")

    if is_consulta() and ct_id_atual():
        st.caption("Exibindo apenas turmas do **seu CT**.")

    col1, col2 = st.columns(2)
    with col1:
        busca_turma = st.text_input(
            "🔍 Buscar (título ou empresa)", placeholder="Digite para filtrar..."
        )
    with col2:
        filtro_status = st.selectbox(
            "Status dos Documentos", ["Todos", "Pendentes", "Emitidos"]
        )

    col_d1, col_d2, col_inst = st.columns(3)
    with col_d1:
        data_de = st.date_input(
            "Data treinamento (de)",
            value=None,
            format="DD/MM/YYYY",
            key="filtro_data_de",
        )
    with col_d2:
        data_ate = st.date_input(
            "Data treinamento (até)",
            value=None,
            format="DD/MM/YYYY",
            key="filtro_data_ate",
        )
    with col_inst:
        opcoes_instrutor = ["Todos"]
        mapa_instrutor: dict[str, str] = {}
        try:
            res_inst = (
                supabase.table("instrutores")
                .select("id, name")
                .order("name")
                .execute()
            )
            if res_inst and res_inst.data:
                for i in res_inst.data:
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

        # Consulta com CT vinculado: só turmas daquele CT; sem CT / admin / operacional: todos
        _ct_user = ct_id_atual() if is_consulta() else None
        if _ct_user:
            query = query.eq("ct_id", _ct_user)

        if filtro_status == "Pendentes":
            query = query.eq("documento_emitido", False)
        elif filtro_status == "Emitidos":
            query = query.eq("documento_emitido", True)

        if filtro_instrutor != "Todos" and filtro_instrutor in mapa_instrutor:
            query = query.eq("instrutor_id", mapa_instrutor[filtro_instrutor])

        try:
            res_turmas = query.order("created_at", desc=True).execute()
        except Exception:
            res_turmas = query.order("data_treinamento", desc=True).execute()

        if not res_turmas or not res_turmas.data:
            st.info("Nenhuma turma encontrada.")
            return

        turmas_exibir = list(res_turmas.data)

        if busca_turma.strip():
            busca_lower = busca_turma.lower()
            turmas_exibir = [
                t
                for t in turmas_exibir
                if busca_lower in str(t.get("titulo", "")).lower()
                or busca_lower in str((t.get("clients") or {}).get("name", "")).lower()
                or busca_lower in str(t.get("id", "")).lower()
            ]

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

        # Pendentes no topo; dentro de cada grupo, mais recentes primeiro
        pendentes = [t for t in turmas_exibir if not t.get("documento_emitido")]
        emitidos = [t for t in turmas_exibir if t.get("documento_emitido")]

        def _ord_recente(lista):
            return sorted(
                lista,
                key=lambda t: (t.get("created_at") or t.get("data_treinamento") or ""),
                reverse=True,
            )

        turmas_exibir = _ord_recente(pendentes) + _ord_recente(emitidos)

        if not turmas_exibir:
            st.info("Nenhuma turma encontrada com os filtros aplicados.")
            return

        st.caption(
            f"{len(turmas_exibir)} turma(s) · "
            "pendentes de documento no topo; mais recentes primeiro."
        )

        for t in turmas_exibir:
            tid = t.get("id")
            data_trein = str(t.get("data_treinamento", ""))[:10]
            data_br = _fmt_data_br(data_trein)
            status_doc = t.get("documento_emitido", False)
            curso_nome = (t.get("cursos") or {}).get("name", "N/A")
            empresa_nome = (t.get("clients") or {}).get("name", "Sem Empresa Vinculada")
            empresa_id = (t.get("clients") or {}).get("id")
            ct_id = (t.get("cts") or {}).get("id")
            instrutor_nome = (t.get("instrutores") or {}).get("name", "N/A")
            titulo = t.get("titulo") or "Sem título"
            icon_status = "✅" if status_doc else "⚠️"

            label_expander = f"{icon_status} **{data_br}** · {empresa_nome}"

            with st.expander(label_expander, expanded=False):
                st.markdown(
                    f"""
* **ID:** `{tid}`
* **Título:** {titulo}
* **Curso:** {curso_nome}
* **Instrutor:** {instrutor_nome}
* **Empresa:** {empresa_nome}
* **Data treinamento:** {data_br}
* **Modalidade:** {t.get('modalidade') or '—'}
* **Nível:** {t.get('nivel') or '—'}
* **Carga:** {t.get('carga_horaria') or '—'}
* **Documentos:** {'Emitidos' if status_doc else 'Pendentes'}
                    """
                )

                c1, c2, c3, c4, c5 = st.columns(5)
                with c1:
                    if st.button(
                        "📄 Documentos",
                        key=f"docs_{tid}",
                        use_container_width=True,
                    ):
                        modal_emitir_documentacao(t)
                with c2:
                    if st.button(
                        "✏️ Editar",
                        key=f"edit_{tid}",
                        use_container_width=True,
                    ):
                        modal_editar_turma(t)
                with c3:
                    if st.button(
                        "➕ Aluno",
                        key=f"add_{tid}",
                        use_container_width=True,
                    ):
                        modal_adicionar_aluno(tid)
                with c4:
                    if st.button(
                        "👥 Matrículas",
                        key=f"mat_{tid}",
                        use_container_width=True,
                    ):
                        modal_editar_matriculas(tid)
                with c5:
                    if st.button(
                        "🗑️ Excluir",
                        key=f"del_{tid}",
                        use_container_width=True,
                    ):
                        try:
                            r = (
                                supabase.table("matriculas")
                                .select("id", count="exact")
                                .eq("turma_id", tid)
                                .execute()
                            )
                            qtd = r.count if r and r.count is not None else 0
                        except Exception:
                            qtd = 0
                        modal_excluir_turma(tid, titulo, qtd)

    except Exception as e:
        st.error(f"Erro ao listar turmas: {e}")
