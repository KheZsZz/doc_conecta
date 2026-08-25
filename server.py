import streamlit as st
from src.config.database import supabase
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

st.set_page_config(page_title="CRM - Emissão de Documentos", page_icon="🔥", layout="wide")

if 'user' not in st.session_state:
    st.session_state.user = None

# Lê os parâmetros da URL (ex: ?page=checkin)
query_params = st.query_params
pagina_atual = query_params.get("page")

# Páginas
login_page = st.Page("src/pages/public/login.py", title="Login", icon="🔑")
signup_page = st.Page("src/pages/private/signup.py", title="Cadastro Admin", icon="📝")
checkin_page = st.Page("src/pages/public/cadastro_aluno.py", title="Check-in Aluno", icon="📱")

home_page = st.Page("src/pages/private/home.py", title="Home", icon="🏠", default=True)
turmas_page = st.Page("src/pages/private/turmas.py", title="Turmas", icon="📅")
clients_page = st.Page("src/pages/private/empresas.py", title="Empresas / Clientes", icon="🏢")
cursos_page = st.Page("src/pages/private/cursos.py", title="Cursos", icon="📚")
instrutores_page = st.Page("src/pages/private/instrutores.py", title="Instrutores", icon="👨‍🏫")
cts_page = st.Page("src/pages/private/cts.py", title="CTS", icon="📝")
alunos_page = st.Page("src/pages/private/alunos.py", title="Alunos", icon="👨‍🎓")

# Roteamento
if pagina_atual == "checkin":
    pg = st.navigation([checkin_page])
elif st.session_state.user is None:
    pg = st.navigation({"Acesso": [login_page]})
else:
    pg = st.navigation({
        "Principal": [home_page],
        "Operacional": [clients_page, cursos_page, turmas_page, instrutores_page, cts_page],
        "cadastro": [signup_page, alunos_page]
    })
    
    with st.sidebar:
        st.write(f"👤 {st.session_state.user.email}")
        if st.button("Sair"):
            supabase.auth.sign_out()
            st.session_state.user = None
            st.rerun()

pg.run()