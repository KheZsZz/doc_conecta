"""Geracao de carteirinhas de alunos (4 por pagina A4)."""
from __future__ import annotations

import base64
import os
from datetime import datetime, timedelta
from typing import Any

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS


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
    s = str(val).split("T")[0][:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return s


def _fmt_cpf(cpf: str) -> str:
    d = "".join(ch for ch in str(cpf or "") if ch.isdigit())
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
    """Validade = conclusao + N anos (padrao 1)."""
    s = str(data_conclusao or "").split("T")[0][:10]
    try:
        dt = datetime.strptime(s, "%Y-%m-%d")
        return (dt + timedelta(days=365 * anos)).strftime("%d/%m/%Y")
    except Exception:
        return ""


def gerar_carteirinhas_pdf(
    alunos: list[dict],
    curso_nome: str,
    carga_horaria: str,
    data_conclusao: str,
    instrutor: dict | None = None,
    ct: dict | None = None,
    validade: str | None = None,
    caminho_fundo: str | None = None,
    caminho_pasta_templates: str = "src/templates",
    nome_template: str = "template_carteirinha.html",
) -> bytes:
    """
    Gera PDF com ate 4 carteirinhas por pagina A4.

    cada aluno: name/nome, cpf, rg (opcionais)
    fundo: caminho_fundo > ct.fundo_carteirinha_url > vazio
    """
    instrutor = instrutor or {}
    ct = ct or {}

    fundo = (
        caminho_fundo
        or ct.get("fundo_carteirinha_url")
        or ""
    )
    imagem_fundo = _resolver_imagem(fundo)
    logo_ct = _resolver_imagem(ct.get("logo_url"))

    assinatura_inst = _resolver_imagem(
        instrutor.get("assinatura") or instrutor.get("assinatura_url")
    )
    nome_inst = instrutor.get("name") or instrutor.get("nome") or ""
    cpf_inst = _fmt_cpf(instrutor.get("cpf") or "")

    data_br = _fmt_data_br(data_conclusao)
    val_br = validade or _validade_padrao(data_conclusao)

    cards: list[dict[str, Any]] = []
    for a in alunos:
        nome = (a.get("name") or a.get("nome") or "").strip().upper()
        if not nome:
            continue
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
                "assinatura_instrutor": assinatura_inst,
            }
        )

    if not cards:
        raise ValueError("Nenhum aluno para gerar carteirinha.")

    # 4 cards por pagina
    paginas: list[list[dict]] = []
    for i in range(0, len(cards), 4):
        paginas.append(cards[i : i + 4])

    env = Environment(loader=FileSystemLoader(caminho_pasta_templates))
    template = env.get_template(nome_template)
    html = template.render(
        paginas=paginas,
        IMAGEM_FUNDO=imagem_fundo,
        LOGO_CT=logo_ct,
    )

    return HTML(string=html).write_pdf(
        stylesheets=[CSS(string="@page { size: A4 portrait; margin: 8mm; }")]
    )
