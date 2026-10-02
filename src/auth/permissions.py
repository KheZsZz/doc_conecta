"""Papeis e permissoes de acesso as paginas do sistema."""
from __future__ import annotations

from typing import Any

import streamlit as st

from src.config.database import supabase

# ---------------------------------------------------------------------------
# Papeis disponiveis
# ---------------------------------------------------------------------------
ROLE_ADMIN = "admin"
ROLE_OPERACIONAL = "operacional"
ROLE_CONSULTA = "consulta"

ROLES = [ROLE_ADMIN, ROLE_OPERACIONAL, ROLE_CONSULTA]

ROLE_LABELS = {
    ROLE_ADMIN: "Administrador",
    ROLE_OPERACIONAL: "Operacional",
    ROLE_CONSULTA: "Consulta",
}

ROLE_HELP = {
    ROLE_ADMIN: "Acesso total, inclusive gestão de usuários.",
    ROLE_OPERACIONAL: "Cadastros operacionais, turmas, emissão e listas. Sem gestão de usuários.",
    ROLE_CONSULTA: "Apenas dashboard (Home) e configurações da própria conta.",
}

# Paginas liberadas por papel (chaves internas)
PERMISSOES: dict[str, set[str]] = {
    ROLE_ADMIN: {
        "home",
        "empresas",
        "cursos",
        "turmas",
        "instrutores",
        "cts",
        "responsaveis",
        "usuarios",
        "alunos",
        "subir_listas",
        "mcdonalds",
        "configs",
    },
    ROLE_OPERACIONAL: {
        "home",
        "empresas",
        "cursos",
        "turmas",
        "instrutores",
        "cts",
        "responsaveis",
        "alunos",
        "subir_listas",
        "mcdonalds",
        "configs",
    },
    ROLE_CONSULTA: {
        "home",
        "configs",
    },
}


def normalizar_role(role: str | None) -> str:
    """
    Usuarios antigos sem coluna role (ou null) continuam como admin
    para nao travar o acesso apos o deploy.
    """
    r = (role or "").strip().lower()
    if r in ROLES:
        return r
    return ROLE_ADMIN


def carregar_perfil(user_id: str | None) -> dict[str, Any]:
    if not user_id:
        return {}
    try:
        res = (
            supabase.table("usuarios")
            .select("*")
            .eq("id", user_id)
            .single()
            .execute()
        )
        return res.data if res and res.data else {}
    except Exception:
        return {}


def sincronizar_perfil_sessao(user) -> dict[str, Any]:
    """
    Carrega o perfil do banco e grava em session_state.
    Retorna o perfil (pode ser vazio).
    """
    uid = getattr(user, "id", None)
    perfil = carregar_perfil(uid)
    st.session_state["perfil"] = perfil
    st.session_state["role"] = normalizar_role(perfil.get("role") if perfil else None)
    return perfil


def role_atual() -> str:
    r = st.session_state.get("role")
    if r in ROLES:
        return r
    perfil = st.session_state.get("perfil") or {}
    return normalizar_role(perfil.get("role"))


def tem_permissao(pagina: str) -> bool:
    role = role_atual()
    return pagina in PERMISSOES.get(role, set())


def is_admin() -> bool:
    return role_atual() == ROLE_ADMIN


def exigir_permissao(pagina: str, mensagem: str | None = None) -> None:
    """Bloqueia a pagina se o papel nao tiver acesso."""
    if tem_permissao(pagina):
        return
    st.error(
        mensagem
        or "⛔ Você não tem permissão para acessar esta página."
    )
    st.caption(f"Seu perfil: **{ROLE_LABELS.get(role_atual(), role_atual())}**")
    st.stop()
