from datetime import datetime

import streamlit as st

from src.config.database import supabase
from src.auth.local_auth import atualizar_senha, criar_usuario
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
    "Cadastre, liste, edite e defina o **perfil de acesso** de cada usuário. "
    "O login **não depende** do Auth do Supabase (sem confirmação de e-mail)."
)

with st.expander("ℹ️ O que cada perfil pode fazer", expanded=False):
    for r in ROLES:
        st.markdown(f"- **{ROLE_LABELS[r]}** (`{r}`): {ROLE_HELP[r]}")

tab_listar, tab_cadastrar = st.tabs(["📋 Usuários Cadastrados", "➕ Cadastrar Usuário"])


def _opcoes_role() -> list[str]:
    return [ROLE_LABELS[r] for r in ROLES]


def _label_para_role(label: str) -> str:
    for r, lab in ROLE_LABELS.items():
        if lab == label:
            return r
    return ROLE_OPERACIONAL


# ==========================================================================
# Modal de edição
# ==========================================================================
@st.dialog("✏️ Editar Usuário", width="medium")
def modal_editar_usuario(
    usuario_id, nome_atual, email_atual, phone_atual, ativo_atual, role_atual_user
):
    st.caption(f"E-mail de login: **{email_atual or '—'}**")

    with st.form(f"form_edit_usuario_{usuario_id}"):
        novo_nome = st.text_input("Nome Completo*", value=nome_atual or "")
        novo_phone = st.text_input("Telefone", value=phone_atual or "")
        novo_ativo = st.checkbox("Usuário ativo", value=bool(ativo_atual))

        role_norm = normalizar_role(role_atual_user)
        idx = ROLES.index(role_norm) if role_norm in ROLES else 1
        novo_role_label = st.selectbox(
            "Perfil de acesso*",
            options=_opcoes_role(),
            index=idx,
        )
        st.caption(ROLE_HELP.get(_label_para_role(novo_role_label), ""))

        st.markdown("---")
        st.caption("Deixe em branco para **manter** a senha atual.")
        nova_senha = st.text_input("Nova senha (opcional)", type="password")
        conf_senha = st.text_input("Confirmar nova senha", type="password")

        salvar = st.form_submit_button(
            "💾 Salvar Alterações", type="primary", use_container_width=True
        )

        if salvar:
            if not novo_nome.strip():
                st.warning("⚠️ O nome é obrigatório.")
            elif nova_senha and len(nova_senha) < 6:
                st.warning("⚠️ A nova senha deve ter no mínimo 6 caracteres.")
            elif nova_senha and nova_senha != conf_senha:
                st.warning("⚠️ Confirmação de senha não confere.")
            else:
                try:
                    payload = {
                        "nome": novo_nome.strip(),
                        "phone": novo_phone.strip() if novo_phone else None,
                        "is_active": novo_ativo,
                        "role": _label_para_role(novo_role_label),
                        "updated_at": datetime.now().isoformat(),
                    }
                    supabase.table("usuarios").update(payload).eq(
                        "id", usuario_id
                    ).execute()

                    if nova_senha:
                        ok, msg = atualizar_senha(usuario_id, nova_senha)
                        if not ok:
                            st.error(f"Dados salvos, mas senha falhou: {msg}")
                            return

                    st.success("✅ Usuário atualizado com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Erro ao atualizar: {e}")
                    st.code(
                        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS role text DEFAULT 'operacional';\n"
                        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS password_hash text;",
                        language="sql",
                    )


