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

    # Filtro por CT só quando o usuário Consulta tem CT vinculado
    _ct_user = ct_id_atual() if is_consulta() else None
    if is_consulta() and _ct_user:
        st.caption("Exibindo apenas turmas do **seu CT**.")
    elif is_consulta() and not _ct_user:
        st.caption("Usuário sem CT vinculado — exibindo turmas de **todos os CTs**.")

    col1, col2 = st.columns(2)
    with col1:
        busca_turma = st.text_input(
            "🔍 Buscar (título ou empresa)", placeholder="Digite para filtrar..."
        )
    with col2:
        filtro_status = st.selectbox(
            "Status dos Documentos", ["Todos", "Pendentes", "Emitidos"]
        )

    try:
        # coluna correta em instrutores é "name" (não "nome")
        query = supabase.table("turmas").select(
            "*, clients(name), instrutores(name), cursos(name, sigla)"
        )
        # Admin / operacional / consulta sem CT → todas as turmas
        if _ct_user:
            query = query.eq("ct_id", _ct_user)

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

        if filtro_status == "Pendentes":
            turmas_exibir = [t for t in turmas_exibir if not t.get("documento_emitido")]
        elif filtro_status == "Emitidos":
            turmas_exibir = [t for t in turmas_exibir if t.get("documento_emitido")]

        if not turmas_exibir:
            st.info("Nenhuma turma encontrada com os filtros atuais.")
            return

        st.caption(f"{len(turmas_exibir)} turma(s)")

        for t in turmas_exibir:
            tid = t.get("id")
            titulo = t.get("titulo") or "Sem título"
            data_fmt = _fmt_data_br(t.get("data_treinamento"))
            emp = (t.get("clients") or {}).get("name") or "—"
            inst_obj = t.get("instrutores") or {}
            inst = inst_obj.get("name") or inst_obj.get("nome") or "—"
            curso = (t.get("cursos") or {}).get("name") or "—"
            emitido = bool(t.get("documento_emitido"))
            badge = "✅ Emitido" if emitido else "⚠️ Pendente"

            with st.container(border=True):
                c1, c2 = st.columns([3.5, 1.5])
                with c1:
                    st.markdown(f"**{titulo}** · {badge}")
                    st.caption(
                        f"📅 {data_fmt} · 🏢 {emp} · 📚 {curso} · 👨‍🏫 {inst}"
                    )
                with c2:
                    b1, b2 = st.columns(2)
                    with b1:
                        if st.button("📄 Docs", key=f"docs_{tid}", use_container_width=True):
                            modal_emitir_documentacao(t)
                    with b2:
                        if st.button("✏️", key=f"edit_{tid}", use_container_width=True):
                            modal_editar_turma(t)

                a1, a2, a3 = st.columns(3)
                with a1:
                    if st.button("➕ Aluno", key=f"add_{tid}", use_container_width=True):
                        modal_adicionar_aluno(tid)
                with a2:
                    if st.button("👥 Matrículas", key=f"mat_{tid}", use_container_width=True):
                        modal_editar_matriculas(tid)
                with a3:
                    if st.button("🗑️", key=f"del_{tid}", use_container_width=True):
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
