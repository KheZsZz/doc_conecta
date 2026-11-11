"""Assets compartilhados para geração de PDF (cache de imagens/templates)."""
from __future__ import annotations

import base64
import io
import os
import shutil
import subprocess
import tempfile
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

# Compactação pós-WeasyPrint: não comprimir arquivos já pequenos
_MIN_BYTES_COMPRESS = 350_000
_GS_TIMEOUT_SEC = 120


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


def _ghostscript_bin() -> str | None:
    for name in ("gs", "gswin64c", "gswin32c"):
        path = shutil.which(name)
        if path:
            return path
    return None


def _comprimir_com_ghostscript(pdf_bytes: bytes, preset: str = "ebook") -> bytes | None:
    """Compacta via Ghostscript (melhor redução em PDFs com imagens)."""
    gs = _ghostscript_bin()
    if not gs or not pdf_bytes:
        return None
    preset = preset if preset in ("screen", "ebook", "printer", "prepress", "default") else "ebook"
    tmp_in = tmp_out = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f_in:
            f_in.write(pdf_bytes)
            tmp_in = f_in.name
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f_out:
            tmp_out = f_out.name
        cmd = [
            gs,
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.4",
            f"-dPDFSETTINGS=/{preset}",
            "-dDetectDuplicateImages=true",
            "-dCompressFonts=true",
            "-dNOPAUSE",
            "-dQUIET",
            "-dBATCH",
            f"-sOutputFile={tmp_out}",
            tmp_in,
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            timeout=_GS_TIMEOUT_SEC,
            check=False,
        )
        if proc.returncode != 0:
            return None
        with open(tmp_out, "rb") as f:
            out = f.read()
        if not out or out[:4] != b"%PDF":
            return None
        return out
    except Exception:
        return None
    finally:
        for p in (tmp_in, tmp_out):
            if p:
                try:
                    os.unlink(p)
                except Exception:
                    pass


def _comprimir_com_pikepdf(pdf_bytes: bytes) -> bytes | None:
    """Fallback: recomprime streams (sem reamostrar imagens como o GS)."""
    try:
        import pikepdf
    except Exception:
        return None
    try:
        src = io.BytesIO(pdf_bytes)
        dst = io.BytesIO()
        with pikepdf.open(src) as pdf:
            pdf.save(
                dst,
                compress_streams=True,
                object_stream_mode=pikepdf.ObjectStreamMode.generate,
                recompress_flate=True,
                normalize_content=False,
            )
        out = dst.getvalue()
        if not out or out[:4] != b"%PDF":
            return None
        return out
    except Exception:
        return None


def comprimir_pdf(pdf_bytes: bytes, *, preset: str = "ebook") -> bytes:
    """Compacta PDF gerado (Ghostscript preferencial; fallback pikepdf).

    Se a saída não for menor, devolve o original.
    """
    if not pdf_bytes or len(pdf_bytes) < _MIN_BYTES_COMPRESS:
        return pdf_bytes

    original_len = len(pdf_bytes)
    candidatos: list[bytes] = []

    gs_out = _comprimir_com_ghostscript(pdf_bytes, preset=preset)
    if gs_out:
        candidatos.append(gs_out)

    pk_out = _comprimir_com_pikepdf(pdf_bytes)
    if pk_out:
        candidatos.append(pk_out)

    if not candidatos:
        return pdf_bytes

    melhor = min(candidatos, key=len)
    # só troca se realmente encolher (margem de 2%)
    if len(melhor) < int(original_len * 0.98):
        return melhor
    return pdf_bytes


def html_para_pdf(html_str: str, *, landscape: bool = True) -> bytes:
    css = CSS_LANDSCAPE if landscape else CSS_PORTRAIT
    pdf = HTML(string=html_str).write_pdf(stylesheets=[css])
    return comprimir_pdf(pdf)