# ==========================================================================
# Modal de remoção
# ==========================================================================
@st.dialog("🗑️ Remover Usuário", width="small")
def modal_remover_usuario(usuario_id, nome, email):
    st.warning(
        f"Remover permanentemente:\n\n**{nome}**\n`{email or '—'}`"
    )

    confirmar = st.checkbox(
        "Confirmo a exclusão deste usuário",
        key=f"conf_del_user_{usuario_id}",
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Cancelar", use_container_width=True, key=f"btn_cancel_del_{usuario_id}"):
            st.rerun()
    with col2:
        if st.button(
            "🗑️ Remover",
            type="primary",
            disabled=not confirmar,
            use_container_width=True,
            key=f"btn_confirm_del_{usuario_id}",
        ):
            try:
                supabase.table("usuarios").delete().eq("id", usuario_id).execute()
                st.success(f"✅ Usuário **{nome}** removido.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Erro ao remover: {e}")


# ==========================================================================
# ABA 1 — Listagem
# ==========================================================================
with tab_listar:
    st.subheader("Usuários do sistema")

    busca = st.text_input(
        "🔍 Buscar por nome, e-mail ou telefone",
        placeholder="Digite para filtrar...",
        key="busca_usuario",
    )

    try:
        res = supabase.table("usuarios").select("*").order("nome").execute()

        if res and isinstance(res.data, list) and len(res.data) > 0:
            lista = res.data

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
                st.info("Nenhum usuário encontrado com esse filtro.")
            else:
                st.caption(f"Exibindo **{len(lista)}** usuário(s).")

                for u in lista:
                    uid = u.get("id")
                    nome = u.get("nome") or "Sem nome"
                    email = u.get("email") or "—"
                    phone = u.get("phone") or ""
                    ativo = u.get("is_active", True)
                    role_u = normalizar_role(u.get("role"))
                    tem_senha = bool(u.get("password_hash"))
                    status = "🟢 Ativo" if ativo else "🔴 Inativo"
                    role_badge = ROLE_LABELS.get(role_u, role_u)
                    senha_flag = "🔑 OK" if tem_senha else "⚠️ Sem senha local"

                    with st.container(border=True):
                        col_info, col_edit, col_del = st.columns([4, 1.2, 1.2])

                        with col_info:
                            st.markdown(
                                f"**{nome}** · {status} · 🏷️ **{role_badge}** · {senha_flag}"
                            )
                            detalhes = [f"📧 {email}"]
                            if phone:
                                detalhes.append(f"📞 {phone}")
                            st.caption(" · ".join(detalhes))

                        with col_edit:
                            st.markdown(
                                "<div style='height: 6px;'></div>",
                                unsafe_allow_html=True,
                            )
                            if st.button(
                                "✏️ Editar",
                                key=f"edit_user_{uid}",
                                use_container_width=True,
                            ):
                                modal_editar_usuario(
                                    uid, nome, email, phone, ativo, role_u
                                )

                        with col_del:
                            st.markdown(
                                "<div style='height: 6px;'></div>",
                                unsafe_allow_html=True,
                            )
                            if st.button(
                                "🗑️ Remover",
                                key=f"del_user_{uid}",
                                use_container_width=True,
                            ):
                                modal_remover_usuario(uid, nome, email)
        else:
            st.info("ℹ️ Nenhum usuário cadastrado ainda.")

    except Exception as e:
        st.error(f"Erro ao carregar usuários: {e}")


# ==========================================================================
# ABA 2 — Cadastro
# ==========================================================================
with tab_cadastrar:
    if not is_admin():
        st.error("Apenas administradores podem cadastrar usuários.")
        st.stop()

    st.subheader("Cadastrar Usuário")
    st.caption(
        "Cria o usuário na tabela local. Ele já consegue logar na hora, "
        "sem e-mail de confirmação."
    )

    with st.form("form_cadastro_usuario", clear_on_submit=True):
        nome = st.text_input("Nome Completo*")
        phone = st.text_input("Telefone")
        email = st.text_input("E-mail*")

        role_label = st.selectbox(
            "Perfil de acesso*",
            options=_opcoes_role(),
            index=1,
        )
        st.caption(ROLE_HELP.get(_label_para_role(role_label), ""))

        st.markdown("---")
        senha = st.text_input("Senha*", type="password", help="Mínimo 6 caracteres.")
        confirmar_senha = st.text_input("Confirmar Senha*", type="password")

        submit = st.form_submit_button(
            "✅ Cadastrar Usuário", type="primary", use_container_width=True
        )

        if submit:
            if not email or not senha or not nome:
                st.warning("⚠️ Preencha todos os campos obrigatórios (*).")
            elif senha != confirmar_senha:
                st.warning("⚠️ As senhas não coincidem.")
            elif len(senha) < 6:
                st.warning("⚠️ A senha deve ter no mínimo 6 caracteres.")
            else:
                registro, erro = criar_usuario(
                    nome=nome,
                    email=email,
                    senha=senha,
                    phone=phone,
                    role=_label_para_role(role_label),
                )
                if erro:
                    st.error(f"❌ {erro}")
                    if "ALTER TABLE" in erro:
                        st.code(
                            "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS role text DEFAULT 'operacional';\n"
                            "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS password_hash text;",
                            language="sql",
                        )
                else:
                    st.success(
                        f"✅ Usuário **{nome}** cadastrado como **{role_label}**. "
                        f"Já pode fazer login com **{email.strip().lower()}**."
                    )
                    st.balloons()
