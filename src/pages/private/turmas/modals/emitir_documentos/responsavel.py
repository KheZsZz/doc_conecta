import streamlit as st
from .data import (
    fetch_responsaveis,
    fetch_responsaveis_do_curso,
    label_responsavel,
    dados_resp_de_registro,
    resolver_responsavel,
)


def ui_selecionar_responsavel(
    tid: str,
    tipo_documento: str,
    curso_id: str | None = None,
    responsavel_id_turma: str | None = None,
) -> dict:
    """Select de RT com pré-seleção: turma → vínculo do curso → is_default."""
    responsaveis = [r for r in fetch_responsaveis() if r.get("is_active", True)]

    if not responsaveis:
        st.warning("Nenhum responsável técnico ativo encontrado. Usando padrão.")
        return resolver_responsavel()

    # Preferidos do curso no topo da lista
    preferidos_ids: set[str] = set()
    if curso_id:
        for r in fetch_responsaveis_do_curso(curso_id):
            if r.get("id"):
                preferidos_ids.add(str(r["id"]))

    ordenados = sorted(
        responsaveis,
        key=lambda r: (
            0 if str(r.get("id")) in preferidos_ids else 1,
            (r.get("nome") or "").lower(),
        ),
    )

    opcoes: dict[str, dict] = {}
    for r in ordenados:
        lbl = label_responsavel(r)
        if str(r.get("id")) in preferidos_ids:
            lbl = f"★ {lbl}"
        opcoes[lbl] = r

    # índice padrão
    default_idx = 0
    if responsavel_id_turma:
        for i, r in enumerate(ordenados):
            if str(r.get("id")) == str(responsavel_id_turma):
                default_idx = i
                break
    elif preferidos_ids:
        for i, r in enumerate(ordenados):
            if str(r.get("id")) in preferidos_ids:
                default_idx = i
                break
    else:
        for i, r in enumerate(ordenados):
            if r.get("is_default"):
                default_idx = i
                break

    selecionado = st.selectbox(
        "Responsável Técnico Assinante",
        options=list(opcoes.keys()),
        index=default_idx,
        key=f"sel_resp_{tipo_documento}_{tid}",
        help=(
            "★ = vinculado ao curso desta turma. "
            "O padrão global só é usado se o curso não tiver RT vinculado."
        ),
    )
    return dados_resp_de_registro(opcoes.get(selecionado, {}))
