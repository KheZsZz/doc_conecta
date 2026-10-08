"""Leitura e importacao em lote de turmas a partir de planilha."""
from __future__ import annotations

import io
import re
import unicodedata
from datetime import datetime
from typing import Any

import pandas as pd

from src.config.database import supabase

COLUNAS_MODELO = [
    "CNPJ",
    "NOME EMPRESA",
    "ENDERECO",
    "RESPONSAVEL",
    "TELEFONE",
    "EMAIL",
    "UNIDADE",
    "SIGLA CURSO",
    "CURSO",
    "DATA TREINAMENTO",
    "CARGA HORARIA",
    "MODALIDADE",
    "NIVEL",
    "INSTRUTOR",
    "CT",
    "TITULO",
]


def _pick_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    mapa = {str(c).strip().lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in mapa:
            return mapa[cand.lower()]
    for key, orig in mapa.items():
        for cand in candidates:
            if cand.lower() in key or key in cand.lower():
                return orig
    return None


def normalizar_cnpj(val) -> str:
    return re.sub(r"\D", "", str(val or ""))


def _cel(row, col) -> str:
    if col is None:
        return ""
    v = row.get(col)
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v).strip()


def _parse_data(val) -> str | None:
    """
    Aceita data no padrao brasileiro DD/MM/YYYY (preferencial),
    alem de YYYY-MM-DD, datetime do Excel e serial.
    Retorna ISO YYYY-MM-DD para gravar no banco.
    """
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None

    # datetime / Timestamp do pandas ou Excel
    if hasattr(val, "strftime"):
        try:
            return val.strftime("%Y-%m-%d")
        except Exception:
            pass

    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "nat"):
        return None

    # remove hora se vier junto: "15/10/2026 00:00:00"
    s = s.split(" ")[0].split("T")[0].strip()

    # Padrao brasileiro primeiro
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except Exception:
            continue

    # ISO
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(s[:10], fmt).strftime("%Y-%m-%d")
        except Exception:
            continue

    # serial Excel
    try:
        n = float(str(val).strip())
        if 30000 < n < 60000:
            base = datetime(1899, 12, 30)
            return (base + pd.Timedelta(days=n)).strftime("%Y-%m-%d")
    except Exception:
        pass

    return None


