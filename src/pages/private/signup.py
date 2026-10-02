from datetime import datetime

import streamlit as st

from src.config.database import supabase

st.title("👤 Gestão de Usuários")
st.markdown("Cadastre, liste e pesquise os usuários com acesso ao sistema.")

tab_listar, tab_cadastrar = st.tabs(["📋 Usuários Cadastrados", "➕ Cadastrar Usuário"])


# ==========================================================================
# Modal de edição
# ==========================================================================
@st.dialog("✏️ Editar Usuário", width="medium")
def modal_editar_usuario(usuario_id, nome_atual, email_atual, phone_atual, ativo_atual):
    with st.form(f"form_edit_usuario_{usuario_id}"):
        novo_nome = st.text_input("Nome Completo*", value=nome_atual or "")
        novo_email = st.text_input(
            "E-mail",
            value=email_atual or "",
            disabled=True,
            help="O e-mail de login não pode ser alterado por aqui.",
        )
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
        res = (
            supabase.table("usuarios")
            .select("*")
            .order("nome")
            .execute()
        )

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
                    status = "🟢 **Ativo**" if ativo else "🔴 **Inativo**"

                    with st.container(border=True):
                        col_info, col_acoes = st.columns([5, 1])

                        with col_info:
                            st.markdown(f"**{nome}** — {status}")
                            detalhes = [f"**E-mail:** {email}"]
                            if phone:
                                detalhes.append(f"**Tel:** {phone}")
                            st.caption(" | ".join(detalhes))

                        with col_acoes:
                            st.markdown(
                                "<div style='height: 8px;'></div>",
                                unsafe_allow_html=True,
                            )
                            if st.button(
                                "✏️",
                                key=f"edit_user_{uid}",
                                help="Editar usuário",
                                use_container_width=True,
                            ):
                                modal_editar_usuario(
                                    uid, nome, email, phone, ativo
                                )
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
