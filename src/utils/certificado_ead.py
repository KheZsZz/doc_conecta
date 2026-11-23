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

from src.pages.private.turmas.helpers import extrair_cidade_do_endereco
from src.utils.pdf_assets import get_template, html_para_pdf, resolver_imagem, rotulo_registro_profissional

_FUNDO_DEFAULT = (
    "https://vesgrrejcehseygchigh.supabase.co/storage/v1/object/public/logos/"
    "certificado_conecta_fundo.png"
)

MESES_PT = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Março",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}


def _fmt_cpf(cpf) -> str:
    d = re.sub(r"\D", "", str(cpf or ""))
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    return str(cpf or "").strip()


def _fmt_data(data_str) -> str:
    if not data_str:
        return ""
    if hasattr(data_str, "strftime"):
        try:
            return data_str.strftime("%d/%m/%Y")
        except Exception:
            pass
    s = str(data_str).strip()
    if not s or s.lower() in ("nan", "none", "nat"):
        return ""
    s10 = s.split("T")[0][:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(
                s10 if fmt.startswith("%Y") else s[:10], fmt
            ).strftime("%d/%m/%Y")
        except Exception:
            continue
    return s[:10]


def _parse_data(val):
    if val is None:
        return None
    if hasattr(val, "year") and hasattr(val, "month") and hasattr(val, "day"):
        return val
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "nat"):
        return None
    s10 = s.split("T")[0][:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s10 if fmt.startswith("%Y") else s[:10], fmt)
        except Exception:
            continue
    return None


def formatar_cidade_data_ead(data_ref, ct: dict | None = None) -> str:
    """Ex.: Itu, 27 de Outubro de 2026."""
    ct = ct or {}
    cidade = extrair_cidade_do_endereco(
        ct.get("full_address") or ct.get("endereco") or ct.get("address")
    )
    dt = _parse_data(data_ref)
    if not dt:
        return cidade
    return f"{cidade}, {dt.day} de {MESES_PT[dt.month]} de {dt.year}"


def normalizar_carga_horaria(carga) -> str:
    s = str(carga or "").strip()
    if not s or s.lower() in ("nan", "none"):
        return "08 Horas"
    m = re.search(r"(\d+)", s)
    if not m:
        return s
    return f"{int(m.group(1)):02d} Horas"


def gerar_certificado_ead_pdf(
    *,
    aluno: dict,
    turma: dict | None = None,
    curso: dict | None = None,
    empresa: dict | None = None,
    assinante: dict | None = None,
    ct: dict | None = None,
    cidade_data: str = "",
    data_inicio=None,
    data_termino=None,
    carga_horaria: str = "",
    modalidade: str | None = None,
    nivel: str | None = None,
    data_documento=None,
    caminho_fundo: str | None = None,
    caminho_pasta_templates: str = "src/templates",
) -> bytes:
    turma = turma or {}
    curso = curso or {}
    empresa = empresa or {}
    assinante = assinante or {}
    ct = ct or {}
    aluno = aluno or {}

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
    carga = normalizar_carga_horaria(
        carga_horaria
        or turma.get("carga_horaria")
        or aluno.get("carga_horaria")
        or curso.get("carga_horaria")
        or "08"
    )
    nivel_txt = (nivel or turma.get("nivel") or "").strip() or "Formação"
    modalidade_txt = (modalidade or turma.get("modalidade") or "EAD").strip() or "EAD"

    data_inicio_txt = _fmt_data(
        data_inicio
        or aluno.get("data_inicio")
        or turma.get("data_inicio")
        or turma.get("data")
    )
    data_termino_txt = _fmt_data(
        data_termino
        or aluno.get("data_termino")
        or aluno.get("data_fim")
        or turma.get("data_termino")
        or turma.get("data")
    )

    nome_ass = (assinante.get("name") or assinante.get("nome") or "").strip()
    formacao_ass = (assinante.get("formacao") or assinante.get("cargo") or "").strip()
    cpf_ass = _fmt_cpf(assinante.get("cpf"))
    re_ass = (assinante.get("re") or "").strip()

    dizeres = (
        curso.get("dizeres_certificado_aluno")
        or curso.get("dizeres_certificado")
        or turma.get("dizeres_certificado_ead")
        or turma.get("dizeres_certificado_aluno")
    )
    if not dizeres:
        dizeres = (
            f"Certificamos que o aluno acima identificado concluiu com aproveitamento "
            f"o treinamento de \"{curso_nome}\" na modalidade EAD."
        )

    cidade = cidade_data
    if not cidade:
        cidade = formatar_cidade_data_ead(
            data_documento if data_documento is not None else (data_termino or data_inicio),
            ct,
        )

    html_renderizado = template.render(
        IMAGEM_FUNDO=imagem_fundo,
        NOME_ALUNO=nome_aluno,
        CPF_ALUNO=cpf_aluno,
        RG_ALUNO=rg_aluno,
        EMPRESA=empresa.get("name") or "",
        CURSO_NOME=curso_nome,
        CARGA_HORARIA=carga,
        NIVEL=nivel_txt,
        MODALIDADE=modalidade_txt,
        DATA_INICIO=data_inicio_txt,
        DATA_TERMINO=data_termino_txt,
        CIDADE_DATA=cidade or "",
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
