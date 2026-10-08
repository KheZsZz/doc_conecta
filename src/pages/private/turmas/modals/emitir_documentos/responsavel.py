import streamlit as st
from .data import fetch_responsaveis


def ui_selecionar_responsavel(tid: str, tipo_documento: str) -> dict:
    responsaveis = fetch_responsaveis()

    if not responsaveis:
        st.warning("⚠️ Nenhum responsável técnico ativo encontrado. Usando padrão.")
        return {
            "nome": "Cristiano Reis",
            "cpf": "214.135.358-01",
            "re": "0075191",
            "assinatura_url": None,
        }

    opcoes = {}
    for r in responsaveis:
        re_val = (r.get("re") or "").strip()
        label = f"{r.get('nome', 'Sem Nome')} (CPF: {r.get('cpf', 'N/D')}"
        if re_val:
            label += f" | RE: {re_val}"
        label += ")"
        opcoes[label] = r

    default_idx = next(
        (i for i, r in enumerate(responsaveis) if r.get("is_default")), 0
    )

    selecionado = st.selectbox(
        "Responsável Técnico Assinante",
        options=list(opcoes.keys()),
        index=default_idx,
        key=f"sel_resp_{tipo_documento}_{tid}",
    )
    r = opcoes.get(selecionado, {})
    return {
        "nome": r.get("nome") or "",
        "cpf": r.get("cpf") or "",
        "re": (r.get("re") or "").strip(),
        "assinatura_url": r.get("assinatura_url"),
    }
