# auth/login.py
import streamlit as st
from src.config.database import supabase

st.title("Acesso ao Sistema")

with st.form("form_login"):
    email = st.text_input("E-mail")
    senha = st.text_input("Senha", type="password")
    submit = st.form_submit_button("Entrar")
    
    if submit:
        try:
            response = supabase.auth.sign_in_with_password({"email": email, "password": senha})
            st.session_state.user = response.user
            st.rerun() # Atualiza o estado e joga para o main.py rotear para o app
        except Exception as e:
            st.error("E-mail ou senha incorretos. Tente novamente.")