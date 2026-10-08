import re
import unicodedata

from src.config.database import supabase
from src.pages.private.turmas.helpers import extrair_cidade_do_endereco


def fetch_turma(tid: str) -> dict:
    try:
        res = supabase.table("turmas").select("*").eq("id", tid).single().execute()
        return res.data if res and res.data else {}
    except Exception:
        return {}


def fetch_curso(curso_id: str | None) -> dict:
    if not curso_id:
        return {}
    try:
        res = supabase.table("cursos").select("*").eq("id", curso_id).single().execute()
        return res.data if res and res.data else {}
    except Exception:
        return {}


def fetch_ct(ct_id: str | None) -> dict:
    if not ct_id:
        return {}
    try:
        res = supabase.table("cts").select("*").eq("id", ct_id).single().execute()
        return res.data if res and res.data else {}
    except Exception:
        return {}


def fetch_empresa(client_id: str | None) -> dict:
    if not client_id:
        return {}
    try:
        res = supabase.table("clients").select("*").eq("id", client_id).single().execute()
        return res.data if res and res.data else {}
    except Exception:
        return {}


def fetch_instrutor(instrutor_id: str | None) -> dict:
    if not instrutor_id:
        return {}
    try:
        res = (
            supabase.table("instrutores")
            .select("*")
            .eq("id", instrutor_id)
            .single()
            .execute()
        )
        return res.data if res and res.data else {}
    except Exception:
        return {}


def fetch_matriculas(tid: str) -> list[dict]:
    try:
        res = (
            supabase.table("matriculas")
            .select("data_treinamento, carga_horaria, alunos(name, rg, cpf, data_nasc)")
            .eq("turma_id", tid)
            .execute()
        )
        return res.data if res and res.data else []
    except Exception:
        return []


def _norm_nome(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", s.strip().lower())


def _cpf_digitos(val) -> str:
    return re.sub(r"\D", "", str(val or ""))


def _mapa_re_instrutores() -> dict[str, str]:
    """
    Mapa cpf_digitos -> RE e nome_norm -> RE a partir da tabela instrutores.
    Usado para completar RE do responsavel tecnico quando estiver vazio.
    """
    by_cpf: dict[str, str] = {}
    by_nome: dict[str, str] = {}
    try:
        res = supabase.table("instrutores").select("name, cpf, re").execute()
        for i in res.data or []:
            re_val = (i.get("re") or "").strip()
            if not re_val:
                continue
            cpf = _cpf_digitos(i.get("cpf"))
            if cpf:
                by_cpf[cpf] = re_val
            nome = _norm_nome(i.get("name") or "")
            if nome:
                by_nome[nome] = re_val
    except Exception:
        pass
    return {"cpf": by_cpf, "nome": by_nome}


def fetch_responsaveis() -> list[dict]:
    """
    Lista responsaveis tecnicos e preenche RE a partir do cadastro de
    instrutores (mesmo CPF ou mesmo nome) quando o campo re estiver vazio.
    """
    try:
        res = supabase.table("responsaveis_tecnicos").select("*").execute()
        lista = res.data if res and res.data else []
    except Exception:
        return []

    mapa = _mapa_re_instrutores()
    by_cpf = mapa["cpf"]
    by_nome = mapa["nome"]

    for r in lista:
        if (r.get("re") or "").strip():
            continue
        cpf = _cpf_digitos(r.get("cpf"))
        if cpf and cpf in by_cpf:
            r["re"] = by_cpf[cpf]
            continue
        nome = _norm_nome(r.get("nome") or "")
        if nome and nome in by_nome:
            r["re"] = by_nome[nome]

    return lista


def resolver_cidade(ct_id: str | None, turma_data: dict) -> str:
    ct_id_resolvido = ct_id or turma_data.get("ct_id")
    ct_data = fetch_ct(ct_id_resolvido)
    if ct_data:
        return extrair_cidade_do_endereco(ct_data.get("full_address"))
    return "Itapecerica da Serra"


def marcar_documento_emitido(tid: str) -> tuple[bool, str]:
    if not tid:
        return False, "ID da turma inválido."
    try:
        res = (
            supabase.table("turmas")
            .update({"documento_emitido": True})
            .eq("id", tid)
            .execute()
        )
        if res is None:
            return False, "Resposta vazia do banco ao marcar emissão."
        check = (
            supabase.table("turmas")
            .select("documento_emitido")
            .eq("id", tid)
            .single()
            .execute()
        )
        if check and check.data and check.data.get("documento_emitido") is True:
            return True, "Turma marcada como documentação emitida."
        return True, "Update enviado (confira o card na listagem)."
    except Exception as e:
        return False, f"Falha ao marcar emissão: {e}"
