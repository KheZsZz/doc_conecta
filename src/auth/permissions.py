"""Papeis e permissoes de acesso as paginas do sistema."""
from __future__ import annotations

from typing import Any

import streamlit as st

from src.config.database import supabase

ROLE_ADMIN = "admin"
ROLE_OPERACIONAL = "operacional"
ROLE_CONSULTA = "consulta"

ROLES = [ROLE_ADMIN, ROLE_OPERACIONAL, ROLE_CONSULTA]

ROLE_LABELS = {
    ROLE_ADMIN: "Administrador",
    ROLE_OPERACIONAL: "Operacional",
    ROLE_CONSULTA: "Adm. de CT (Consulta)",
}

ROLE_HELP = {
    ROLE_ADMIN: "Acesso total, inclusive gestão de usuários.",
    ROLE_OPERACIONAL: "Cadastros operacionais, turmas, emissão e listas. Sem gestão de usuários.",
    ROLE_CONSULTA: (
        "Administrador de CT: Home, Turmas do seu CT, Imprimir Documentação, "
        "Alunos e Configs. Vê apenas o centro de treinamento vinculado."
    ),
}

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
        "emissao_ead",
        "pacote_grupo",
        "imprimir_documentacao",
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
        "emissao_ead",
        "pacote_grupo",
        "imprimir_documentacao",
        "mcdonalds",
        "configs",
    },
    ROLE_CONSULTA: {
        "home",
        "turmas",
        "imprimir_documentacao",
        "alunos",
        "configs",
    },
}


def normalizar_role(role: str | None) -> str:
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


def is_consulta() -> bool:
    return role_atual() == ROLE_CONSULTA


def ct_id_atual() -> str | None:
    """CT vinculado ao usuário (perfil consulta). Admin/operacional retorna None."""
    perfil = st.session_state.get("perfil") or {}
    cid = perfil.get("ct_id")
    if cid:
        return str(cid)
    return None


def exigir_permissao(pagina: str) -> None:
    if not tem_permissao(pagina):
        st.error("Você não tem permissão para acessar esta página.")
        st.caption(f"Seu perfil: **{ROLE_LABELS.get(role_atual(), role_atual())}**")
        st.stop()
