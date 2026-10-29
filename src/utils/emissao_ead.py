"""Leitura da planilha EAD e resolucao de empresa/curso/CT/assinantes."""
from __future__ import annotations

import io
import re
import unicodedata
from typing import Any

import pandas as pd

from src.config.database import supabase


def normalizar_cnpj(val) -> str:
    return re.sub(r"\D", "", str(val or ""))


def normalizar_cpf(val) -> str:
    return re.sub(r"\D", "", str(val or ""))


def normalizar_sigla(val) -> str:
    return re.sub(r"\s+", "", str(val or "").strip().upper())


def _sem_acento(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(ch for ch in s if not unicodedata.combining(ch)).lower().strip()


def normalizar_nivel(val) -> str:
    """Aceita formação/reciclagem (com ou sem acento); padrão Formação."""
    s = _sem_acento(str(val or ""))
    if not s or s in ("nan", "none"):
        return "Formação"
    if "recic" in s:
        return "Reciclagem"
    return "Formação"


def _achacol(df: pd.DataFrame, candidatos: list[str]) -> str | None:
    """Encontra coluna ignorando maiúsculas, espaços extras e acentos."""
    cols_norm = {_sem_acento(str(c)): c for c in df.columns}
    for cand in candidatos:
        key = _sem_acento(cand)
        if key in cols_norm:
            return cols_norm[key]
    for c in df.columns:
        cl = _sem_acento(str(c))
        for cand in candidatos:
            if _sem_acento(cand) in cl:
                return c
    return None


def ler_planilha_ead(conteudo: bytes) -> tuple[list[dict], list[str]]:
    """Retorna (linhas validas, erros/avisos)."""
    erros: list[str] = []
    try:
        df = pd.read_excel(io.BytesIO(conteudo))
    except Exception as e:
        return [], [f"Falha ao ler planilha: {e}"]

    if df is None or df.empty:
        return [], ["Planilha vazia."]

    col_cnpj = _achacol(df, ["cnpj"])
    col_nome = _achacol(df, ["nome", "name", "aluno"])
    col_email = _achacol(df, ["e-mail", "email", "mail"])
    col_cpf = _achacol(df, ["cpf"])
    col_sigla = _achacol(df, ["sigla curso", "sigla", "curso"])
    col_carga = _achacol(df, ["carga", "carga horaria", "carga_horaria"])
    col_prog = _achacol(df, ["progresso", "progress"])
    col_nivel = _achacol(
        df, ["nivel", "nível", "tipo", "tipo treinamento", "tipo de treinamento"]
    )
    col_ini = _achacol(df, ["data de inicio", "data inicio", "inicio", "data_inicio"])
    col_fim = _achacol(
        df,
        [
            "data de finalizacao",
            "data de finalização",
            "data finalizacao",
            "data finalização",
            "data fim",
            "fim",
            "data_fim",
            "data de termino",
            "data termino",
        ],
    )

    obrigatorias = {
        "CNPJ": col_cnpj,
        "Nome": col_nome,
        "CPF": col_cpf,
        "SIGLA CURSO": col_sigla,
        "Progresso": col_prog,
        "Data de Inicio": col_ini,
        "Data de Finalização": col_fim,
    }
    faltando = [k for k, v in obrigatorias.items() if v is None]
    if faltando:
        return [], [f"Colunas obrigatórias ausentes: {', '.join(faltando)}"]

    linhas: list[dict] = []
    for i, row in df.iterrows():
        nlinha = int(i) + 2  # header = 1
        nome = str(row.get(col_nome) or "").strip()
        cpf = normalizar_cpf(row.get(col_cpf))
        cnpj = normalizar_cnpj(row.get(col_cnpj))
        sigla = normalizar_sigla(row.get(col_sigla))

        prog_raw = row.get(col_prog)
        try:
            prog = float(prog_raw)
            if prog > 1.5:
                prog = prog / 100.0
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

        nivel = "Formação"
        if col_nivel is not None and pd.notna(row.get(col_nivel)):
            nivel = normalizar_nivel(row.get(col_nivel))

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
                "nivel": nivel,
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


def listar_responsaveis_tecnicos() -> list[dict]:
    """RTs ativos; o padrão (is_default) vem sempre em primeiro."""
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
                    "formacao": (r.get("formacao") or "").strip(),
                    "assinatura_url": r.get("assinatura_url"),
                    "assinatura": r.get("assinatura_url"),
                    "cargo": (r.get("formacao") or "Técnico em Segurança do Trabalho").strip(),
                    "is_default": bool(r.get("is_default")),
                }
            )
    except Exception:
        pass
    out.sort(key=lambda x: (0 if x.get("is_default") else 1, (x.get("nome") or "").upper()))
    return out


def listar_assinantes() -> list[dict]:
    """Compat: RTs (padrão primeiro) + instrutores ativos."""
    out = listar_responsaveis_tecnicos()
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
                    "formacao": (r.get("formacao") or "").strip(),
                    "assinatura": r.get("assinatura"),
                    "assinatura_url": r.get("assinatura"),
                    "cargo": "Técnico em Segurança do Trabalho",
                    "is_default": False,
                }
            )
    except Exception:
        pass
    return out


def nome_arquivo_certificado(nome_aluno: str, sigla: str) -> str:
    base = re.sub(r"[^A-Za-z0-9 _-]", "", nome_aluno).strip().replace("  ", " ")
    sig = normalizar_sigla(sigla) or "CURSO"
    return f"{base} - {sig}.pdf"
