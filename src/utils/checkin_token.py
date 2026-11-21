"""Tokens HMAC de check-in por turma (link público com validade)."""
from __future__ import annotations

import hashlib
import hmac
import time
from urllib.parse import quote


def _secret() -> str:
    try:
        import streamlit as st

        s = (
            st.secrets.get("CHECKIN_SECRET")
            or st.secrets.get("AUTH_PEPPER")
            or ""
        )
        if s:
            return str(s)
    except Exception:
        pass
    # fallback apenas para não quebrar dev local — em produção defina CHECKIN_SECRET
    return "doc_conecta_checkin_dev_only"


def gerar_token(turma_id: str, horas_validade: int = 48) -> str:
    tid = str(turma_id).strip()
    exp = int(time.time()) + max(1, int(horas_validade)) * 3600
    payload = f"{tid}.{exp}"
    sig = hmac.new(
        _secret().encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:32]
    return f"{payload}.{sig}"


def validar_token(token: str | None) -> tuple[str | None, str | None]:
    """Retorna (turma_id, erro)."""
    if not token or not str(token).strip():
        return None, "Link de check-in inválido ou ausente."
    partes = str(token).strip().split(".")
    if len(partes) != 3:
        return None, "Token de check-in malformado."
    tid, exp_s, sig = partes
    try:
        exp = int(exp_s)
    except ValueError:
        return None, "Token de check-in inválido."
    if exp < int(time.time()):
        return None, "Este link de check-in expirou. Solicite um novo ao instrutor."
    payload = f"{tid}.{exp}"
    esperado = hmac.new(
        _secret().encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:32]
    if not hmac.compare_digest(esperado, sig):
        return None, "Token de check-in inválido."
    return tid, None


def montar_url_checkin(base_url: str, token: str) -> str:
    base = (base_url or "").rstrip("/")
    return f"{base}/?page=checkin&t={quote(token, safe='')}"
