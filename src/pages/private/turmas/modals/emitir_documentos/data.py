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
        res = supabase.table("instrutores").select("*").eq("id", instrutor_id).single().execute()
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


def fetch_responsaveis() -> list[dict]:
    try:
        res = supabase.table("responsaveis_tecnicos").select("*").execute()
        return res.data if res and res.data else []
    except Exception:
        return []


def resolver_cidade(ct_id: str | None, turma_data: dict) -> str:
    ct_id_resolvido = ct_id or turma_data.get("ct_id")
    ct_data = fetch_ct(ct_id_resolvido)
    if ct_data:
        return extrair_cidade_do_endereco(ct_data.get("full_address"))
    return "Itapecerica da Serra"


def marcar_documento_emitido(tid: str) -> tuple[bool, str]:
    """
    Marca a turma como documentação emitida.
    Retorna (ok, mensagem).
    """
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
        # Confirma leitura
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
