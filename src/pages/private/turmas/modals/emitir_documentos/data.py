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
            .select(
                "id, data_treinamento, carga_horaria, client_id, "
                "clients(id, name, cnpj, sigla), "
                "alunos(id, name, rg, cpf, data_nasc, re)"
            )
            .eq("turma_id", tid)
            .execute()
        )
        return res.data if res and res.data else []
    except Exception:
        try:
            res = (
                supabase.table("matriculas")
                .select(
                    "data_treinamento, carga_horaria, client_id, "
                    "alunos(id, name, rg, cpf, data_nasc)"
                )
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


def fetch_cursos_ids_do_responsavel(responsavel_id: str | None) -> list[str]:
    """IDs de cursos vinculados ao RT (tabela responsavel_cursos)."""
    if not responsavel_id:
        return []
    try:
        res = (
            supabase.table("responsavel_cursos")
            .select("curso_id")
            .eq("responsavel_id", responsavel_id)
            .execute()
        )
        return [str(r["curso_id"]) for r in (res.data or []) if r.get("curso_id")]
    except Exception:
        return []


def salvar_cursos_do_responsavel(responsavel_id: str, curso_ids: list[str]) -> None:
    """Substitui os vínculos do RT com a lista de cursos informada."""
    if not responsavel_id:
        return
    ids = [str(c) for c in (curso_ids or []) if c]
    # remove vínculos atuais
    try:
        supabase.table("responsavel_cursos").delete().eq(
            "responsavel_id", responsavel_id
        ).execute()
    except Exception:
        pass
    if not ids:
        return
    rows = [{"responsavel_id": responsavel_id, "curso_id": cid} for cid in ids]
    supabase.table("responsavel_cursos").insert(rows).execute()


def fetch_responsaveis_do_curso(curso_id: str | None) -> list[dict]:
    """RTs ativos vinculados ao curso (via responsavel_cursos)."""
    if not curso_id:
        return []
    try:
        res = (
            supabase.table("responsavel_cursos")
            .select("responsavel_id")
            .eq("curso_id", curso_id)
            .execute()
        )
        ids = [str(r["responsavel_id"]) for r in (res.data or []) if r.get("responsavel_id")]
    except Exception:
        return []
    if not ids:
        return []
    todos = fetch_responsaveis()
    ativos = [r for r in todos if r.get("is_active", True) and str(r.get("id")) in ids]
    return ativos


def dados_resp_de_registro(r: dict | None) -> dict:
    r = r or {}
    return {
        "id": r.get("id"),
        "nome": r.get("nome") or "",
        "cpf": r.get("cpf") or "",
        "re": (r.get("re") or "").strip(),
        "formacao": (r.get("formacao") or "").strip(),
        "assinatura_url": r.get("assinatura_url"),
    }


def resolver_responsavel(
    *,
    curso_id: str | None = None,
    responsavel_id: str | None = None,
) -> dict:
    """Resolve o RT na ordem: id explícito → vínculo do curso → is_default → primeiro ativo."""
    todos = fetch_responsaveis()
    ativos = [r for r in todos if r.get("is_active", True)]

    if not ativos:
        return {
            "id": None,
            "nome": "Cristiano Reis",
            "cpf": "214.135.358-01",
            "re": "0075191",
            "formacao": "",
            "assinatura_url": None,
        }

    if responsavel_id:
        for r in ativos:
            if str(r.get("id")) == str(responsavel_id):
                return dados_resp_de_registro(r)

    if curso_id:
        do_curso = fetch_responsaveis_do_curso(curso_id)
        if do_curso:
            return dados_resp_de_registro(do_curso[0])

    padrao = next((r for r in ativos if r.get("is_default")), None)
    if padrao:
        return dados_resp_de_registro(padrao)

    return dados_resp_de_registro(ativos[0])


def label_responsavel(r: dict) -> str:
    nome = r.get("nome") or "Sem Nome"
    cpf = r.get("cpf") or "N/D"
    re_val = (r.get("re") or "").strip()
    formacao = (r.get("formacao") or "").strip()
    label = f"{nome} (CPF: {cpf}"
    if re_val:
        label += f" | RE: {re_val}"
    if formacao:
        label += f" | {formacao}"
    label += ")"
    return label


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
