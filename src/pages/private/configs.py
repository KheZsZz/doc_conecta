import streamlit as st

from src.config.database import supabase

st.title("⚙️ Configurações")
st.markdown("Ajustes da sua conta e preferências do sistema.")

usuario = st.session_state.get("user")
email_logado = getattr(usuario, "email", None) if usuario else None

if not email_logado:
    st.warning("Sessão inválida. Faça login novamente.")
    st.stop()

st.info(f"Conta logada: **{email_logado}**")

st.markdown("---")
st.subheader("🔑 Alterar minha senha")
st.caption(
    "Informe a senha atual e a nova senha. Após salvar, use a nova senha no próximo login."
)

with st.form("form_alterar_senha", clear_on_submit=True):
    senha_atual = st.text_input("Senha atual*", type="password")
    nova_senha = st.text_input(
        "Nova senha*",
        type="password",
        help="Mínimo de 6 caracteres.",
    )
    confirmar = st.text_input("Confirmar nova senha*", type="password")

    enviar = st.form_submit_button(
        "💾 Salvar nova senha", type="primary", use_container_width=True
    )

    if enviar:
        if not senha_atual or not nova_senha or not confirmar:
            st.warning("⚠️ Preencha todos os campos.")
        elif len(nova_senha) < 6:
            st.warning("⚠️ A nova senha deve ter no mínimo 6 caracteres.")
        elif nova_senha != confirmar:
            st.warning("⚠️ A confirmação não confere com a nova senha.")
        elif nova_senha == senha_atual:
            st.warning("⚠️ A nova senha deve ser diferente da atual.")
        else:
            try:
                # Confirma a senha atual reautenticando
                supabase.auth.sign_in_with_password(
                    {"email": email_logado, "password": senha_atual}
                )

                # Atualiza a senha da sessão atual
                supabase.auth.update_user({"password": nova_senha})

                st.success("✅ Senha alterada com sucesso!")
                st.caption("No próximo login, use a nova senha.")

            except Exception as e:
                msg = str(e).lower()
                if "invalid" in msg or "credentials" in msg or "password" in msg:
                    st.error("❌ Senha atual incorreta.")
                else:
                    st.error(f"❌ Não foi possível alterar a senha: {e}")

st.markdown("---")
st.subheader("🚪 Sair do sistema")
st.caption("Encerra a sessão atual e volta para a tela de login.")

if st.button("🚪 Logout", type="primary", use_container_width=True):
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    st.session_state.user = None
    st.rerun()
