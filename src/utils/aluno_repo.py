"""Helpers de persistência de alunos (lista em lote)."""
from __future__ import annotations

from typing import Any

from src.config.database import supabase


def _buscar_ou_criar_aluno(
    nome: str,
    cpf: str,
    rg: str | None,
    data_nasc: str | None,
    email: str | None,
    re_aluno: str | None = None,
) -> str:
    """
    Busca aluno por CPF (depois RG, depois nome).
    RG duplicado (unique alunos_rg_key) NÃO bloqueia: grava sem RG ou
    reaproveita o aluno que já tem esse RG.
    """
    aluno_id = None

    # 1) CPF limpo
    res = supabase.table("alunos").select("id").eq("cpf", cpf).execute()
    if res and res.data:
        aluno_id = res.data[0]["id"]

    # 2) CPF formatado
    if not aluno_id:
        cpf11 = cpf.zfill(11)
        cpf_fmt = f"{cpf11[:3]}.{cpf11[3:6]}.{cpf11[6:9]}-{cpf11[9:]}"
        try:
            res = supabase.table("alunos").select("id").eq("cpf", cpf_fmt).execute()
            if res and res.data:
                aluno_id = res.data[0]["id"]
        except Exception:
            pass

    # 3) RG já cadastrado (evita 23505 na insert)
    if not aluno_id and rg:
        try:
            res = supabase.table("alunos").select("id").eq("rg", rg).execute()
            if res and res.data:
                aluno_id = res.data[0]["id"]
        except Exception:
            pass

    # 4) Nome
    if not aluno_id:
        res = supabase.table("alunos").select("id").ilike("name", nome).execute()
        if res and res.data:
            aluno_id = res.data[0]["id"]

    payload_base: dict[str, Any] = {"name": nome, "cpf": cpf}
    if data_nasc:
        payload_base["data_nasc"] = data_nasc
    if email:
        payload_base["email"] = email

    def _is_retryable(err: Exception) -> bool:
        msg = str(err).lower()
        if "22001" in str(err) or "too long" in msg:
            return True
        if "23505" in str(err) or "duplicate" in msg or "unique" in msg:
            return True
        if "column" in msg and ("does not exist" in msg or "schema cache" in msg):
            return True
        return False

    def _gravar_base(aid: str | None) -> str:
        tentativas: list[dict[str, Any]] = []
        if rg:
            tentativas.append({**payload_base, "rg": rg})
            if len(str(rg)) > 9:
                tentativas.append({**payload_base, "rg": str(rg)[:9]})
        tentativas.append(dict(payload_base))

        last_err = None
        for p in tentativas:
            try:
                if aid:
                    supabase.table("alunos").update(p).eq("id", aid).execute()
                    return aid
                ins = supabase.table("alunos").insert(p).execute()
                return ins.data[0]["id"]
            except Exception as e:
                last_err = e
                if _is_retryable(e):
                    if (
                        not aid
                        and rg
                        and ("23505" in str(e) or "duplicate" in str(e).lower())
                    ):
                        try:
                            r2 = (
                                supabase.table("alunos")
                                .select("id")
                                .eq("rg", rg)
                                .execute()
                            )
                            if r2 and r2.data:
                                aid = r2.data[0]["id"]
                                supabase.table("alunos").update(payload_base).eq(
                                    "id", aid
                                ).execute()
                                return aid
                        except Exception:
                            pass
                    continue
                raise
        if last_err:
            raise last_err
        raise RuntimeError("Falha ao gravar aluno")

    aluno_id = _gravar_base(aluno_id)

    re_val = (re_aluno or "").strip()
    if re_val and re_val.lower() not in ("nan", "none"):
        try:
            supabase.table("alunos").update({"re": re_val}).eq("id", aluno_id).execute()
        except Exception:
            pass

    return aluno_id
