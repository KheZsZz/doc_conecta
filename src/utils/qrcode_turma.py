"""Geração do link público e do QR Code de cadastro de alunos por turma."""
from __future__ import annotations

from io import BytesIO

import streamlit as st

URL_PADRAO = "https://docfacil.streamlit.app"


def url_base_publica() -> str:
    try:
        url = st.secrets.get("PUBLIC_URL", "")  # type: ignore[attr-defined]
    except Exception:
        url = ""
    return (url or URL_PADRAO).rstrip("/")


def link_cadastro_turma(turma_id: str) -> str:
    return f"{url_base_publica()}/alunos?turma={turma_id}"


def qrcode_png(link: str, box_size: int = 12) -> bytes:
    import qrcode

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=3,
    )
    qr.add_data(link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0b1f3a", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
