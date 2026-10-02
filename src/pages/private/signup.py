from datetime import datetime

import streamlit as st

from src.config.database import supabase

st.title("👤 Gestão de Usuários")
st.markdown("Cadastre, liste, edite e remova os usuários com acesso ao sistema.")

tab_listar, tab_cadastrar = st.tabs(["📋 Usuários Cadastrados", "➕ Cadastrar Usuário"])


# ==========================================================================
# Modal de edição
# ==========================================================================
@st.dialog("✏️ Editar Usuário", width="medium")
def modal_editar_usuario(usuario_id, nome_atual, email_atual, phone_atual, ativo_atual):
    st.caption(f"E-mail de login: **{email_atual or '—'}** (não editável)")

    with st.form(f"form_edit_usuario_{usuario_id}"):
        novo_nome = st.text_input("Nome Completo*", value=nome_atual or "")
        novo_phone = st.text_input("Telefone", value=phone_atual or "")
        novo_ativo = st.checkbox("Usuário ativo", value=bool(ativo_atual))

        salvar = st.form_submit_button(
            "💾 Salvar Alterações", type="primary", use_container_width=True
        )

        if salvar:
            if not novo_nome.strip():
                st.warning("⚠️ O nome é obrigatório.")
            else:
                try:
                    payload = {
                        "nome": novo_nome.strip(),
                        "phone": novo_phone.strip() if novo_phone else None,
                        "is_active": novo_ativo,
                        "updated_at": datetime.now().isoformat(),
                    }
                    supabase.table("usuarios").update(payload).eq(
                        "id", usuario_id
                    ).execute()
                    st.success("✅ Usuário atualizado com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Erro ao atualizar: {e}")


# ==========================================================================
# Modal de remoção
# ==========================================================================
@st.dialog("🗑️ Remover Usuário", width="small")
def modal_remover_usuario(usuario_id, nome, email):
    st.warning(
        f"Você está prestes a **remover permanentemente** o usuário:\n\n"
        f"**{nome}**\n"
        f"E-mail: `{email or '—'}`"
    )
    st.caption(
        "Isso apaga o registro na tabela de usuários. "
        "A conta de autenticação (login) pode continuar existindo no Supabase Auth."
    )

    confirmar = st.checkbox(
        "Confirmo a exclusão deste usuário",
        key=f"conf_del_user_{usuario_id}",
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button(
            "Cancelar",
            use_container_width=True,
            key=f"btn_cancel_del_{usuario_id}",
        ):
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
                # Remove registro da tabela usuarios
                supabase.table("usuarios").delete().eq("id", usuario_id).execute()

                # Tenta remover do Auth (só funciona com service_role / admin API)
                try:
                    if hasattr(supabase.auth, "admin"):
                        supabase.auth.admin.delete_user(usuario_id)
                except Exception:
                    pass  # Auth pode exigir chave de serviço — ignora se falhar

                st.success(f"✅ Usuário **{nome}** removido.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Erro ao remover: {e}")


# ==========================================================================
# ABA 1 — Listagem + busca
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
                    status = "🟢 Ativo" if ativo else "🔴 Inativo"

                    with st.container(border=True):
                        col_info, col_edit, col_del = st.columns([4, 1.2, 1.2])

                        with col_info:
                            st.markdown(f"**{nome}** · {status}")
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
                                    uid, nome, email, phone, ativo
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
    st.subheader("Cadastrar Usuário")
    st.caption(
        "Cria a conta de acesso (login) e o registro na tabela de usuários."
    )

    with st.form("form_cadastro_usuario", clear_on_submit=True):
        nome = st.text_input("Nome Completo*")
        phone = st.text_input("Telefone")
        email = st.text_input("E-mail*")

        st.markdown("---")
        senha = st.text_input(
            "Senha*",
            type="password",
            help="A senha deve ter no mínimo 6 caracteres.",
        )
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
                try:
                    response = supabase.auth.sign_up(
                        {"email": email.strip(), "password": senha}
                    )

                    if response.user:
                        dados_usuario = {
                            "id": response.user.id,
                            "nome": nome.strip(),
                            "email": email.strip(),
                            "phone": phone.strip() if phone else None,
                            "is_active": True,
                            "updated_at": datetime.now().isoformat(),
                        }
                        supabase.table("usuarios").insert(dados_usuario).execute()
                        st.success(
                            f"✅ Usuário **{nome}** cadastrado com sucesso!"
                        )
                        st.balloons()
                    else:
                        st.error(
                            "Erro desconhecido ao criar usuário. Tente novamente."
                        )

                except Exception as e:
                    st.error(f"❌ Erro ao criar conta: {e}")
