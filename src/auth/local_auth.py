"""Autenticacao local pela tabela usuarios (sem Supabase Auth)."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime
from types import SimpleNamespace
from typing import Any

from src.config.database import supabase

# salt fixo da aplicacao + salt aleatorio por usuario (armazenado no hash)
_APP_PEPPER = "doc_conecta_v1"


def hash_senha(senha: str, salt: str | None = None) -> str:
    """
    Retorna string no formato: pbkdf2$<salt_hex>$<hash_hex>
    """
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


def buscar_por_email(email: str) -> dict[str, Any] | None:
    email_n = (email or "").strip().lower()
    if not email_n:
        return None
    try:
        res = (
            supabase.table("usuarios")
            .select("*")
            .ilike("email", email_n)
            .limit(1)
            .execute()
        )
        if res and res.data:
            return res.data[0]
    except Exception:
        # fallback sem ilike
        try:
            res = (
                supabase.table("usuarios")
                .select("*")
                .eq("email", email.strip())
                .limit(1)
                .execute()
            )
            if res and res.data:
                return res.data[0]
        except Exception:
            return None
    return None


def autenticar(email: str, senha: str) -> tuple[SimpleNamespace | None, dict | None, str | None]:
    """
    Autentica na tabela usuarios.
    Retorna (user_obj, perfil, erro).
    """
    perfil = buscar_por_email(email)
    if not perfil:
        return None, None, "E-mail ou senha incorretos."

    if perfil.get("is_active") is False:
        return None, None, "Usuário inativo. Contate o administrador."

    pwd_hash = perfil.get("password_hash")
    if not pwd_hash:
        return (
            None,
            None,
            "Este usuário ainda não tem senha local. "
            "Peça a um admin para redefinir a senha em Cadastrar Usuário → Editar.",
        )

    if not verificar_senha(senha, pwd_hash):
        return None, None, "E-mail ou senha incorretos."

    user = SimpleNamespace(
        id=perfil.get("id"),
        email=perfil.get("email"),
    )
    return user, perfil, None


def criar_usuario(
    nome: str,
    email: str,
    senha: str,
    phone: str | None = None,
    role: str = "operacional",
) -> tuple[dict | None, str | None]:
    """
    Cria usuario apenas na tabela usuarios (sem Supabase Auth).
    Retorna (registro, erro).
    """
    email_n = email.strip().lower()
    existente = buscar_por_email(email_n)
    if existente:
        return None, "Já existe um usuário com este e-mail."

    uid = str(uuid.uuid4())
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
        return payload, None
    except Exception as e:
        msg = str(e)
        # tenta sem colunas novas se o schema ainda não tiver
        if "password_hash" in msg.lower() or "role" in msg.lower():
            return (
                None,
                "Falta coluna no banco. Execute no Supabase:\n"
                "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS role text DEFAULT 'operacional';\n"
                "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS password_hash text;",
            )
        return None, msg


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
        return False, str(e)
