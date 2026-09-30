import streamlit as st
from .data import fetch_responsaveis


def ui_selecionar_responsavel(tid: str, tipo_documento: str) -> dict:
    responsaveis = fetch_responsaveis()

    if not responsaveis:
        st.warning("⚠️ Nenhum responsável técnico ativo encontrado. Usando padrão.")
        return {
            "nome": "Cristiano Reis",
            "cpf": "214.135.358-01",
            "assinatura_url": None,
        }

    opcoes = {
        f"{r.get('nome', 'Sem Nome')} (CPF: {r.get('cpf', 'N/D')})": r
        for r in responsaveis
    }
    default_idx = next(
        (i for i, r in enumerate(responsaveis) if r.get("is_default")), 0
    )

    selecionado = st.selectbox(
        "Responsável Técnico Assinante",
        options=list(opcoes.keys()),
        index=default_idx,
        key=f"sel_resp_{tipo_documento}_{tid}",
    )
    return opcoes.get(selecionado, {})