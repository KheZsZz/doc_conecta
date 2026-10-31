"""Assets compartilhados para geração de PDF (cache de imagens/templates)."""
from __future__ import annotations

import base64
import io
import os
from functools import lru_cache
from urllib.request import Request, urlopen

from jinja2 import Environment, FileSystemLoader
from weasyprint import CSS, HTML

_ENV_CACHE: dict[str, Environment] = {}
_TEMPLATE_CACHE: dict[tuple[str, str], object] = {}

CSS_LANDSCAPE = CSS(string="@page { size: A4 landscape; margin: 0; }")
CSS_PORTRAIT = CSS(string="@page { size: A4 portrait; margin: 0; }")

MAX_PDF_WORKERS = 3
# Limite para fundos/logos embutidos (carteirinha usa fundo em cada card)
_MAX_IMAGE_SIDE = 1400
_JPEG_QUALITY = 70


def get_template(caminho_pasta: str, nome: str):
    key = (os.path.abspath(caminho_pasta), nome)
    if key not in _TEMPLATE_CACHE:
        if caminho_pasta not in _ENV_CACHE:
            _ENV_CACHE[caminho_pasta] = Environment(
                loader=FileSystemLoader(caminho_pasta)
            )
        _TEMPLATE_CACHE[key] = _ENV_CACHE[caminho_pasta].get_template(nome)
    return _TEMPLATE_CACHE[key]


def _comprimir_bytes(data: bytes) -> tuple[bytes, str]:
    """Reduz resolução/qualidade de imagens grandes (menos HTML e WeasyPrint mais rápido)."""
    if not data or len(data) < 80_000:
        return data, ""
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(data))
        img.load()
        w, h = img.size
        if max(w, h) > _MAX_IMAGE_SIDE:
            img.thumbnail((_MAX_IMAGE_SIDE, _MAX_IMAGE_SIDE), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        if img.mode in ("RGBA", "LA") or (
            img.mode == "P" and "transparency" in img.info
        ):
            img = img.convert("RGBA")
            img.save(out, format="PNG", optimize=True)
            return out.getvalue(), "image/png"
        img = img.convert("RGB")
        img.save(out, format="JPEG", quality=_JPEG_QUALITY, optimize=True)
        return out.getvalue(), "image/jpeg"
    except Exception:
        return data, ""


@lru_cache(maxsize=128)
def url_para_data_uri(url: str) -> str:
    """Baixa imagem HTTP 1x, comprime se grande e cacheia como data-URI."""
    if not url or not str(url).startswith(("http://", "https://")):
        return url or ""
    try:
        req = Request(str(url), headers={"User-Agent": "doc-conecta/1.0"})
        with urlopen(req, timeout=15) as resp:
            data = resp.read()
            ctype = (resp.headers.get("Content-Type") or "image/png").split(";")[0].strip()
        if not ctype.startswith("image/"):
            ctype = "image/png"
        data2, ctype2 = _comprimir_bytes(data)
        if ctype2:
            ctype = ctype2
            data = data2
        return f"data:{ctype};base64,{base64.b64encode(data).decode()}"
    except Exception:
        return str(url)


def imagem_para_data_uri(caminho: str) -> str:
    ext = os.path.splitext(caminho)[1].lower().lstrip(".")
    mime = {
        "jpg": "jpeg",
        "jpeg": "jpeg",
        "png": "png",
        "gif": "gif",
        "webp": "webp",
    }.get(ext, "png")
    with open(caminho, "rb") as f:
        data = f.read()
    data2, ctype2 = _comprimir_bytes(data)
    if ctype2:
        mime = ctype2.split("/")[-1]
        data = data2
    return f"data:image/{mime};base64,{base64.b64encode(data).decode()}"


def resolver_imagem(caminho_ou_url: str | None) -> str:
    if not caminho_ou_url:
        return ""
    s = str(caminho_ou_url).strip()
    if s.startswith("data:"):
        return s
    if s.startswith(("http://", "https://")):
        return url_para_data_uri(s)
    if os.path.exists(s):
        try:
            return imagem_para_data_uri(s)
        except Exception:
            return ""
    return ""


def html_para_pdf(html_str: str, *, landscape: bool = True) -> bytes:
    css = CSS_LANDSCAPE if landscape else CSS_PORTRAIT
    return HTML(string=html_str).write_pdf(stylesheets=[css])
