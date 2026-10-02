from datetime import datetime

import streamlit as st

from src.config.database import supabase
from src.auth.local_auth import SQL_SETUP, atualizar_senha, criar_usuario
from src.auth.permissions import (
    ROLE_HELP,
    ROLE_LABELS,
    ROLE_OPERACIONAL,
    ROLES,
    exigir_permissao,
    is_admin,
    normalizar_role,
)

exigir_permissao("usuarios")

st.title("👤 Gestão de Usuários")
st.markdown(
    "Cadastre usuários com **login imediato** (senha na tabela `usuarios`). "
    "Não depende de confirmação de e-mail."
)

with st.expander("ℹ️ Perfis de acesso", expanded=False):
    for r in ROLES:
        st.markdown(f"- **{ROLE_LABELS[r]}**: {ROLE_HELP[r]}")

with st.expander("🛠️ Se cadastro/login falhar — rode no Supabase", expanded=False):
    st.code(SQL_SETUP, language="sql")

tab_listar, tab_cadastrar = st.tabs(["📋 Usuários Cadastrados", "➕ Cadastrar Usuário"])


def _opcoes_role() -> list[str]:
    return [ROLE_LABELS[r] for r in ROLES]


def _label_para_role(label: str) -> str:
    for r, lab in ROLE_LABELS.items():
        if lab == label:
            return r
    return ROLE_OPERACIONAL


@st.dialog("✏️ Editar Usuário", width="medium")
def modal_editar_usuario(
    usuario_id, nome_atual, email_atual, phone_atual, ativo_atual, role_atual_user
):
    st.caption(f"E-mail: **{email_atual or '—'}**")

    with st.form(f"form_edit_usuario_{usuario_id}"):
        novo_nome = st.text_input("Nome Completo*", value=nome_atual or "")
        novo_phone = st.text_input("Telefone", value=phone_atual or "")
        novo_ativo = st.checkbox("Usuário ativo", value=bool(ativo_atual))

        role_norm = normalizar_role(role_atual_user)
        idx = ROLES.index(role_norm) if role_norm in ROLES else 1
        novo_role_label = st.selectbox("Perfil de acesso*", options=_opcoes_role(), index=idx)

        st.markdown("---")
        st.caption("Preencha só se quiser **trocar a senha** (obrigatório se aparecer “Sem senha local”).")
        nova_senha = st.text_input("Nova senha", type="password")
        conf_senha = st.text_input("Confirmar nova senha", type="password")

        salvar = st.form_submit_button("💾 Salvar", type="primary", use_container_width=True)

        if salvar:
            if not novo_nome.strip():
                st.warning("Nome obrigatório.")
            elif nova_senha and len(nova_senha) < 6:
                st.warning("Senha mínima: 6 caracteres.")
            elif nova_senha and nova_senha != conf_senha:
                st.warning("Confirmação de senha não confere.")
            else:
                try:
                    payload = {
                        "nome": novo_nome.strip(),
                        "phone": novo_phone.strip() if novo_phone else None,
                        "is_active": novo_ativo,
                        "role": _label_para_role(novo_role_label),
                        "updated_at": datetime.now().isoformat(),
                    }
                    supabase.table("usuarios").update(payload).eq("id", usuario_id).execute()
                    if nova_senha:
                        ok, msg = atualizar_senha(usuario_id, nova_senha)
                        if not ok:
                            st.error(msg)
                            return
                    st.success("✅ Salvo!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")
                    st.code(SQL_SETUP, language="sql")


@st.dialog("🗑️ Remover Usuário", width="small")
def modal_remover_usuario(usuario_id, nome, email):
    st.warning(f"Remover **{nome}** (`{email}`)?")
    confirmar = st.checkbox("Confirmo", key=f"conf_del_{usuario_id}")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Cancelar", key=f"c_{usuario_id}", use_container_width=True):
            st.rerun()
    with c2:
        if st.button(
            "Remover",
            type="primary",
            disabled=not confirmar,
            key=f"d_{usuario_id}",
            use_container_width=True,
        ):
            try:
                supabase.table("usuarios").delete().eq("id", usuario_id).execute()
                st.success("Removido.")
                st.rerun()
            except Exception as e:
                st.error(str(e))


