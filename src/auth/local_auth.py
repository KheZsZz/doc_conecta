"""Autenticacao local pela tabela usuarios.

Login valida password_hash na tabela (sem depender de confirmacao de e-mail).
No cadastro, tenta criar tambem no Supabase Auth so para satisfazer FK id -> auth.users,
quando existir.
"""
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
    "-- 1) Colunas necessarias\n"
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS role text DEFAULT 'operacional';\n"
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS password_hash text;\n\n"
    "-- 2) Se o INSERT falhar por foreign key, remova a FK para auth.users:\n"
    "-- (ajuste o nome da constraint no Table Editor > usuarios > Constraints)\n"
    "-- ALTER TABLE usuarios DROP CONSTRAINT IF EXISTS usuarios_id_fkey;\n\n"
    "-- 3) Politicas RLS (Table Editor > usuarios > RLS): permitir SELECT/INSERT/UPDATE\n"
    "-- para a chave anon/authenticated, ou desative RLS nesta tabela se for app interno.\n"
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


def buscar_por_email(email: str) -> tuple[dict[str, Any] | None, str | None]:
    """Retorna (perfil, erro_tecnico)."""
    email_n = _normalize_email(email)
    if not email_n:
        return None, "E-mail vazio."

    # tenta match exato em lower via filter; depois varre lista se necessario
    try:
        res = supabase.table("usuarios").select("*").execute()
        rows = res.data if res and isinstance(res.data, list) else []
        for row in rows:
            if _normalize_email(str(row.get("email") or "")) == email_n:
                return row, None
        return None, None
    except Exception as e:
        return None, f"Erro ao ler tabela usuarios: {e}"


def autenticar(
    email: str, senha: str
) -> tuple[SimpleNamespace | None, dict | None, str | None]:
    perfil, err_tech = buscar_por_email(email)
    if err_tech:
        return None, None, err_tech + "\n\n" + SQL_SETUP

    if not perfil:
        return (
            None,
            None,
            "E-mail não encontrado na tabela usuarios. "
            "Cadastre o usuário em Gestão de Usuários ou confira o e-mail.",
        )

    if perfil.get("is_active") is False:
        return None, None, "Usuário inativo. Contate o administrador."

    pwd_hash = perfil.get("password_hash")
    if not pwd_hash:
        return (
            None,
            None,
            "Usuário existe, mas está sem senha local (password_hash vazio). "
            "Admin: abra Editar neste usuário e defina uma nova senha.",
        )

    if not verificar_senha(senha, pwd_hash):
        return None, None, "Senha incorreta."

    user = SimpleNamespace(id=perfil.get("id"), email=perfil.get("email"))
    return user, perfil, None


def _criar_no_auth_supabase(email: str, senha: str) -> str | None:
    """Tenta criar no Auth so para obter um UUID valido (FK). Retorna user id ou None."""
    try:
        response = supabase.auth.sign_up({"email": email, "password": senha})
        if response and response.user and response.user.id:
            return str(response.user.id)
    except Exception:
        # usuario ja existe no auth, tenta logar so para pegar id (pode falhar se email nao confirmado)
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
    if err_tech:
        return None, err_tech + "\n\n" + SQL_SETUP
    if existente:
        # se existe mas sem senha, atualiza senha/role
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

    # 1) tenta obter id via Auth (para FK)
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
        # alguns clients retornam data vazia mas inserem
        conf, _ = buscar_por_email(email_n)
        if conf:
            return conf, None
        return payload, None
    except Exception as e:
        msg = str(e).lower()

        # tenta de novo sem id (default do banco)
        if "foreign key" in msg or "fkey" in msg or "violates" in msg:
            payload_sem_id = dict(payload)
            payload_sem_id.pop("id", None)
            try:
                res2 = supabase.table("usuarios").insert(payload_sem_id).execute()
                if res2 and res2.data:
                    return res2.data[0], None
            except Exception as e2:
                return (
                    None,
                    f"Falha de foreign key ao criar usuário.\n"
                    f"Detalhe: {e2}\n\n"
                    f"No Supabase, remova a FK de usuarios.id → auth.users ou "
                    f"crie o usuário no Auth manualmente.\n\n"
                    + SQL_SETUP,
                )

        if "password_hash" in msg or "role" in msg or "column" in msg:
            return None, "Falta coluna no banco.\n\n" + SQL_SETUP

        if "row-level security" in msg or "rls" in msg or "42501" in msg:
            return (
                None,
                "RLS bloqueou o INSERT em usuarios.\n"
                "Desative RLS na tabela usuarios (ou crie policy de INSERT/SELECT)\n\n"
                + SQL_SETUP,
            )

        return None, f"Erro ao inserir usuário: {e}\n\n" + SQL_SETUP


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
