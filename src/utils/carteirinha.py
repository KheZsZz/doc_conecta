"""Geracao de carteirinhas de alunos (4 por pagina A4)."""
from __future__ import annotations

import base64
import os
import re
from datetime import datetime, timedelta
from typing import Any

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS

URL_LOGO_CONECTA = (
    "https://vesgrrejcehseygchigh.supabase.co/storage/v1/object/public/logos/logo_conecta.png"
)

TEXTO_VERSO_BOMBEIRO = (
    "Este cartão só poderá ser utilizado para comprovar que o "
    "portador identificado possui o certificado de conclusão do curso "
    "de Bombeiro Civil. No Certificado consta que o curso foi realizado "
    "conforme Lei Estadual 15.180/13 e Portaria CCB-003/600/14 do "
    "Corpo de Bombeiros da PMESP e que o aluno foi aprovado. Só é "
    "válido com apresentação de um documento de identidade."
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


def _numero_cartao(aluno: dict, indice: int, base: int | None) -> str:
    """
    Número do cartão:
    1) campo explícito do aluno (numero_cartao / cartao_n)
    2) base + índice sequencial (se informado)
    3) últimos 5 dígitos do CPF + índice (estável por aluno)
    """
    explicit = (
        aluno.get("numero_cartao")
        or aluno.get("cartao_n")
        or aluno.get("cartao_numero")
        or ""
    )
    explicit = str(explicit).strip()
    if explicit and explicit.lower() not in ("nan", "none"):
        return explicit

    if base is not None:
        return str(base + indice)

    cpf = "".join(ch for ch in str(aluno.get("cpf") or "") if ch.isdigit())
    if len(cpf) >= 5:
        return cpf[-5:]
    return str(10000 + indice)


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
    nome_template: str | None = None,
    curso_sigla: str = "",
    numero_cartao_base: int | None = None,
    modelo: str | None = None,
) -> bytes:
    """
    Gera PDF com até 4 carteirinhas por página A4.

    modelo:
      - "padrao" → template_carteirinha.html
      - "bombeiro" → template_carteirinha_bombeiro.html
      - None → detecta pelo nome/sigla do curso
    """
    instrutor = instrutor or {}
    ct = ct or {}

    if modelo is None:
        modelo = (
            "bombeiro"
            if _eh_curso_bombeiro(curso_nome, curso_sigla)
            else "padrao"
        )

    if nome_template is None:
        nome_template = (
            "template_carteirinha_bombeiro.html"
            if modelo == "bombeiro"
            else "template_carteirinha.html"
        )

    fundo = caminho_fundo or ct.get("fundo_carteirinha_url") or ""
    imagem_fundo = _resolver_imagem(fundo)
    logo_ct = _resolver_imagem(ct.get("logo_url"))
    logo_conecta = _resolver_imagem(URL_LOGO_CONECTA)

    assinatura_inst = _resolver_imagem(
        instrutor.get("assinatura") or instrutor.get("assinatura_url")
    )
    nome_inst = instrutor.get("name") or instrutor.get("nome") or ""
    cpf_inst = _fmt_cpf(instrutor.get("cpf") or "")

    data_br = _fmt_data_br(data_conclusao)
    val_br = validade or _validade_padrao(data_conclusao)

    ct_nome = ct.get("full_name") or ct.get("name") or ""
    ct_cnpj = (ct.get("cnpj") or "").strip()
    escola_credenciada = "Escola credenciada"
    if ct_nome:
        escola_credenciada = f"Escola credenciada {ct_nome}"
    if ct_cnpj:
        escola_credenciada += f" CNPJ: {ct_cnpj}"

    cards: list[dict[str, Any]] = []
    for idx, a in enumerate(alunos):
        nome = (a.get("name") or a.get("nome") or "").strip().upper()
        if not nome:
            continue

        if modelo == "bombeiro":
            cards.append(
                {
                    "nome": nome,
                    "rg": (a.get("rg") or "").strip(),
                    "cpf": _fmt_cpf(a.get("cpf") or ""),
                    "validade": val_br,
                    "numero_cartao": _numero_cartao(a, idx, numero_cartao_base),
                    "titulo_curso": "BOMBEIRO PROFISSIONAL CIVIL",
                    "titulo_verso": "CENTRO DE FORMAÇÃO DE BOMBEIRO CIVIL",
                    "subtitulo_verso": "ETEPS Conecta",
                    "texto_verso": TEXTO_VERSO_BOMBEIRO,
                    "escola_credenciada": escola_credenciada,
                    "assinatura": assinatura_inst,
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
                    "assinatura_instrutor": assinatura_inst,
                }
            )

    if not cards:
        raise ValueError("Nenhum aluno para gerar carteirinha.")

    paginas: list[list[dict]] = []
    for i in range(0, len(cards), 4):
        paginas.append(cards[i : i + 4])

    env = Environment(loader=FileSystemLoader(caminho_pasta_templates))
    template = env.get_template(nome_template)
    html = template.render(
        paginas=paginas,
        IMAGEM_FUNDO=imagem_fundo,
        LOGO_CT=logo_ct,
        LOGO_CONECTA=logo_conecta,
        ESCOLA_LINHA="Escola Técnica de Especialização e Profissionalização em Segurança",
        TEXTO_VERSO=TEXTO_VERSO_BOMBEIRO,
        ESCOLA_CREDENCIADA=escola_credenciada,
    )

    return HTML(string=html).write_pdf(
        stylesheets=[CSS(string="@page { size: A4 portrait; margin: 6mm; }")]
    )
