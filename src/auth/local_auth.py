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
        return [], str(e)


def buscar_por_email(email: str) -> tuple[dict[str, Any] | None, str | None]:
    email_n = _normalize_email(email)
    if not email_n:
        return None, "E-mail vazio."

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

    rows, err = listar_usuarios()
    if err:
        return None, "Não foi possível acessar os usuários. Verifique a conexão com o banco."

    if not rows:
        return None, "Nenhum usuário encontrado no sistema."

    for row in rows:
        if _normalize_email(str(row.get("email") or "")) == email_n:
            return row, None

    return None, None


def _criar_no_auth_supabase(email: str, senha: str) -> str | None:
    try:
        auth = getattr(supabase, "auth", None)
        if not auth:
            return None
        admin = getattr(auth, "admin", None)
        if admin and hasattr(admin, "create_user"):
            r = admin.create_user({"email": email, "password": senha, "email_confirm": True})
            user = getattr(r, "user", None) or (r.get("user") if isinstance(r, dict) else None)
            if user:
                return getattr(user, "id", None) or user.get("id")
    except Exception:
        pass
    return None


def criar_usuario(
    nome: str,
    email: str,
    senha: str,
    phone: str | None = None,
    role: str = "operacional",
    ct_id: str | None = None,
) -> tuple[dict | None, str | None]:
    email_n = _normalize_email(email)
    existente, _ = buscar_por_email(email_n)

    if existente and existente.get("id"):
        if not existente.get("password_hash"):
            try:
                upd = {
                        "password_hash": hash_senha(senha),
                        "role": role,
                        "nome": nome.strip(),
                        "phone": phone.strip() if phone else existente.get("phone"),
                        "is_active": True,
                        "updated_at": datetime.now().isoformat(),
                    }
                if ct_id:
                    upd["ct_id"] = ct_id
                supabase.table("usuarios").update(upd).eq("id", existente["id"]).execute()
                return existente, None
            except Exception as e:
                return None, f"Não foi possível atualizar o usuário: {e}"
        return None, "Já existe um usuário com este e-mail."

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
    if ct_id:
        payload["ct_id"] = ct_id

    try:
        res = supabase.table("usuarios").insert(payload).execute()
        if res and res.data:
            return res.data[0] if isinstance(res.data, list) else res.data, None
        return payload, None
    except Exception as e:
        return None, f"Erro ao criar usuário: {e}"


def atualizar_senha(usuario_id: str, nova_senha: str) -> tuple[bool, str]:
    if not usuario_id or not nova_senha or len(nova_senha) < 6:
        return False, "Senha inválida (mín. 6 caracteres)."
    try:
        supabase.table("usuarios").update(
            {
                "password_hash": hash_senha(nova_senha),
                "updated_at": datetime.now().isoformat(),
            }
        ).eq("id", usuario_id).execute()
        return True, "Senha atualizada."
    except Exception as e:
        return False, str(e)


def autenticar(email: str, senha: str) -> tuple[Any | None, dict | None, str | None]:
    """Retorna (user, perfil_row, erro) — compatível com login.py."""
    row, err = buscar_por_email(email)
    if err and not row:
        return None, None, err
    if not row:
        return None, None, "E-mail ou senha inválidos."
    if not row.get("is_active", True):
        return None, None, "Usuário inativo."
    if not verificar_senha(senha, row.get("password_hash")):
        return None, None, "E-mail ou senha inválidos."

    user = SimpleNamespace(
        id=row.get("id"),
        email=row.get("email"),
        user_metadata={"nome": row.get("nome")},
    )
    return user, row, None
