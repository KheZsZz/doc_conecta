"""Geracao de certificados de aluno (HTML/PDF/ZIP) com cache e paralelo."""
from __future__ import annotations

import base64
import io
import os
import re
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from functools import lru_cache
from urllib.request import Request, urlopen

from jinja2 import Environment, FileSystemLoader
from weasyprint import CSS, HTML
from src.utils.pdf_assets import comprimir_pdf, empresa_e_particular, rotulo_registro_profissional

_FUNDO_DEFAULT = (
    "https://vesgrrejcehseygchigh.supabase.co/storage/v1/object/public/logos/"
    "certificado_conecta_fundo.png"
)

_ENV_CACHE: dict[str, Environment] = {}
_TEMPLATE_CACHE: dict[tuple[str, str], object] = {}
_CSS_LANDSCAPE = CSS(string="@page { size: A4 landscape; margin: 0; }")
_MAX_WORKERS = 3


def _get_template(caminho_pasta: str, nome: str = "template_certificado.html"):
    key = (os.path.abspath(caminho_pasta), nome)
    if key not in _TEMPLATE_CACHE:
        if caminho_pasta not in _ENV_CACHE:
            _ENV_CACHE[caminho_pasta] = Environment(
                loader=FileSystemLoader(caminho_pasta)
            )
        _TEMPLATE_CACHE[key] = _ENV_CACHE[caminho_pasta].get_template(nome)
    return _TEMPLATE_CACHE[key]


@lru_cache(maxsize=64)
def _url_para_data_uri(url: str) -> str:
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


def _imagem_para_data_uri(caminho: str) -> str:
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


def _resolver_imagem(caminho_ou_url: str) -> str:
    if not caminho_ou_url:
        return ""
    caminho_ou_url = str(caminho_ou_url).strip()
    if caminho_ou_url.startswith("data:"):
        return caminho_ou_url
    if caminho_ou_url.startswith(("http://", "https://")):
        return _url_para_data_uri(caminho_ou_url)
    if os.path.exists(caminho_ou_url):
        try:
            return _imagem_para_data_uri(caminho_ou_url)
        except Exception:
            return ""
    return ""


def _endereco_ct(ct: dict | None, mostrar: bool) -> str:
    if not mostrar or not ct:
        return ""
    return (
        (ct.get("full_address") or ct.get("endereco") or ct.get("address") or "")
        .strip()
    )


def _slug_nome_arquivo(nome: str) -> str:
    s = (nome or "aluno").strip().upper()
    s = "".join(c if c.isalnum() or c in (" ", "-", "_") else "" for c in s)
    s = re.sub(r"\s+", "_", s.strip())
    s = re.sub(r"_+", "_", s)
    return s or "ALUNO"


def _carga_numerica(carga) -> str:
    m = re.search(r"\d+", str(carga or ""))
    if not m:
        return "8"
    return str(int(m.group(0)))


def _nome_pdf_certificado(aluno: dict, turma: dict) -> str:
    nome = _slug_nome_arquivo(aluno.get("name") or "aluno")
    sigla = (
        (turma.get("curso_sigla") or turma.get("sigla") or "")
        .strip()
        .upper()
        .replace(" ", "")
    )
    if not sigla:
        curso_nome = (turma.get("curso_nome") or "CURSO").strip()
        sigla = re.sub(r"[^A-Z0-9]", "", curso_nome.upper())[:8] or "CURSO"
    carga_n = _carga_numerica(turma.get("carga_horaria"))
    return f"{nome} - {sigla}_{carga_n}.pdf"


def _fmt_cpf(cpf) -> str:
    d = re.sub(r"\D", "", str(cpf or ""))
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    return str(cpf or "").strip()

def _fmt_cnpj(cnpj) -> str:
    d = re.sub(r"\D", "", str(cnpj or ""))
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    return str(cnpj or "").strip()


def _preparar_assets(
    turma: dict,
    instrutor: dict,
    empresa: dict | None,
    ct: dict | None,
    normativa: str,
    caminho_fundo: str | None,
) -> dict:
    ct = ct or {}
    empresa = empresa or {}
    instrutor = instrutor or {}
    turma = turma or {}

    if caminho_fundo:
        fundo_path = caminho_fundo
    elif ct.get("fundo_certificado_url"):
        fundo_path = ct.get("fundo_certificado_url")
    else:
        fundo_path = _FUNDO_DEFAULT

    imagem_fundo = _resolver_imagem(str(fundo_path)) or _FUNDO_DEFAULT
    if str(imagem_fundo).startswith("http"):
        imagem_fundo = _url_para_data_uri(str(imagem_fundo)) or imagem_fundo

    assinatura_instrutor = _resolver_imagem(
        instrutor.get("assinatura") or instrutor.get("assinatura_url") or ""
    )
    assinatura_resp_tecnico = _resolver_imagem(turma.get("assinatura_resp_url") or "")

    dizeres = turma.get("dizeres_certificado_aluno")
    if not dizeres:
        dizeres = (
            "Certificamos que o aluno acima identificado realizou o treinamento de "
            f"\"{turma.get('curso_nome', 'Treinamento')}\""
        )
        if normativa:
            dizeres += f", em conformidade com as exigências da {normativa}."
        else:
            dizeres += "."

    ocultar_empresa = empresa_e_particular(empresa)
    return {
        "imagem_fundo": imagem_fundo,
        "assinatura_instrutor": assinatura_instrutor,
        "assinatura_resp_tecnico": assinatura_resp_tecnico,
        "dizeres": dizeres,
        "endereco_ct": _endereco_ct(ct, bool(turma.get("mostrar_endereco_ct"))),
        "carga": (turma.get("carga_horaria") or "").strip() or "8 Horas",
        "modalidade": (turma.get("modalidade") or "").strip() or "Presencial",
        "nivel": (turma.get("nivel") or "").strip() or "Formação",
        "nome_instrutor": instrutor.get("name") or "",
        "formacao_instrutor": (instrutor.get("formacao") or "").strip(),
        "re_instrutor": (instrutor.get("re") or "").strip(),
        "cpf_instrutor": _fmt_cpf(instrutor.get("cpf") or ""),
        "resp_tecnico": turma.get("resp_tecnico") or "",
        "formacao_resp": (turma.get("formacao_resp_tecnico") or "").strip(),
        "re_resp": (turma.get("re_resp_tecnico") or "").strip(),
        "cpf_resp": _fmt_cpf(turma.get("cpf_resp_tecnico") or ""),
        "empresa_nome": "" if ocultar_empresa else (empresa.get("name") or ""),
        "endereco_empresa": "" if ocultar_empresa else (empresa.get("full_address") or ""),
        "curso_nome": turma.get("curso_nome") or "",
        "normativa": normativa or "",
        "label_re_resp": rotulo_registro_profissional((turma.get("formacao_resp_tecnico") or "").strip()),
        "label_re_instrutor": rotulo_registro_profissional((instrutor.get("formacao") or "").strip()),
    }
