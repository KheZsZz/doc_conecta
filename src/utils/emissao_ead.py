"""Leitura e normalizacao da planilha de emissao EAD."""
from __future__ import annotations

import io
import re
import unicodedata
from typing import Any

import pandas as pd

from src.config.database import supabase

COLUNAS_OBRIGATORIAS = [
    "CNPJ",
    "Nome",
    "CPF",
    "SIGLA CURSO",
    "Data de Inicio",
    "Data de Finalização",
]


def normalizar_nome(nome: str) -> str:
    nome = str(nome or "").strip()
    nome = unicodedata.normalize("NFKD", nome).encode("ASCII", "ignore").decode()
    nome = re.sub(r"[^A-Z0-9 ]", "", nome.upper()).strip()
    nome = re.sub(r"\s+", " ", nome)
    return nome


def normalizar_cpf(cpf: str) -> str:
    d = re.sub(r"\D", "", str(cpf or ""))
    return d.zfill(11) if d else ""


def normalizar_cnpj(cnpj: str) -> str:
    return re.sub(r"\D", "", str(cnpj or ""))


def normalizar_sigla(sigla: str) -> str:
    s = str(sigla or "").strip().upper()
    s = re.sub(r"[^A-Z0-9]", "", s)
    return s


def _pick_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    mapa = {str(c).strip().lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in mapa:
            return mapa[cand.lower()]
    return None


def ler_planilha_ead(arquivo_bytes: bytes) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Retorna (linhas_ok, erros).
    Cada linha: nome, email, cpf, cnpj, sigla, carga, progresso, data_inicio, data_fim
    """
    df = pd.read_excel(io.BytesIO(arquivo_bytes))
    df.columns = [str(c).strip() for c in df.columns]

    col_cnpj = _pick_col(df, ["CNPJ", "cnpj"])
    col_nome = _pick_col(df, ["Nome", "NOME", "name"])
    col_email = _pick_col(df, ["E-mail", "Email", "email"])
    col_cpf = _pick_col(df, ["CPF", "cpf"])
    col_sigla = _pick_col(df, ["SIGLA CURSO", "SIGLA", "Sigla", "sigla"])
    col_carga = _pick_col(df, ["CARGA", "Carga", "carga", "Carga Horaria", "CARGA HORARIA"])
    col_prog = _pick_col(df, ["Progresso", "progresso", "PROGRESSO"])
    col_ini = _pick_col(df, ["Data de Inicio", "Data de Início", "DATA INICIO", "Inicio"])
    col_fim = _pick_col(
        df,
        [
            "Data de Finalização",
            "Data de Finalizacao",
            "Data Finalização",
            "DATA FIM",
            "Termino",
        ],
    )

    faltando = []
    for label, col in [
        ("CNPJ", col_cnpj),
        ("Nome", col_nome),
        ("CPF", col_cpf),
        ("SIGLA CURSO", col_sigla),
        ("Data de Inicio", col_ini),
        ("Data de Finalização", col_fim),
    ]:
        if not col:
            faltando.append(label)
    if faltando:
        return [], [f"Colunas obrigatórias ausentes: {', '.join(faltando)}"]

    linhas: list[dict[str, Any]] = []
    erros: list[str] = []

    for idx, row in df.iterrows():
        nlinha = int(idx) + 2  # header + 1
        nome = normalizar_nome(row.get(col_nome))
        cpf = normalizar_cpf(row.get(col_cpf))
        cnpj = normalizar_cnpj(row.get(col_cnpj))
        sigla = normalizar_sigla(row.get(col_sigla))

        if not nome and not cpf:
            continue

        prog = 1.0
        if col_prog is not None:
            try:
                prog = float(row.get(col_prog))
            except Exception:
                prog = 0.0

        if prog < 0.96:
            erros.append(
                f"Linha {nlinha} ({nome or cpf}): progresso {prog} < 0.96 — ignorada."
            )
            continue

        if not nome or not cpf or not cnpj or not sigla:
            erros.append(
                f"Linha {nlinha}: dados incompletos (nome/cpf/cnpj/sigla)."
            )
            continue

        if len(cpf) != 11:
            erros.append(f"Linha {nlinha} ({nome}): CPF inválido.")
            continue

        carga = ""
        if col_carga is not None and pd.notna(row.get(col_carga)):
            carga = str(row.get(col_carga)).strip()

        email = ""
        if col_email is not None and pd.notna(row.get(col_email)):
            email = str(row.get(col_email)).strip()

        linhas.append(
            {
                "linha": nlinha,
                "nome": nome,
                "email": email,
                "cpf": cpf,
                "cnpj": cnpj,
                "sigla": sigla,
                "carga": carga,
                "progresso": prog,
                "data_inicio": row.get(col_ini),
                "data_fim": row.get(col_fim),
            }
        )

    return linhas, erros


def buscar_empresa_por_cnpj(cnpj: str) -> dict | None:
    digitos = normalizar_cnpj(cnpj)
    if not digitos:
        return None
    try:
        res = supabase.table("clients").select("*").execute()
        rows = res.data if res and isinstance(res.data, list) else []
        for r in rows:
            if normalizar_cnpj(r.get("cnpj")) == digitos:
                return r
    except Exception:
        return None
    return None


def buscar_curso_por_sigla(sigla: str) -> dict | None:
    s = normalizar_sigla(sigla)
    if not s:
        return None
    try:
        res = supabase.table("cursos").select("*").execute()
        rows = res.data if res and isinstance(res.data, list) else []
        for r in rows:
            if normalizar_sigla(r.get("sigla")) == s:
                return r
    except Exception:
        return None
    return None


def buscar_ct_conecta() -> dict | None:
    try:
        res = supabase.table("cts").select("*").execute()
        rows = res.data if res and isinstance(res.data, list) else []
        for r in rows:
            nome = str(r.get("name") or r.get("full_name") or "").lower()
            if "conecta" in nome:
                return r
        return rows[0] if rows else None
    except Exception:
        return None


def listar_assinantes() -> list[dict]:
    """Responsaveis tecnicos ativos + instrutores ativos (unificado para escolha)."""
    out: list[dict] = []
    try:
        res = (
            supabase.table("responsaveis_tecnicos")
            .select("*")
            .eq("is_active", True)
            .execute()
        )
        for r in res.data or []:
            out.append(
                {
                    "tipo": "responsavel",
                    "id": r.get("id"),
                    "nome": r.get("nome"),
                    "cpf": r.get("cpf"),
                    "re": r.get("re"),
                    "assinatura_url": r.get("assinatura_url"),
                    "cargo": "Técnico em Segurança do Trabalho",
                }
            )
    except Exception:
        pass
    try:
        res = (
            supabase.table("instrutores")
            .select("*")
            .eq("is_active", True)
            .execute()
        )
        for r in res.data or []:
            out.append(
                {
                    "tipo": "instrutor",
                    "id": r.get("id"),
                    "nome": r.get("name"),
                    "cpf": r.get("cpf"),
                    "re": r.get("re"),
                    "assinatura": r.get("assinatura"),
                    "assinatura_url": r.get("assinatura"),
                    "cargo": "Técnico em Segurança do Trabalho",
                }
            )
    except Exception:
        pass
    return out


def nome_arquivo_certificado(nome_aluno: str, sigla: str) -> str:
    base = re.sub(r"[^A-Za-z0-9 _-]", "", nome_aluno).strip().replace("  ", " ")
    sig = normalizar_sigla(sigla) or "CURSO"
    return f"{base} - {sig}.pdf"
