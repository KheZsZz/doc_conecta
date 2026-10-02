"""Geracao de certificado EAD (layout especifico + data inicio/termino)."""
from __future__ import annotations

import os
import re
import base64
from datetime import datetime
from typing import Any

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS

_FUNDO_CONECTA = (
    "https://vesgrrejcehseygchigh.supabase.co/storage/v1/object/public/logos/"
    "certificado_conecta_fundo.png"
)


def _imagem_para_data_uri(caminho: str) -> str:
    ext = os.path.splitext(caminho)[1].lower().lstrip(".")
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif", "webp": "webp"}.get(
        ext, "png"
    )
    with open(caminho, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:image/{mime};base64,{b64}"


def _resolver_imagem(caminho_ou_url: str | None) -> str:
    if not caminho_ou_url:
        return ""
    s = str(caminho_ou_url).strip()
    if s.startswith(("http://", "https://", "data:")):
        return s
    if os.path.exists(s):
        try:
            return _imagem_para_data_uri(s)
        except Exception:
            return ""
    return ""


def _fmt_data_br(val) -> str:
    if not val:
        return ""
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "nat"):
        return ""
    # excel serial sometimes comes as datetime already via pandas
    if hasattr(val, "strftime"):
        try:
            return val.strftime("%d/%m/%Y")
        except Exception:
            pass
    s10 = s.split("T")[0][:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s10 if fmt.startswith("%Y") else s[:10], fmt).strftime(
                "%d/%m/%Y"
            )
        except Exception:
            continue
    return s


def _fmt_cpf(cpf: str) -> str:
    d = re.sub(r"\D", "", str(cpf or ""))
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    return str(cpf or "").strip()


def _fmt_cnpj(cnpj: str) -> str:
    d = re.sub(r"\D", "", str(cnpj or ""))
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    return str(cnpj or "").strip()


def _parse_conteudo(raw) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    texto = str(raw).replace("\r\n", "\n").replace("\r", "\n")
    itens = []
    for linha in texto.split("\n"):
        l = linha.strip().lstrip("•*-–— ").strip()
        if l:
            itens.append(l)
    return itens


def gerar_certificado_ead_pdf(
    *,
    aluno: dict,
    empresa: dict,
    curso: dict,
    assinante: dict,
    data_inicio,
    data_termino,
    carga_horaria: str = "",
    modalidade: str = "EAD",
    ct: dict | None = None,
    caminho_fundo: str | None = None,
    caminho_pasta_templates: str = "src/templates",
    nome_template: str = "template_certificado_ead.html",
) -> bytes:
    """
    Gera um PDF de certificado EAD (1 pagina + conteudo programatico se houver).
    """
    ct = ct or {}
    empresa = empresa or {}
    curso = curso or {}
    assinante = assinante or {}
    aluno = aluno or {}

    fundo = (
        caminho_fundo
        or ct.get("fundo_certificado_url")
        or _FUNDO_CONECTA
    )
    imagem_fundo = _resolver_imagem(fundo) or _FUNDO_CONECTA
    logo_ct = _resolver_imagem(ct.get("logo_url"))

    nome_aluno = (aluno.get("name") or aluno.get("nome") or "").strip().upper()
    cpf_aluno = _fmt_cpf(aluno.get("cpf") or "")
    rg_aluno = (aluno.get("rg") or "").strip()
    rg_cpf = " / ".join([x for x in (rg_aluno, cpf_aluno) if x]) or cpf_aluno

    dizeres = (
        curso.get("dizeres_certificado_aluno")
        or curso.get("dizeres_certificado")
        or ""
    ).strip()
    if not dizeres:
        nome_curso = curso.get("name") or "Treinamento"
        normativa = curso.get("normativa") or ""
        dizeres = (
            f'Certificamos que o aluno acima identificado realizou o treinamento de '
            f'“{nome_curso}”'
        )
        if normativa:
            dizeres += f", de acordo com a {normativa}."
        else:
            dizeres += "."

    carga = (
        carga_horaria
        or curso.get("carga_horaria")
        or "8 h"
    )
    # normaliza "08 Horas" -> mantém o que veio
    carga = str(carga).strip()

    ass_img = _resolver_imagem(
        assinante.get("assinatura")
        or assinante.get("assinatura_url")
        or ""
    )
    nome_ass = (assinante.get("nome") or assinante.get("name") or "").strip()
    cpf_ass = _fmt_cpf(assinante.get("cpf") or "")
    # no modelo: CPF sem pontuacao junto do RE
    cpf_ass_raw = re.sub(r"\D", "", str(assinante.get("cpf") or ""))
    re_ass = (assinante.get("re") or "").strip()

    conteudo = _parse_conteudo(
        curso.get("conteudo_programatico") or curso.get("conteudo") or ""
    )
    titulo_conteudo = curso.get("name") or curso.get("sigla") or "Curso"
    if carga:
        titulo_conteudo = f"{titulo_conteudo} – {carga}"

    env = Environment(loader=FileSystemLoader(caminho_pasta_templates))
    template = env.get_template(nome_template)

    html = template.render(
        IMAGEM_FUNDO=imagem_fundo,
        LOGO_CT=logo_ct,
        NOME_ALUNO=nome_aluno,
        RG_CPF=rg_cpf,
        EMPRESA=empresa.get("name") or "",
        CNPJ=_fmt_cnpj(empresa.get("cnpj") or ""),
        ENDERECO=empresa.get("full_address") or "",
        DIZERES=dizeres,
        CARGA_HORARIA=carga,
        MODALIDADE=modalidade or "EAD",
        DATA_INICIO=_fmt_data_br(data_inicio),
        DATA_TERMINO=_fmt_data_br(data_termino),
        ASSINATURA_IMG=ass_img,
        NOME_ASSINANTE=nome_ass,
        CARGO_ASSINANTE="Instrutor/Resp. Técnico",
        CARGO_ASSINANTE_2=assinante.get("cargo") or "Técnico em Segurança do Trabalho",
        CPF_ASSINANTE=cpf_ass_raw or cpf_ass,
        RE_ASSINANTE=re_ass,
        CONTEUDO_PROGRAMATICO=conteudo,
        CURSO_TITULO_CONTEUDO=titulo_conteudo,
    )

    return HTML(string=html).write_pdf(
        stylesheets=[CSS(string="@page { size: A4 landscape; margin: 0; }")]
    )
