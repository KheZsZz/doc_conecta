"""Geracao de certificado EAD (layout especifico + data inicio/termino)."""
from __future__ import annotations

import os
import re
import base64
from datetime import datetime
from functools import lru_cache
from urllib.request import Request, urlopen

from jinja2 import Environment, FileSystemLoader
from weasyprint import CSS, HTML

from src.utils.pdf_assets import get_template, html_para_pdf, resolver_imagem, rotulo_registro_profissional

_FUNDO_DEFAULT = (
    "https://vesgrrejcehseygchigh.supabase.co/storage/v1/object/public/logos/"
    "certificado_conecta_fundo.png"
)


def _fmt_cpf(cpf) -> str:
    d = re.sub(r"\D", "", str(cpf or ""))
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    return str(cpf or "").strip()


def _fmt_data(data_str) -> str:
    if not data_str:
        return ""
    s = str(data_str).strip()[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return s


def gerar_certificado_ead_pdf(
    *,
    aluno: dict,
    turma: dict | None = None,
    curso: dict | None = None,
    empresa: dict | None = None,
    assinante: dict | None = None,
    ct: dict | None = None,
    cidade_data: str = "",
    caminho_fundo: str | None = None,
    caminho_pasta_templates: str = "src/templates",
) -> bytes:
    turma = turma or {}
    curso = curso or {}
    empresa = empresa or {}
    assinante = assinante or {}
    ct = ct or {}

    template = get_template(caminho_pasta_templates, "template_certificado_ead.html")

    if caminho_fundo:
        fundo_path = caminho_fundo
    elif ct.get("fundo_certificado_url"):
        fundo_path = ct.get("fundo_certificado_url")
    else:
        fundo_path = _FUNDO_DEFAULT

    imagem_fundo = resolver_imagem(str(fundo_path)) or _FUNDO_DEFAULT

    assinatura_src = (
        assinante.get("assinatura")
        or assinante.get("assinatura_url")
        or assinante.get("signature_url")
        or ""
    )
    assinatura_resolvida = resolver_imagem(assinatura_src)

    nome_aluno = (aluno.get("name") or aluno.get("nome") or "").strip()
    cpf_aluno = _fmt_cpf(aluno.get("cpf"))
    rg_aluno = (aluno.get("rg") or "").strip()

    curso_nome = (
        curso.get("name")
        or turma.get("curso_nome")
        or aluno.get("curso_nome")
        or "Treinamento EAD"
    )
    carga = (
        (turma.get("carga_horaria") or aluno.get("carga_horaria") or "").strip()
        or "8 Horas"
    )
    nivel = (turma.get("nivel") or "").strip() or "Formação"
    modalidade = (turma.get("modalidade") or "EAD").strip() or "EAD"

    data_inicio = _fmt_data(
        aluno.get("data_inicio")
        or turma.get("data_inicio")
        or turma.get("data")
    )
    data_termino = _fmt_data(
        aluno.get("data_termino")
        or aluno.get("data_fim")
        or turma.get("data_termino")
        or turma.get("data")
    )

    nome_ass = (assinante.get("name") or assinante.get("nome") or "").strip()
    formacao_ass = (assinante.get("formacao") or assinante.get("cargo") or "").strip()
    cpf_ass = _fmt_cpf(assinante.get("cpf"))
    re_ass = (assinante.get("re") or "").strip()

    dizeres = turma.get("dizeres_certificado_ead") or turma.get("dizeres_certificado_aluno")
    if not dizeres:
        dizeres = (
            f"Certificamos que o aluno acima identificado concluiu com aproveitamento "
            f"o treinamento de \"{curso_nome}\" na modalidade EAD."
        )

    html_renderizado = template.render(
        IMAGEM_FUNDO=imagem_fundo,
        NOME_ALUNO=nome_aluno,
        CPF_ALUNO=cpf_aluno,
        RG_ALUNO=rg_aluno,
        EMPRESA=empresa.get("name") or "",
        CURSO_NOME=curso_nome,
        CARGA_HORARIA=carga,
        NIVEL=nivel,
        MODALIDADE=modalidade,
        DATA_INICIO=data_inicio,
        DATA_TERMINO=data_termino,
        CIDADE_DATA=cidade_data or "",
        DIZERES=dizeres,
        ASSINATURA_IMG=assinatura_resolvida,
        NOME_ASSINANTE=nome_ass,
        FORMACAO_ASSINANTE=formacao_ass,
        CPF_ASSINANTE=cpf_ass,
        RE_ASSINANTE=re_ass,
        LABEL_RE_ASSINANTE=rotulo_registro_profissional(formacao_ass),
        CONTEUDO_PROGRAMATICO=turma.get("conteudo_programatico") or curso.get("conteudo") or "",
    )

    return html_para_pdf(html_renderizado, landscape=True)
