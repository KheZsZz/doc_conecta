"""Geracao de carteirinhas de alunos (4 por pagina A4)."""
from __future__ import annotations

import base64
import os
import re
from datetime import datetime, timedelta
from typing import Any

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS

from src.utils.pdf_assets import get_template, html_para_pdf, resolver_imagem

URL_LOGO_CONECTA = (
    "https://vesgrrejcehseygchigh.supabase.co/storage/v1/object/public/logos/logo_conecta_dourado_sem_fundo.png"
)

TEXTO_VERSO_BOMBEIRO = (
    "Este cartão só poderá ser utilizado para comprovar que o "
    "portador identificado possui o certificado de conclusão do curso "
    "de Bombeiro Civil. No Certificado consta que o curso foi realizado "
    "conforme Lei Estadual 15.180/13 e Portaria CCB-003/600/14 do "
    "Corpo de Bombeiros da PMESP e que o aluno foi aprovado. Só é "
    "válido com apresentação de um documento de identidade."
)


def _fmt_data_br(val) -> str:
    if not val:
        return ""
    s = str(val).split("T")[0][:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return s


def _fmt_cpf(cpf: str) -> str:
    d = "".join(ch for ch in str(cpf or "") if ch.isdigit())
    if len(d) < 11:
        d = d.zfill(11) if d else ""
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    return cpf or ""


def _documento_aluno(aluno: dict) -> str:
    rg = (aluno.get("rg") or "").strip()
    cpf = "".join(ch for ch in str(aluno.get("cpf") or "") if ch.isdigit())
    if rg and cpf:
        return f"{rg} / {cpf}"
    if cpf:
        return cpf
    return rg


def _validade_padrao(data_conclusao: str, anos: int = 1) -> str:
    s = str(data_conclusao or "").split("T")[0][:10]
    try:
        dt = datetime.strptime(s, "%Y-%m-%d")
        return (dt + timedelta(days=365 * anos)).strftime("%d/%m/%Y")
    except Exception:
        return ""


def _eh_curso_bombeiro(curso_nome: str, curso_sigla: str = "") -> bool:
    t = f"{curso_nome or ''} {curso_sigla or ''}".lower()
    t = re.sub(r"\s+", " ", t)
    return any(
        k in t
        for k in (
            "bombeiro",
            "bombeiros",
            "bc civil",
            "bombeiro civil",
            "bombeiro profissional",
        )
    ) or (curso_sigla or "").strip().upper() in ("BC", "BPC", "BPCIVIL")


def _eh_reciclagem(nivel: str = "", curso_nome: str = "") -> bool:
    t = f"{nivel or ''} {curso_nome or ''}".lower()
    return "recicl" in t


def _numero_cartao(
    aluno: dict,
    idx: int,
    numero_cartao_base: str = "",
    gerar_se_vazio: bool = True,
) -> str:
    re_existente = (aluno.get("re") or "").strip()
    if re_existente:
        return re_existente
    if not gerar_se_vazio:
        return ""
    base = (numero_cartao_base or "").strip()
    if base:
        return f"{base}{idx:04d}"
    return f"RE{idx:06d}"


def gerar_carteirinhas_pdf(
    *,
    alunos: list[dict],
    turma: dict | None = None,
    curso: dict | None = None,
    instrutor: dict | None = None,
    responsavel: dict | None = None,
    ct: dict | None = None,
    data_conclusao: str = "",
    carga_horaria: str = "",
    caminho_fundo: str | None = None,
    numero_cartao_base: str = "",
    gerar_re: bool = True,
    caminho_pasta_templates: str = "src/templates",
    nome_template: str = "template_carteirinha.html",
) -> tuple[bytes, list[dict]]:
    turma = turma or {}
    curso = curso or {}
    instrutor = instrutor or {}
    responsavel = responsavel or {}
    ct = ct or {}

    curso_nome = curso.get("name") or turma.get("curso_nome") or ""
    curso_sigla = curso.get("sigla") or turma.get("curso_sigla") or ""
    nivel = turma.get("nivel") or ""
    bombeiro = _eh_curso_bombeiro(curso_nome, curso_sigla)

    fundo = caminho_fundo or ct.get("fundo_carteirinha_url") or ""
    imagem_fundo = resolver_imagem(fundo)
    logo_ct = resolver_imagem(ct.get("logo_url"))
    logo_conecta = resolver_imagem(URL_LOGO_CONECTA)

    assinatura_src = (
        responsavel.get("assinatura_url")
        or responsavel.get("assinatura")
        or instrutor.get("assinatura")
        or instrutor.get("assinatura_url")
        or ""
    )
    assinatura_img = resolver_imagem(assinatura_src)

    data_br = _fmt_data_br(data_conclusao or turma.get("data_treinamento"))
    val_br = _validade_padrao(data_conclusao or turma.get("data_treinamento") or "")

    nome_inst = (instrutor.get("name") or instrutor.get("nome") or "").strip()
    cpf_inst = _fmt_cpf(instrutor.get("cpf") or "")
    rt_nome = (responsavel.get("nome") or responsavel.get("name") or nome_inst).strip()
    rt_cpf = _fmt_cpf(responsavel.get("cpf") or instrutor.get("cpf") or "")
    rt_re = (responsavel.get("re") or instrutor.get("re") or "").strip()

    escola_credenciada = (ct.get("name") or ct.get("full_name") or "ETEPS Conecta").strip()

    cards: list[dict] = []
    alunos_com_re: list[dict] = []

    for idx, a in enumerate(alunos or [], start=1):
        nome = (a.get("name") or a.get("nome") or "").strip().upper()
        if not nome:
            continue

        if bombeiro:
            re_val = _numero_cartao(
                a, idx, numero_cartao_base, gerar_se_vazio=gerar_re
            )
            cards.append(
                {
                    "nome": nome,
                    "rg": (a.get("rg") or "").strip(),
                    "cpf": _fmt_cpf(a.get("cpf") or ""),
                    "validade": val_br,
                    "numero_cartao": re_val,
                    "titulo_curso": "BOMBEIRO PROFISSIONAL CIVIL",
                    "titulo_verso": "CENTRO DE FORMAÇÃO DE BOMBEIRO CIVIL",
                    "subtitulo_verso": "ETEPS Conecta",
                    "texto_verso": TEXTO_VERSO_BOMBEIRO,
                    "escola_credenciada": escola_credenciada,
                    "assinatura": assinatura_img,
                    "rt_nome": rt_nome,
                    "rt_cpf": rt_cpf,
                    "rt_re": rt_re,
                }
            )
            alunos_com_re.append(
                {
                    "aluno_id": a.get("aluno_id") or a.get("id") or "",
                    "cpf": "".join(ch for ch in str(a.get("cpf") or "") if ch.isdigit()),
                    "re": re_val,
                    "gerado": gerar_re and not (a.get("re") or "").strip(),
                }
            )
        else:
            cards.append(
                {
                    "nome": nome,
                    "documento": _documento_aluno(a),
                    "data_conclusao": data_br,
                    "validade": val_br,
                    "curso_nome": curso_nome or "Treinamento",
                    "carga_horaria": carga_horaria or "8 Horas",
                    "nome_instrutor": nome_inst,
                    "cpf_instrutor": cpf_inst,
                    "assinatura_instrutor": assinatura_img,
                }
            )

    if not cards:
        raise ValueError("Nenhum aluno para gerar carteirinha.")

    paginas: list[list[dict]] = []
    for i in range(0, len(cards), 4):
        paginas.append(cards[i : i + 4])

    template = get_template(caminho_pasta_templates, nome_template)
    html = template.render(
        paginas=paginas,
        IMAGEM_FUNDO=imagem_fundo,
        LOGO_CT=logo_ct,
        LOGO_CONECTA=logo_conecta,
        ESCOLA_LINHA="Escola Técnica de Especialização e Profissionalização em Segurança",
        TEXTO_VERSO=TEXTO_VERSO_BOMBEIRO,
        ESCOLA_CREDENCIADA=escola_credenciada,
    )

    pdf = html_para_pdf(html, landscape=True)
    return pdf, alunos_com_re
