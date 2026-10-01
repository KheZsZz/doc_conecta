"""Processamento de planilhas de alunos em lote (por ID da turma)."""
from __future__ import annotations

import io
import re
import unicodedata
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

_MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _df_para_excel_bytes(df: pd.DataFrame, sheet_name: str = "Dados") -> bytes:
    """Gera bytes de arquivo Excel (.xlsx) a partir de um DataFrame."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return buffer.getvalue()


def gerar_template_excel() -> bytes:
    """Gera o modelo de lista de alunos em .xlsx."""
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
    return _df_para_excel_bytes(df, sheet_name="Lista")


def gerar_export_turmas_excel(turmas: list[dict]) -> bytes:
    """
    Exporta lista de turmas (ID, titulo, data, empresa) em Excel (.xlsx).
    Aceita linhas ja montadas ou registros crus do Supabase.
    """
    rows = []
    for t in turmas or []:
        if "ID TURMA" in t:
            rows.append(
                {
                    "ID TURMA": t.get("ID TURMA"),
                    "Titulo": t.get("Título") or t.get("Titulo") or "",
                    "Data": t.get("Data") or "",
                    "Empresa": t.get("Empresa") or "",
                }
            )
        else:
            rows.append(
                {
                    "ID TURMA": t.get("id"),
                    "Titulo": t.get("titulo") or "",
                    "Data": str(t.get("data_treinamento") or "")[:10],
                    "Empresa": (t.get("clients") or {}).get("name") or "—",
                }
            )
    df = pd.DataFrame(rows, columns=["ID TURMA", "Titulo", "Data", "Empresa"])
    return _df_para_excel_bytes(df, sheet_name="Turmas")


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


def _normalizar_nome(val) -> str | None:
    s = _limpar_texto(val)
    if not s:
        return None

    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.upper()
    s = re.sub(r"[^A-Z\s]", "", s)
    s = re.sub(r"\s+", " ", s).strip()

    return s or None


def _normalizar_cpf(val) -> str | None:
    s = _limpar_texto(val)
    if not s:
        return None

    digits = re.sub(r"\D", "", s)
    if not digits:
        return None

    if len(digits) > 11:
        return None

    return digits.zfill(11)


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
    cpf: str,
    rg: str | None,
    data_nasc: str | None,
    email: str | None,
) -> str:
    aluno_id = None

    res = supabase.table("alunos").select("id").eq("cpf", cpf).execute()
    if res and res.data:
        aluno_id = res.data[0]["id"]

    if not aluno_id:
        res = supabase.table("alunos").select("id").ilike("name", nome).execute()
        if res and res.data:
            aluno_id = res.data[0]["id"]

    if aluno_id:
        payload_upd: dict[str, Any] = {"name": nome, "cpf": cpf}
        if rg:
            payload_upd["rg"] = rg
        if data_nasc:
            payload_upd["data_nasc"] = data_nasc
        if email:
            payload_upd["email"] = email
        supabase.table("alunos").update(payload_upd).eq("id", aluno_id).execute()
        return aluno_id

    payload_novo: dict[str, Any] = {
        "name": nome,
        "cpf": cpf,
        "rg": rg,
        "data_nasc": data_nasc,
        "email": email,
    }
    payload_novo = {k: v for k, v in payload_novo.items() if v is not None}
    ins = supabase.table("alunos").insert(payload_novo).execute()
    return ins.data[0]["id"]


def processar_lista_lote(arquivo_bytes: bytes, nome_arquivo: str) -> dict:
    """
    Le a planilha e matricula alunos em lote por ID TURMA.

    Obrigatorios: ID TURMA, NOME, CPF
    Opcionais: RG, NASC, DATA TREINAMENTO, EMAIL ALUNO
    """
    try:
        nome_lower = nome_arquivo.lower()
        if nome_lower.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(arquivo_bytes), dtype=str)
        else:
            # .xlsx, .xls, .xlsm
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

    faltando = [c for c in ("ID TURMA", "NOME", "CPF") if c not in df.columns]
    if faltando:
        return {
            "sucesso": False,
            "mensagem": (
                f"A planilha precisa das colunas obrigatorias: {', '.join(faltando)}. "
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
        nome = _normalizar_nome(row.get("NOME"))
        cpf = _normalizar_cpf(row.get("CPF"))

        if not turma_id or not nome or not cpf:
            partes = []
            if not turma_id:
                partes.append("ID TURMA")
            if not nome:
                partes.append("NOME")
            if not cpf:
                partes.append("CPF (apenas numeros, max 11 digitos)")
            erros.append(
                f"Linha {linha_n}: campo(s) obrigatorio(s) invalido(s): {', '.join(partes)}."
            )
            continue

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