def data_iso_para_br(iso: str) -> str:
    try:
        return datetime.strptime(str(iso)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return str(iso or "")


def _parse_carga(val) -> str:
    s = str(val or "").strip()
    if not s or s.lower() in ("nan", "none"):
        return "8 Horas"
    dig = re.sub(r"\D", "", s)
    if dig:
        n = int(dig)
        return f"{n} Horas" if n != 1 else "1 Hora"
    return s


def _sem_acento(s: str) -> str:
    nk = unicodedata.normalize("NFKD", s or "")
    return "".join(ch for ch in nk if not unicodedata.combining(ch))


def _norm_key(s: str) -> str:
    """Normaliza para comparacao de nomes (minusculo, sem acento, espacos simples)."""
    s = _sem_acento(s or "")
    s = re.sub(r"\s+", " ", s.strip().lower())
    return s


def ler_planilha_turmas(arquivo_bytes: bytes) -> tuple[list[dict[str, Any]], list[str]]:
    """Retorna (linhas, erros_leitura)."""
    df = pd.read_excel(io.BytesIO(arquivo_bytes))
    df.columns = [str(c).strip() for c in df.columns]

    col_cnpj = _pick_col(df, ["CNPJ", "cnpj"])
    col_emp = _pick_col(
        df, ["NOME EMPRESA", "EMPRESA", "RAZAO SOCIAL", "RAZÃO SOCIAL", "CLIENTE"]
    )
    col_end = _pick_col(df, ["ENDERECO", "ENDEREÇO", "FULL_ADDRESS", "ADDRESS"])
    col_resp = _pick_col(df, ["RESPONSAVEL", "RESPONSÁVEL", "CONTATO NOME"])
    col_tel = _pick_col(df, ["TELEFONE", "PHONE", "CELULAR", "CONTATO"])
    col_email = _pick_col(df, ["EMAIL", "E-MAIL", "E_MAIL"])
    col_unid = _pick_col(df, ["UNIDADE", "SIGLA UNIDADE", "PLANTA"])
    col_sigla = _pick_col(df, ["SIGLA CURSO", "SIGLA", "ACRONYM"])
    col_curso = _pick_col(df, ["CURSO", "TREINAMENTO", "NOME CURSO"])
    col_data = _pick_col(
        df, ["DATA TREINAMENTO", "DATA", "DATA DO TREINAMENTO", "DATA_TREINAMENTO"]
    )
    col_carga = _pick_col(df, ["CARGA HORARIA", "CARGA", "CARGA_HORARIA", "HORAS"])
    col_mod = _pick_col(df, ["MODALIDADE", "MODALITY"])
    col_nivel = _pick_col(df, ["NIVEL", "NÍVEL", "LEVEL"])
    col_inst = _pick_col(
        df,
        [
            "INSTRUTOR",
            "INSTRUTOR TITULAR",
            "NOME INSTRUTOR",
            "NOME COMPLETO INSTRUTOR",
        ],
    )
    col_ct = _pick_col(df, ["CT", "CENTRO", "CT RESPONSAVEL", "LOCAL"])
    col_titulo = _pick_col(df, ["TITULO", "TÍTULO", "TITULO TURMA"])

    faltando = []
    if not col_cnpj:
        faltando.append("CNPJ")
    if not col_emp:
        faltando.append("NOME EMPRESA")
    if not col_data:
        faltando.append("DATA TREINAMENTO")
    if not col_sigla and not col_curso:
        faltando.append("SIGLA CURSO ou CURSO")
    if faltando:
        return [], [f"Colunas obrigatórias ausentes: {', '.join(faltando)}"]

    linhas: list[dict[str, Any]] = []
    erros: list[str] = []

    for idx, row in df.iterrows():
        nlinha = int(idx) + 2
        cnpj = normalizar_cnpj(_cel(row, col_cnpj))
        nome_emp = _cel(row, col_emp)
        data = _parse_data(row.get(col_data) if col_data else None)
        sigla = re.sub(r"[^A-Z0-9]", "", _cel(row, col_sigla).upper())
        curso_nome = _cel(row, col_curso)
        instrutor_nome = _cel(row, col_inst)

        if not cnpj and not nome_emp and not data:
            continue

        if not cnpj or len(cnpj) < 11:
            erros.append(f"Linha {nlinha}: CNPJ inválido ({cnpj or 'vazio'}).")
            continue
        cnpj = cnpj.zfill(14) if len(cnpj) <= 14 else cnpj[:14]

        if not nome_emp:
            erros.append(f"Linha {nlinha}: nome da empresa obrigatório.")
            continue
        if not data:
            raw = _cel(row, col_data)
            erros.append(
                f"Linha {nlinha}: data inválida ({raw or 'vazia'}). "
                f"Use o padrão brasileiro DD/MM/AAAA (ex.: 15/10/2026)."
            )
            continue
        if not sigla and not curso_nome:
            erros.append(f"Linha {nlinha}: informe SIGLA CURSO ou CURSO.")
            continue

        linhas.append(
            {
                "linha": nlinha,
                "cnpj": cnpj,
                "nome_empresa": nome_emp,
                "endereco": _cel(row, col_end),
                "responsavel": _cel(row, col_resp),
                "telefone": re.sub(r"\D", "", _cel(row, col_tel)) or _cel(row, col_tel),
                "email": _cel(row, col_email),
                "unidade": _cel(row, col_unid),
                "sigla_curso": sigla,
                "curso_nome": curso_nome,
                "data_treinamento": data,
                "data_treinamento_br": data_iso_para_br(data),
                "carga_horaria": _parse_carga(
                    row.get(col_carga) if col_carga else None
                ),
                "modalidade": _cel(row, col_mod) or "In Company",
                "nivel": _cel(row, col_nivel) or "Formação",
                "instrutor": instrutor_nome,
                "ct": _cel(row, col_ct),
                "titulo": _cel(row, col_titulo),
            }
        )

    return linhas, erros


def _cache_empresas_por_cnpj() -> dict[str, dict]:
    out: dict[str, dict] = {}
    try:
        res = supabase.table("clients").select("*").execute()
        for r in res.data or []:
            dig = normalizar_cnpj(r.get("cnpj"))
            if dig:
                out[dig] = r
    except Exception:
        pass
    return out


def _cache_cursos() -> tuple[dict[str, dict], dict[str, dict]]:
    by_sigla: dict[str, dict] = {}
    by_nome: dict[str, dict] = {}
    try:
        res = supabase.table("cursos").select("*").execute()
        for r in res.data or []:
            sig = re.sub(r"[^A-Z0-9]", "", str(r.get("sigla") or "").upper())
            if sig:
                by_sigla[sig] = r
            nome = _norm_key(r.get("name") or "")
            if nome:
                by_nome[nome] = r
    except Exception:
        pass
    return by_sigla, by_nome


def _cache_instrutores() -> dict[str, dict]:
    out: dict[str, dict] = {}
    try:
        res = supabase.table("instrutores").select("*").execute()
        for r in res.data or []:
            key = _norm_key(r.get("name") or "")
            if key:
                out[key] = r
    except Exception:
        pass
    return out


def _cache_cts() -> dict[str, dict]:
    out: dict[str, dict] = {}
    try:
        res = supabase.table("cts").select("*").execute()
        for r in res.data or []:
            key = _norm_key(r.get("name") or "")
            if key:
                out[key] = r
    except Exception:
        pass
    return out


def resolver_ou_criar_empresa(
    linha: dict,
    cache_cnpj: dict[str, dict],
) -> tuple[dict | None, str | None, bool]:
    cnpj = linha["cnpj"]
    if cnpj in cache_cnpj:
        return cache_cnpj[cnpj], None, False

    nome = linha["nome_empresa"].strip()
    payload = {
        "name": nome,
        "cnpj": cnpj,
        "full_address": linha.get("endereco") or None,
        "responsavel": linha.get("responsavel") or None,
        "phone": linha.get("telefone") or None,
        "email": linha.get("email") or None,
        "sigla": linha.get("unidade") or None,
    }

    try:
        res = supabase.table("clients").insert(payload).execute()
        emp = res.data[0] if res and res.data else payload
        if emp.get("id"):
            cache_cnpj[cnpj] = emp
        return emp, None, True
    except Exception as e:
        msg = str(e)
        if "clients_name_key" in msg or "duplicate" in msg.lower():
            payload["name"] = f"{nome} ({cnpj[-6:]})"
            try:
                res = supabase.table("clients").insert(payload).execute()
                emp = res.data[0] if res and res.data else payload
                if emp.get("id"):
                    cache_cnpj[cnpj] = emp
                return emp, None, True
            except Exception as e2:
                return None, f"Falha ao criar empresa: {e2}", False
        return None, f"Falha ao criar empresa: {e}", False


def resolver_curso(
    linha: dict,
    by_sigla: dict[str, dict],
    by_nome: dict[str, dict],
) -> tuple[dict | None, str | None]:
    sig = re.sub(r"[^A-Z0-9]", "", str(linha.get("sigla_curso") or "").upper())
    if sig and sig in by_sigla:
        return by_sigla[sig], None
    nome = _norm_key(linha.get("curso_nome") or "")
    if nome and nome in by_nome:
        return by_nome[nome], None
    if nome:
        for k, v in by_nome.items():
            if nome in k or k in nome:
                return v, None
    ref = sig or linha.get("curso_nome") or "?"
    return None, f"Curso não encontrado: {ref}"


def resolver_instrutor(
    nome: str,
    cache: dict[str, dict],
    fallback: dict | None,
) -> tuple[dict | None, str | None]:
    """
    Resolve pelo nome completo do instrutor (ignora acentos e maiúsculas).
    Ex.: "Carlos Eduardo Morroni" == "CARLOS EDUARDO MORRONI"
    """
    nome = (nome or "").strip()
    if nome:
        key = _norm_key(nome)
        # 1) match exato do nome completo
        if key in cache:
            return cache[key], None
        # 2) planilha contém o nome cadastrado ou vice-versa
        candidatos = []
        for k, v in cache.items():
            if key == k:
                return v, None
            if key in k or k in key:
                candidatos.append((len(k), v))
        if len(candidatos) == 1:
            return candidatos[0][1], None
        if len(candidatos) > 1:
            # pega o nome mais longo (mais específico)
            candidatos.sort(key=lambda x: -x[0])
            return candidatos[0][1], None
        return (
            None,
            f"Instrutor não encontrado: '{nome}'. "
            f"Use o nome completo igual ao cadastro de instrutores.",
        )
    if fallback:
        return fallback, None
    return None, "Instrutor não informado e nenhum padrão disponível"


def resolver_ct(
    nome: str,
    cache: dict[str, dict],
    fallback: dict | None,
) -> tuple[dict | None, str | None]:
    if nome:
        key = _norm_key(nome)
        if key in cache:
            return cache[key], None
        for k, v in cache.items():
            if key in k or k in key:
                return v, None
        return None, f"CT não encontrado: {nome}"
    if fallback:
        return fallback, None
    return None, "CT não informado e nenhum padrão disponível"


def montar_titulo(linha: dict, curso: dict) -> str:
    if linha.get("titulo"):
        return linha["titulo"]
    sig = curso.get("sigla") or ""
    nome_c = curso.get("name") or "Treinamento"
    emp = linha.get("nome_empresa") or ""
    data_br = linha.get("data_treinamento_br") or data_iso_para_br(
        linha.get("data_treinamento") or ""
    )
    base = f"{sig or nome_c} - {emp} - {data_br}"
    return base[:200]


def importar_turmas_lote(
    linhas: list[dict],
    *,
    instrutor_padrao_id: str | None = None,
    ct_padrao_id: str | None = None,
) -> dict[str, Any]:
    cache_emp = _cache_empresas_por_cnpj()
    by_sigla, by_nome = _cache_cursos()
    cache_inst = _cache_instrutores()
    cache_ct = _cache_cts()

    fb_inst = None
    if instrutor_padrao_id:
        for v in cache_inst.values():
            if v.get("id") == instrutor_padrao_id:
                fb_inst = v
                break
    if not fb_inst and cache_inst:
        fb_inst = next(iter(cache_inst.values()))

    fb_ct = None
    if ct_padrao_id:
        for v in cache_ct.values():
            if v.get("id") == ct_padrao_id:
                fb_ct = v
                break
    if not fb_ct and cache_ct:
        for v in cache_ct.values():
            if "conecta" in (v.get("name") or "").lower():
                fb_ct = v
                break
        if not fb_ct:
            fb_ct = next(iter(cache_ct.values()))

    criadas = 0
    empresas_novas = 0
    erros: list[str] = []
    detalhes: list[dict] = []

    for linha in linhas:
        n = linha["linha"]
        emp, err_emp, nova = resolver_ou_criar_empresa(linha, cache_emp)
        if err_emp or not emp:
            erros.append(f"Linha {n}: {err_emp or 'empresa inválida'}")
            continue
        if nova:
            empresas_novas += 1

        curso, err_c = resolver_curso(linha, by_sigla, by_nome)
        if err_c or not curso:
            erros.append(f"Linha {n}: {err_c}")
            continue

        inst, err_i = resolver_instrutor(
            linha.get("instrutor") or "", cache_inst, fb_inst
        )
        if err_i or not inst:
            erros.append(f"Linha {n}: {err_i}")
            continue

        ct, err_ct = resolver_ct(linha.get("ct") or "", cache_ct, fb_ct)
        if err_ct or not ct:
            erros.append(f"Linha {n}: {err_ct}")
            continue

        titulo = montar_titulo(linha, curso)
        payload = {
            "titulo": titulo,
            "data_treinamento": linha["data_treinamento"],
            "curso_id": curso.get("id"),
            "instrutor_id": inst.get("id"),
            "client_id": emp.get("id"),
            "ct_id": ct.get("id"),
            "modalidade": linha.get("modalidade") or "In Company",
            "nivel": linha.get("nivel") or "Formação",
            "carga_horaria": linha.get("carga_horaria") or "8 Horas",
            "documento_emitido": False,
        }

        try:
            supabase.table("turmas").insert(payload).execute()
            criadas += 1
            detalhes.append(
                {
                    "linha": n,
                    "titulo": titulo,
                    "empresa": emp.get("name"),
                    "empresa_nova": nova,
                    "curso": curso.get("sigla") or curso.get("name"),
                    "instrutor": inst.get("name"),
                    "data": linha.get("data_treinamento_br")
                    or data_iso_para_br(linha["data_treinamento"]),
                }
            )
        except Exception as e:
            erros.append(f"Linha {n}: erro ao criar turma: {e}")

    return {
        "criadas": criadas,
        "empresas_novas": empresas_novas,
        "erros": erros,
        "detalhes": detalhes,
    }


def gerar_modelo_planilha() -> bytes:
    df = pd.DataFrame(
        [
            {
                "CNPJ": "42.365.296/0010-85",
                "NOME EMPRESA": "KION SOUTH AMERICA FABRICACAO DE EQUIPAMENTOS PARA ARMAZENAGEM LTDA",
                "ENDERECO": "Rod. SP-075, Km 56, Indaiatuba - SP",
                "RESPONSAVEL": "João Silva",
                "TELEFONE": "11999999999",
                "EMAIL": "contato@empresa.com",
                "UNIDADE": "Indaiatuba",
                "SIGLA CURSO": "NR12",
                "CURSO": "",
                "DATA TREINAMENTO": "15/10/2026",
                "CARGA HORARIA": "8",
                "MODALIDADE": "In Company",
                "NIVEL": "Formação",
                "INSTRUTOR": "CARLOS EDUARDO MORRONI",
                "CT": "Conecta",
                "TITULO": "",
            }
        ]
    )
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Turmas")
    return buf.getvalue()
