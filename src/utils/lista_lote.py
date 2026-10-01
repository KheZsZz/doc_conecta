"""Processamento de planilhas de alunos em lote (por ID da turma)."""
from __future__ import annotations

import io
import re
from typing import Any

import pandas as pd

from src.config.database import supabase

COLUNAS_MODELO = [
    "ID TURMA",
    "NOME",
    "CPF",
    "RG",
    "NASC",
    "DATA TREINAMENTO",
    "EMAIL ALUNO",
]

ALIASES: dict[str, list[str]] = {
    "ID TURMA": ["id turma", "turma_id", "id_turma", "turma id", "id da turma"],
    "NOME": ["nome", "name", "nome completo", "aluno"],
    "CPF": ["cpf"],
    "RG": ["rg"],
    "NASC": ["nasc", "nascimento", "data nasc", "data de nascimento", "data_nasc"],
    "DATA TREINAMENTO": [
        "data treinamento",
        "data do treinamento",
        "data_treinamento",
        "data",
    ],
    "EMAIL ALUNO": ["email aluno", "email", "e-mail", "e-mail aluno"],
}


def gerar_template_excel() -> bytes:
    """Gera o modelo .xlsx para download."""
    df = pd.DataFrame(columns=COLUNAS_MODELO)
    df.loc[0] = [
        "uuid-da-turma-aqui",
        "JOAO DA SILVA",
        "00000000000",
        "1234567",
        "15/03/1990",
        "01/10/2026",
        "joao@email.com",
    ]
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Lista")
    return buffer.getvalue()


def _normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    mapa: dict[str, str] = {}
    colunas_lower = {str(c).strip().lower(): c for c in df.columns}

    for canonico, aliases in ALIASES.items():
        if canonico.lower() in colunas_lower:
            mapa[colunas_lower[canonico.lower()]] = canonico
            continue
        for alias in aliases:
            if alias in colunas_lower:
                mapa[colunas_lower[alias]] = canonico
                break

    return df.rename(columns=mapa)


def _limpar_texto(val) -> str | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "nat"):
        return None
    return s


def _limpar_cpf(val) -> str | None:
    s = _limpar_texto(val)
    if not s:
        return None
    digits = re.sub(r"\D", "", s)
    return digits or None


def _parse_data(val) -> str | None:
    s = _limpar_texto(val)
    if not s:
        return None
    try:
        dt = pd.to_datetime(s, dayfirst=True, errors="coerce")
        if pd.notnull(dt):
            return dt.strftime("%Y-%m-%d")
    except Exception:
        pass
    return None


def _buscar_ou_criar_aluno(
    nome: str,
    cpf: str | None,
    rg: str | None,
    data_nasc: str | None,
    email: str | None,
    client_id: str | None,
) -> str:
    aluno_id = None

    if cpf:
        res = supabase.table("alunos").select("id").eq("cpf", cpf).execute()
        if res and res.data:
            aluno_id = res.data[0]["id"]

    if not aluno_id:
        res = supabase.table("alunos").select("id").ilike("name", nome).execute()
        if res and res.data:
            aluno_id = res.data[0]["id"]

    if aluno_id:
        payload_upd: dict[str, Any] = {"name": nome}
        if cpf:
            payload_upd["cpf"] = cpf
        if rg:
            payload_upd["rg"] = rg
        if data_nasc:
            payload_upd["data_nasc"] = data_nasc
        if email:
            payload_upd["email"] = email
        if client_id:
            payload_upd["client_id"] = client_id
        supabase.table("alunos").update(payload_upd).eq("id", aluno_id).execute()
        return aluno_id

    payload_novo: dict[str, Any] = {
        "name": nome,
        "cpf": cpf,
        "rg": rg,
        "data_nasc": data_nasc,
        "email": email,
        "client_id": client_id,
    }
    payload_novo = {k: v for k, v in payload_novo.items() if v is not None}
    ins = supabase.table("alunos").insert(payload_novo).execute()
    return ins.data[0]["id"]


