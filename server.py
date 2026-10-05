import streamlit as st
from src.config.database import supabase
import sys
from pathlib import Path

from src.auth.permissions import (
    ROLE_LABELS,
    role_atual,
    sincronizar_perfil_sessao,
    tem_permissao,
)

root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

st.set_page_config(
    page_title="CRM - Emissão de Documentos", page_icon="🔥", layout="wide"
)

if "user" not in st.session_state:
    st.session_state.user = None
if "perfil" not in st.session_state:
    st.session_state.perfil = None
if "role" not in st.session_state:
    st.session_state.role = None

query_params = st.query_params
pagina_atual = query_params.get("page")

login_page = st.Page("src/pages/public/login.py", title="Login", icon="🔑")
checkin_page = st.Page(
    "src/pages/public/cadastro_aluno.py", title="Check-in Aluno", icon="📱"
)

home_page = st.Page("src/pages/private/home.py", title="Home", icon="🏠", default=True)
turmas_page = st.Page("src/pages/private/turmas_page.py", title="Turmas", icon="📅")
clients_page = st.Page(
    "src/pages/private/empresas.py", title="Empresas / Clientes", icon="🏢"
)
cursos_page = st.Page("src/pages/private/cursos.py", title="Cursos", icon="📚")
instrutores_page = st.Page(
    "src/pages/private/instrutores.py", title="Instrutores", icon="👨‍🏫"
)
responsaveis_page = st.Page(
    "src/pages/private/responsaveis.py", title="Responsáveis Técnicos", icon="✒️"
)
cts_page = st.Page("src/pages/private/cts.py", title="CTS", icon="📝")
signup_page = st.Page(
    "src/pages/private/signup.py", title="Cadastrar Usuário", icon="👤"
)
alunos_page = st.Page("src/pages/private/alunos.py", title="Alunos", icon="👨‍🎓")
subir_listas_page = st.Page(
    "src/pages/private/subir_listas.py", title="Subir Listas", icon="📤"
)
emissao_ead_page = st.Page(
    "src/pages/private/emissao_ead.py", title="Emissão EAD", icon="🎓"
)
pacote_grupo_page = st.Page(
    "src/pages/private/pacote_grupo.py", title="Pacote Grupo", icon="📦"
)
mc_page = st.Page("src/pages/private/mcDonalds.py", title="mcDonalds", icon="💻")
configs_page = st.Page("src/pages/private/configs.py", title="Configs", icon="⚙️")

PAGINAS = {
    "home": home_page,
    "empresas": clients_page,
    "cursos": cursos_page,
    "turmas": turmas_page,
    "instrutores": instrutores_page,
    "cts": cts_page,
    "responsaveis": responsaveis_page,
    "usuarios": signup_page,
    "alunos": alunos_page,
    "subir_listas": subir_listas_page,
    "emissao_ead": emissao_ead_page,
    "pacote_grupo": pacote_grupo_page,
    "mcdonalds": mc_page,
    "configs": configs_page,
}

GRUPOS = {
    "Principal": ["home"],
    "Operacional": [
        "empresas",
        "cursos",
        "turmas",
        "instrutores",
        "cts",
        "responsaveis",
        "pacote_grupo",
    ],
    "Cadastro": ["usuarios", "alunos", "subir_listas", "emissao_ead"],
    "Específicos": ["mcdonalds"],
    "Configs": ["configs"],
}


def montar_navegacao_por_permissao() -> dict:
    nav: dict[str, list] = {}
    for grupo, chaves in GRUPOS.items():
        paginas = [PAGINAS[k] for k in chaves if tem_permissao(k) and k in PAGINAS]
        if paginas:
            nav[grupo] = paginas
    if not nav:
        nav = {"Principal": [home_page], "Configs": [configs_page]}
    return nav


if pagina_atual == "checkin":
    pg = st.navigation([checkin_page])
elif st.session_state.user is None:
    pg = st.navigation({"Acesso": [login_page]})
else:
    if not st.session_state.get("role"):
        sincronizar_perfil_sessao(st.session_state.user)

    pg = st.navigation(montar_navegacao_por_permissao())

    with st.sidebar:
        email = getattr(st.session_state.user, "email", "")
        role = role_atual()
        label = ROLE_LABELS.get(role, role)
        st.write(f"👤 {email}")
        st.caption(f"Perfil: **{label}**")
        if st.button("Sair"):
            st.session_state.user = None
            st.session_state.perfil = None
            st.session_state.role = None
            st.rerun()

pg.run()
