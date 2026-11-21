# database.py
"""Cliente Supabase do app Streamlit.

Use SEMPRE a chave **anon** (public) com RLS habilitado no projeto.
Nunca coloque a service_role nos secrets do Streamlit — ela bypassa RLS.
"""
import streamlit as st
from supabase import create_client, Client


@st.cache_resource
def init_connection() -> Client:
    url: str = st.secrets["SUPABASE_URL"]
    # Preferir anon; SUPABASE_KEY mantido só por compatibilidade legada
    key: str = st.secrets.get("SUPABASE_ANON_KEY") or st.secrets.get("SUPABASE_KEY")
    if not key:
        raise RuntimeError(
            "Defina SUPABASE_ANON_KEY (recomendado) ou SUPABASE_KEY nos secrets."
        )
    return create_client(url, key)


supabase = init_connection()
