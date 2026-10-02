import streamlit as st

from src.config.database import supabase
from src.auth.permissions import sincronizar_perfil_sessao, ROLE_LABELS, normalizar_role

st.title("Acesso ao Sistema")

with st.form("form_login"):
    email = st.text_input("E-mail")
    senha = st.text_input("Senha", type="password")
    submit = st.form_submit_button("Entrar")

    if submit:
        try:
            response = supabase.auth.sign_in_with_password(
                {"email": email, "password": senha}
            )
            user = response.user
            perfil = sincronizar_perfil_sessao(user)

            # Bloqueia usuario inativo (se existir registro)
            if perfil and perfil.get("is_active") is False:
                try:
                    supabase.auth.sign_out()
                except Exception:
                    pass
                st.session_state.user = None
                st.session_state.perfil = None
                st.session_state.role = None
                st.error("⛔ Usuário inativo. Contate o administrador.")
            else:
                st.session_state.user = user
                role = normalizar_role(perfil.get("role") if perfil else None)
                st.session_state.role = role
                st.rerun()
        except Exception:
            st.error("E-mail ou senha incorretos. Tente novamente.")
