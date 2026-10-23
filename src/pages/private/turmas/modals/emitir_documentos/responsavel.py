"""UI e helpers para seleção do Responsável Técnico (RT) na emissão de docs."""
from __future__ import annotations

import streamlit as st

from .data import fetch_responsaveis


def _fmt_cpf_display(cpf: str | None) -> str:
    d = "".join(ch for ch in str(cpf or "") if ch.isdigit())
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    return (cpf or "").strip() or "N/D"


def ui_selecionar_responsavel(tid: str, key_prefix: str = "rt") -> dict:
    """
    Selectbox de Responsável Técnico.

    Retorna dict com: nome, cpf, re, assinatura_url, assinatura
    (chaves consumidas por gerar_carteirinhas_pdf / certificados).
    """
    responsaveis = fetch_responsaveis()

    if not responsaveis:
        st.warning(
            "⚠️ Nenhum responsável técnico cadastrado em "
            "**responsaveis_tecnicos**. Cadastre antes de emitir."
        )
        return {
            "nome": "",
            "cpf": "",
            "re": "",
            "assinatura_url": None,
            "assinatura": None,
        }

    default_idx = 0
    for i, r in enumerate(responsaveis):
        if r.get("is_default"):
            default_idx = i
            break

    labels: list[str] = []
    mapa: dict[str, dict] = {}
    for r in responsaveis:
        nome = (r.get("nome") or "Sem Nome").strip()
        cpf_fmt = _fmt_cpf_display(r.get("cpf"))
        re_val = (r.get("re") or "").strip()
        label = f"{nome} (CPF: {cpf_fmt}"
        if re_val:
            label += f" · RE: {re_val}"
        label += ")"
        # evita colisão de labels iguais
        if label in mapa:
            label = f"{label} [{r.get('id', len(labels))}]"
        labels.append(label)
        mapa[label] = r

    escolhido = st.selectbox(
        "Responsável Técnico (assinatura da carteirinha)",
        options=labels,
        index=min(default_idx, len(labels) - 1),
        key=f"sel_resp_{key_prefix}_{tid}",
        help="Nome completo, CPF e RE aparecem logo abaixo da assinatura no verso.",
    )

    raw = mapa.get(escolhido) or {}
    return {
        "nome": (raw.get("nome") or "").strip(),
        "cpf": (raw.get("cpf") or "").strip(),
        "re": (raw.get("re") or "").strip(),
        "assinatura_url": raw.get("assinatura_url") or raw.get("assinatura"),
        "assinatura": raw.get("assinatura") or raw.get("assinatura_url"),
        "id": raw.get("id"),
    }
