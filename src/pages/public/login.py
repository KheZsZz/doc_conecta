import streamlit as st

from src.auth.local_auth import autenticar, SQL_SETUP
from src.auth.permissions import normalizar_role

st.title("Acesso ao Sistema")
st.caption(
    "🔐 Login local v2 — autenticação pela tabela **usuarios** "
    "(não usa confirmação de e-mail do Supabase Auth)."
)

with st.form("form_login_local_v2"):
    email = st.text_input("E-mail", key="login_email_v2")
    senha = st.text_input("Senha", type="password", key="login_senha_v2")
    submit = st.form_submit_button("Entrar", type="primary")

    if submit:
        if not email or not senha:
            st.warning("Informe e-mail e senha.")
        else:
            user, perfil, erro = autenticar(email.strip(), senha)
            if erro or not user:
                st.error(f"❌ {erro or 'Falha no login.'}")
                if erro and (
                    "ALTER TABLE" in erro
                    or "RLS" in erro
                    or "foreign" in erro.lower()
                    or "tabela usuarios" in erro.lower()
                ):
                    with st.expander("SQL / ajustes no Supabase"):
                        st.code(SQL_SETUP, language="sql")
            else:
                st.session_state.user = user
                st.session_state.perfil = perfil or {}
                st.session_state.role = normalizar_role((perfil or {}).get("role"))
                st.success("Login OK — entrando...")
                st.rerun()
