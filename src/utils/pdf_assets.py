"""Assets compartilhados para geração de PDF (cache de imagens/templates)."""
from __future__ import annotations

import base64
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


def get_template(caminho_pasta: str, nome: str):
    key = (os.path.abspath(caminho_pasta), nome)
    if key not in _TEMPLATE_CACHE:
        if caminho_pasta not in _ENV_CACHE:
            _ENV_CACHE[caminho_pasta] = Environment(
                loader=FileSystemLoader(caminho_pasta)
            )
        _TEMPLATE_CACHE[key] = _ENV_CACHE[caminho_pasta].get_template(nome)
    return _TEMPLATE_CACHE[key]


@lru_cache(maxsize=128)
def url_para_data_uri(url: str) -> str:
    """Baixa imagem HTTP 1x e cacheia como data-URI."""
    if not url or not str(url).startswith(("http://", "https://")):
        return url or ""
    try:
        req = Request(str(url), headers={"User-Agent": "doc-conecta/1.0"})
        with urlopen(req, timeout=20) as resp:
            data = resp.read()
            ctype = (resp.headers.get("Content-Type") or "image/png").split(";")[0].strip()
        if not ctype.startswith("image/"):
            ctype = "image/png"
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
        b64 = base64.b64encode(f.read()).decode()
    return f"data:image/{mime};base64,{b64}"


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
