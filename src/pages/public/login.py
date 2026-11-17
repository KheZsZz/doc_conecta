import streamlit as st

from src.auth.local_auth import autenticar
from src.auth.permissions import normalizar_role

st.markdown(
    """
<div class="df-login-wrap">
  <div class="df-login-brand">
    <h1>DocFacil Conecta</h1>
    <p>Acesse com seu e-mail institucional</p>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

_, col, _ = st.columns([1, 1.2, 1])
with col:
    with st.form("form_login", border=True):
        email = st.text_input("E-mail", placeholder="seu@email.com")
        senha = st.text_input("Senha", type="password", placeholder="••••••••")
        submit = st.form_submit_button("Entrar", type="primary", width="stretch")

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
