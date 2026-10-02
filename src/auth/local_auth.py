"""Autenticacao local pela tabela usuarios."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime
from types import SimpleNamespace
from typing import Any

from src.config.database import supabase

_APP_PEPPER = "doc_conecta_v1"

SQL_SETUP = (
    "ALTER TABLE public.usuarios ADD COLUMN IF NOT EXISTS role text DEFAULT 'operacional';\n"
    "ALTER TABLE public.usuarios ADD COLUMN IF NOT EXISTS password_hash text;\n"
    "ALTER TABLE public.usuarios DROP CONSTRAINT IF EXISTS users_id_fkey;\n"
    "ALTER TABLE public.usuarios DISABLE ROW LEVEL SECURITY;\n"
)


def hash_senha(senha: str, salt: str | None = None) -> str:
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        (senha + _APP_PEPPER).encode("utf-8"),
        salt.encode("utf-8"),
        120_000,
    )
    return f"pbkdf2${salt}${dk.hex()}"


def verificar_senha(senha: str, password_hash: str | None) -> bool:
    if not password_hash or not senha:
        return False
    try:
        partes = str(password_hash).split("$")
        if len(partes) != 3 or partes[0] != "pbkdf2":
            return False
        _, salt, esperado = partes
        novo = hash_senha(senha, salt=salt)
        return hmac.compare_digest(novo, f"pbkdf2${salt}${esperado}")
    except Exception:
        return False


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def listar_usuarios() -> tuple[list[dict[str, Any]], str | None]:
    try:
        res = supabase.table("usuarios").select("*").execute()
        rows = res.data if res and isinstance(res.data, list) else []
        return rows, None
    except Exception as e:
        return [], f"Erro ao ler tabela usuarios: {e}"


def buscar_por_email(email: str) -> tuple[dict[str, Any] | None, str | None]:
    email_n = _normalize_email(email)
    if not email_n:
        return None, "E-mail vazio."

    # 1) filtro direto no PostgREST
    try:
        res = (
            supabase.table("usuarios")
            .select("*")
            .eq("email", email_n)
            .limit(1)
            .execute()
        )
        if res and res.data:
            return res.data[0], None
    except Exception:
        pass

    # 2) tenta com o texto original (caso esteja salvo com maiúsculas)
    try:
        res = (
            supabase.table("usuarios")
            .select("*")
            .eq("email", email.strip())
            .limit(1)
            .execute()
        )
        if res and res.data:
            return res.data[0], None
    except Exception:
        pass

    # 3) varredura completa (normalizando)
    rows, err = listar_usuarios()
    if err:
        return None, err

    if not rows:
        return (
            None,
            "Nenhum usuário visível na tabela usuarios (0 registros retornados). "
            "Isso costuma ser RLS ou SUPABASE_URL/KEY diferentes no Streamlit Cloud. "
            "Confira os Secrets do app e rode:\n\n" + SQL_SETUP,
        )

    for row in rows:
        if _normalize_email(str(row.get("email") or "")) == email_n:
            return row, None

    # ajuda a achar typo sem expor senha
    emails = sorted(
        {
            _normalize_email(str(r.get("email") or ""))
            for r in rows
            if r.get("email")
        }
    )
    amostra = ", ".join(emails[:8])
    extra = f" (+{len(emails) - 8} outros)" if len(emails) > 8 else ""
    return (
        None,
        f"E-mail não encontrado. Digitou: `{email_n}`. "
        f"Há {len(emails)} e-mail(s) cadastrado(s): {amostra}{extra}.",
    )


def autenticar(
    email: str, senha: str
) -> tuple[SimpleNamespace | None, dict | None, str | None]:
    perfil, err = buscar_por_email(email)
    if err and perfil is None and "Digitou:" not in (err or "") and "Nenhum usuário" not in (err or ""):
        # erro tecnico de leitura
        if "Erro ao ler" in err or "0 registros" in err:
            return None, None, err

    if err and perfil is None:
        return None, None, err

    if not perfil:
        return None, None, "E-mail não encontrado na tabela usuarios."

    if perfil.get("is_active") is False:
        return None, None, "Usuário inativo. Contate o administrador."

    pwd_hash = perfil.get("password_hash")
    if not pwd_hash:
        return (
            None,
            None,
            "Usuário sem senha local. Admin: Editar usuário e definir nova senha.",
        )

    if not verificar_senha(senha, pwd_hash):
        return None, None, "Senha incorreta."

    user = SimpleNamespace(id=perfil.get("id"), email=perfil.get("email"))
    return user, perfil, None


def _criar_no_auth_supabase(email: str, senha: str) -> str | None:
    try:
        response = supabase.auth.sign_up({"email": email, "password": senha})
        if response and response.user and response.user.id:
            return str(response.user.id)
    except Exception:
        try:
            response = supabase.auth.sign_in_with_password(
                {"email": email, "password": senha}
            )
            if response and response.user and response.user.id:
                return str(response.user.id)
        except Exception:
            return None
    return None


def criar_usuario(
    nome: str,
    email: str,
    senha: str,
    phone: str | None = None,
    role: str = "operacional",
) -> tuple[dict | None, str | None]:
    email_n = _normalize_email(email)
    existente, err_tech = buscar_por_email(email_n)

    # se o "erro" for so not found com lista, existente continua None
    if existente:
        if not existente.get("password_hash"):
            try:
                supabase.table("usuarios").update(
                    {
                        "password_hash": hash_senha(senha),
                        "role": role,
                        "nome": nome.strip(),
                        "phone": phone.strip() if phone else existente.get("phone"),
                        "is_active": True,
                        "updated_at": datetime.now().isoformat(),
                    }
                ).eq("id", existente["id"]).execute()
                return existente, None
            except Exception as e:
                return None, f"Usuário já existia sem senha e falhou ao atualizar: {e}"
        return None, "Já existe um usuário com este e-mail."

    if err_tech and ("Erro ao ler" in err_tech or "0 registros" in err_tech):
        return None, err_tech

    uid = _criar_no_auth_supabase(email_n, senha) or str(uuid.uuid4())

    payload = {
        "id": uid,
        "nome": nome.strip(),
        "email": email_n,
        "phone": phone.strip() if phone else None,
        "is_active": True,
        "role": role,
        "password_hash": hash_senha(senha),
        "updated_at": datetime.now().isoformat(),
    }

    try:
        res = supabase.table("usuarios").insert(payload).execute()
        if res and res.data:
            return res.data[0], None
        conf, _ = buscar_por_email(email_n)
        if conf and not str(conf.get("email", "")).startswith("E-mail"):
            # conf is user dict
            if conf.get("id"):
                return conf, None
        return payload, None
    except Exception as e:
        msg = str(e).lower()

        if "foreign key" in msg or "fkey" in msg or "violates" in msg:
            payload2 = dict(payload)
            payload2.pop("id", None)
            try:
                res2 = supabase.table("usuarios").insert(payload2).execute()
                if res2 and res2.data:
                    return res2.data[0], None
            except Exception as e2:
                return (
                    None,
                    f"FK bloqueando insert: {e2}\n\nRode no SQL:\n"
                    "ALTER TABLE public.usuarios DROP CONSTRAINT IF EXISTS users_id_fkey;\n\n"
                    + SQL_SETUP,
                )

        if "password_hash" in msg or "role" in msg or "column" in msg:
            return None, "Falta coluna.\n\n" + SQL_SETUP

        if "row-level security" in msg or "rls" in msg or "42501" in msg:
            return None, "RLS bloqueou INSERT.\n\n" + SQL_SETUP

        return None, f"Erro ao inserir: {e}\n\n" + SQL_SETUP


def atualizar_senha(usuario_id: str, nova_senha: str) -> tuple[bool, str]:
    try:
        supabase.table("usuarios").update(
            {
                "password_hash": hash_senha(nova_senha),
                "updated_at": datetime.now().isoformat(),
            }
        ).eq("id", usuario_id).execute()
        return True, "Senha atualizada."
    except Exception as e:
        return False, f"{e}\n\n" + SQL_SETUP