def processar_lista_lote(arquivo_bytes: bytes, nome_arquivo: str) -> dict:
    """
    Le a planilha e matricula alunos em lote por ID TURMA.

    Obrigatorios: ID TURMA, NOME
    Opcionais: CPF, RG, NASC, DATA TREINAMENTO, EMAIL ALUNO
    """
    try:
        if nome_arquivo.lower().endswith(".csv"):
            df = pd.read_csv(io.BytesIO(arquivo_bytes), dtype=str)
        else:
            df = pd.read_excel(io.BytesIO(arquivo_bytes), dtype=str)
    except Exception as e:
        return {
            "sucesso": False,
            "mensagem": f"Nao foi possivel ler o arquivo: {e}",
            "alunos_processados": 0,
            "matriculas_criadas": 0,
            "erros": [],
        }

    df = _normalizar_colunas(df)

    if "ID TURMA" not in df.columns or "NOME" not in df.columns:
        return {
            "sucesso": False,
            "mensagem": (
                "A planilha precisa das colunas ID TURMA e NOME. "
                "Baixe o modelo oficial e preencha."
            ),
            "alunos_processados": 0,
            "matriculas_criadas": 0,
            "erros": [],
        }

    cache_turmas: dict[str, dict] = {}
    alunos_processados = 0
    matriculas_criadas = 0
    erros: list[str] = []

    for idx, row in df.iterrows():
        linha_n = int(idx) + 2

        turma_id = _limpar_texto(row.get("ID TURMA"))
        nome = _limpar_texto(row.get("NOME"))

        if not turma_id or not nome:
            erros.append(f"Linha {linha_n}: ID TURMA e NOME sao obrigatorios.")
            continue

        nome = nome.upper()
        cpf = _limpar_cpf(row.get("CPF")) if "CPF" in df.columns else None
        rg = _limpar_texto(row.get("RG")) if "RG" in df.columns else None
        data_nasc = _parse_data(row.get("NASC")) if "NASC" in df.columns else None
        data_trein_planilha = (
            _parse_data(row.get("DATA TREINAMENTO"))
            if "DATA TREINAMENTO" in df.columns
            else None
        )
        email = (
            _limpar_texto(row.get("EMAIL ALUNO"))
            if "EMAIL ALUNO" in df.columns
            else None
        )

        try:
            if turma_id not in cache_turmas:
                t_res = (
                    supabase.table("turmas")
                    .select("id, titulo, client_id, carga_horaria, data_treinamento")
                    .eq("id", turma_id)
                    .execute()
                )
                if not t_res or not t_res.data:
                    erros.append(f"Linha {linha_n}: turma '{turma_id}' nao encontrada.")
                    continue
                cache_turmas[turma_id] = t_res.data[0]

            turma = cache_turmas[turma_id]
            client_id = turma.get("client_id")
            carga = turma.get("carga_horaria") or "8 Horas"
            data_trein = data_trein_planilha or (
                str(turma.get("data_treinamento", ""))[:10] or None
            )

            aluno_id = _buscar_ou_criar_aluno(
                nome=nome,
                cpf=cpf,
                rg=rg,
                data_nasc=data_nasc,
                email=email,
                client_id=client_id,
            )
            alunos_processados += 1

            mat_res = (
                supabase.table("matriculas")
                .select("id")
                .eq("turma_id", turma_id)
                .eq("aluno_id", aluno_id)
                .execute()
            )
            if mat_res and mat_res.data:
                erros.append(
                    f"Linha {linha_n}: {nome} ja matriculado na turma "
                    f"{turma.get('titulo', turma_id)}."
                )
                continue

            payload_mat = {
                "turma_id": turma_id,
                "aluno_id": aluno_id,
                "data_treinamento": data_trein,
                "carga_horaria": carga,
            }
            supabase.table("matriculas").insert(payload_mat).execute()
            matriculas_criadas += 1

        except Exception as e:
            erros.append(f"Linha {linha_n} ({nome}): {e}")

    if alunos_processados or matriculas_criadas:
        msg = (
            f"Processamento concluido: {alunos_processados} aluno(s), "
            f"{matriculas_criadas} nova(s) matricula(s)."
        )
        return {
            "sucesso": True,
            "mensagem": msg,
            "alunos_processados": alunos_processados,
            "matriculas_criadas": matriculas_criadas,
            "erros": erros,
        }

    return {
        "sucesso": False,
        "mensagem": "Nenhuma linha valida processada.",
        "alunos_processados": 0,
        "matriculas_criadas": 0,
        "erros": erros,
    }
