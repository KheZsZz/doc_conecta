import streamlit as st

from src.auth.local_auth import autenticar
from src.auth.permissions import normalizar_role

st.title("Acesso ao Sistema")

with st.form("form_login"):
    email = st.text_input("E-mail")
    senha = st.text_input("Senha", type="password")
    submit = st.form_submit_button("Entrar", type="primary")

    if submit:
        if not email or not senha:
            st.warning("Informe e-mail e senha.")
        else:
            user, perfil, erro = autenticar(email.strip(), senha)
            if erro or not user:
                st.error(erro or "Não foi possível entrar.")
            else:
                st.session_state.user = user
                st.session_state.perfil = perfil or {}
                st.session_state.role = normalizar_role((perfil or {}).get("role"))
                st.rerun()
