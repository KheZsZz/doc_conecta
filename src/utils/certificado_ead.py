"""Geracao de certificado EAD (layout especifico + data inicio/termino)."""
from __future__ import annotations

import os
import re
import base64
from datetime import datetime
from typing import Any

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS

from src.utils.pdf_assets import (
    get_template,
    html_para_pdf,
    resolver_imagem,
)

from src.pages.private.turmas.helpers import extrair_cidade_do_endereco

_FUNDO_CONECTA = (
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


def _fmt_data_br(val) -> str:
    if not val:
        return ""
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "nat"):
        return ""
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
    """Ex.: Itu, 27 de Outubro de 2026 — cidade sempre do CT Conecta."""
    ct = ct or {}
    cidade = extrair_cidade_do_endereco(
        ct.get("full_address") or ct.get("endereco") or ct.get("address")
    )
    dt = _parse_data(data_ref)
    if not dt:
        return cidade
    return f"{cidade}, {dt.day} de {MESES_PT[dt.month]} de {dt.year}"


def endereco_ct(ct: dict | None) -> str:
    if not ct:
        return ""
    return (ct.get("full_address") or ct.get("endereco") or ct.get("address") or "").strip()


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


def normalizar_carga_horaria(carga) -> str:
    """Garante formato '08 Horas' a partir de '8', '08', '8h', '08 Horas', etc."""
    s = str(carga or "").strip()
    if not s or s.lower() in ("nan", "none"):
        return "08 Horas"
    m = re.search(r"(\d+)", s)
    if not m:
        return s
    n = int(m.group(1))
    return f"{n:02d} Horas"


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
    nivel: str = "Formação",
    ct: dict | None = None,
    data_documento=None,
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
    imagem_fundo = resolver_imagem(fundo) or resolver_imagem(_FUNDO_CONECTA) or _FUNDO_CONECTA
    logo_ct = resolver_imagem(ct.get("logo_url"))

    nome_aluno = (aluno.get("name") or aluno.get("nome") or "").strip().upper()
    cpf_aluno = _fmt_cpf(aluno.get("cpf") or "")
    rg_aluno = (aluno.get("rg") or "").strip()
    matricula_aluno = str(aluno.get("matricula") or "").strip()
    if matricula_aluno.lower() in ("nan", "none", ""):
        matricula_aluno = ""
    cpf_digitos = re.sub(r"\D", "", str(aluno.get("cpf") or ""))
    if not matricula_aluno and cpf_digitos and len(cpf_digitos) != 11:
        matricula_aluno = str(aluno.get("cpf") or cpf_digitos).strip()

    if matricula_aluno:
        rg_cpf = ""
        label_doc_aluno = "Matrícula"
        valor_doc_aluno = matricula_aluno
    else:
        rg_cpf = " / ".join([x for x in (rg_aluno, cpf_aluno) if x]) or cpf_aluno
        label_doc_aluno = "RG/CPF"
        valor_doc_aluno = rg_cpf

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

    carga = normalizar_carga_horaria(
        carga_horaria or curso.get("carga_horaria") or "08"
    )

    cidade_data = formatar_cidade_data_ead(
        data_documento if data_documento is not None else (data_termino or data_inicio),
        ct,
    )

    ass_img = resolver_imagem(
        assinante.get("assinatura")
        or assinante.get("assinatura_url")
        or ""
    )
    nome_ass = (assinante.get("nome") or assinante.get("name") or "").strip()
    cpf_ass = _fmt_cpf(assinante.get("cpf") or "")
    cpf_ass_raw = re.sub(r"\D", "", str(assinante.get("cpf") or ""))
    re_ass = (assinante.get("re") or "").strip()

    conteudo = _parse_conteudo(
        curso.get("conteudo_programatico") or curso.get("conteudo") or ""
    )
    titulo_conteudo = curso.get("name") or curso.get("sigla") or "Curso"
    if carga:
        titulo_conteudo = f"{titulo_conteudo} – {carga}"

    template = get_template(caminho_pasta_templates, nome_template)

    html = template.render(
        IMAGEM_FUNDO=imagem_fundo,
        LOGO_CT=logo_ct,
        NOME_ALUNO=nome_aluno,
        RG_CPF=rg_cpf,
        LABEL_DOC_ALUNO=label_doc_aluno,
        VALOR_DOC_ALUNO=valor_doc_aluno,
        MATRICULA=matricula_aluno,
        EMPRESA=empresa.get("name") or "",
        CNPJ=_fmt_cnpj(empresa.get("cnpj") or ""),
        ENDERECO=empresa.get("full_address") or "",
        DIZERES=dizeres,
        CARGA_HORARIA=carga,
        MODALIDADE=modalidade or "EAD",
        NIVEL=(nivel or "Formação").strip() or "Formação",
        DATA_INICIO=_fmt_data_br(data_inicio),
        DATA_TERMINO=_fmt_data_br(data_termino),
        CIDADE_DATA=cidade_data,
        ASSINATURA_IMG=ass_img,
        NOME_ASSINANTE=nome_ass,
        CARGO_ASSINANTE="Instrutor/Resp. Técnico",
        CARGO_ASSINANTE_2=assinante.get("cargo") or "Técnico em Segurança do Trabalho",
        CPF_ASSINANTE=cpf_ass_raw or cpf_ass,
        RE_ASSINANTE=re_ass,
        CONTEUDO_PROGRAMATICO=conteudo,
        CURSO_TITULO_CONTEUDO=titulo_conteudo,
    )

    return html_para_pdf(html, landscape=True)