with tab_listar:
    busca = st.text_input("🔍 Buscar", placeholder="nome, e-mail, telefone...", key="busca_u")
    try:
        res = supabase.table("usuarios").select("*").order("nome").execute()
        lista = res.data if res and isinstance(res.data, list) else []

        if busca.strip():
            q = busca.strip().lower()
            lista = [
                u
                for u in lista
                if q in str(u.get("nome") or "").lower()
                or q in str(u.get("email") or "").lower()
                or q in str(u.get("phone") or "").lower()
                or q in str(u.get("role") or "").lower()
            ]

        if not lista:
            st.info("Nenhum usuário encontrado.")
        else:
            st.caption(f"{len(lista)} usuário(s)")
            for u in lista:
                uid = u.get("id")
                nome = u.get("nome") or "Sem nome"
                email = u.get("email") or "—"
                phone = u.get("phone") or ""
                ativo = u.get("is_active", True)
                role_u = normalizar_role(u.get("role"))
                tem_senha = bool(u.get("password_hash"))
                status = "🟢 Ativo" if ativo else "🔴 Inativo"
                senha_flag = "🔑 OK" if tem_senha else "⚠️ Sem senha local"

                with st.container(border=True):
                    c1, c2, c3 = st.columns([4, 1.2, 1.2])
                    with c1:
                        st.markdown(
                            f"**{nome}** · {status} · 🏷️ **{ROLE_LABELS.get(role_u, role_u)}** · {senha_flag}"
                        )
                        st.caption(
                            " · ".join(
                                [f"📧 {email}"] + ([f"📞 {phone}"] if phone else [])
                            )
                        )
                    with c2:
                        if st.button("✏️ Editar", key=f"e_{uid}", use_container_width=True):
                            modal_editar_usuario(uid, nome, email, phone, ativo, role_u)
                    with c3:
                        if st.button("🗑️ Remover", key=f"r_{uid}", use_container_width=True):
                            modal_remover_usuario(uid, nome, email)
    except Exception as e:
        st.error(f"Erro ao listar: {e}")
        st.code(SQL_SETUP, language="sql")


with tab_cadastrar:
    if not is_admin():
        st.error("Apenas administradores podem cadastrar.")
        st.stop()

    st.subheader("Cadastrar Usuário")
    with st.form("form_novo_user", clear_on_submit=True):
        nome = st.text_input("Nome Completo*")
        phone = st.text_input("Telefone")
        email = st.text_input("E-mail*")
        role_label = st.selectbox("Perfil*", options=_opcoes_role(), index=1)
        st.caption(ROLE_HELP.get(_label_para_role(role_label), ""))
        senha = st.text_input("Senha*", type="password")
        conf = st.text_input("Confirmar Senha*", type="password")
        ok = st.form_submit_button("✅ Cadastrar", type="primary", use_container_width=True)

        if ok:
            if not nome or not email or not senha:
                st.warning("Preencha os campos obrigatórios.")
            elif senha != conf:
                st.warning("Senhas não coincidem.")
            elif len(senha) < 6:
                st.warning("Senha mínima: 6 caracteres.")
            else:
                reg, erro = criar_usuario(
                    nome=nome,
                    email=email,
                    senha=senha,
                    phone=phone,
                    role=_label_para_role(role_label),
                )
                if erro:
                    st.error(erro)
                    st.code(SQL_SETUP, language="sql")
                else:
                    st.success(
                        f"✅ **{nome}** cadastrado. Login: `{email.strip().lower()}` "
                        f"como **{role_label}**."
                    )
                    st.balloons()
