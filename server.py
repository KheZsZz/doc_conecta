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
from src.ui.styles import aplicar_estilo_global

root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

st.set_page_config(
    page_title="DocFacil Conecta",
    page_icon=":material/local_fire_department:",
    layout="wide",
    initial_sidebar_state="expanded",
)

aplicar_estilo_global()

if "user" not in st.session_state:
    st.session_state.user = None
if "perfil" not in st.session_state:
    st.session_state.perfil = None
if "role" not in st.session_state:
    st.session_state.role = None

query_params = st.query_params
pagina_atual = query_params.get("page")

login_page = st.Page(
    "src/pages/public/login.py", title="Login", icon=":material/login:"
)
checkin_page = st.Page(
    "src/pages/public/cadastro_aluno.py",
    title="Check-in Aluno",
    icon=":material/how_to_reg:",
)

home_page = st.Page(
    "src/pages/private/home.py",
    title="Home",
    icon=":material/home:",
    default=True,
)
turmas_page = st.Page(
    "src/pages/private/turmas_page.py", title="Turmas", icon=":material/groups:"
)
clients_page = st.Page(
    "src/pages/private/empresas.py",
    title="Empresas / Clientes",
    icon=":material/apartment:",
)
cursos_page = st.Page(
    "src/pages/private/cursos.py", title="Cursos", icon=":material/menu_book:"
)
instrutores_page = st.Page(
    "src/pages/private/instrutores.py",
    title="Instrutores",
    icon=":material/school:",
)
responsaveis_page = st.Page(
    "src/pages/private/responsaveis.py",
    title="Responsáveis Técnicos",
    icon=":material/badge:",
)
cts_page = st.Page(
    "src/pages/private/cts.py", title="CTS", icon=":material/domain:"
)
signup_page = st.Page(
    "src/pages/private/signup.py",
    title="Cadastrar Usuário",
    icon=":material/person_add:",
)
alunos_page = st.Page(
    "src/pages/private/alunos.py", title="Alunos", icon=":material/group:"
)
subir_listas_page = st.Page(
    "src/pages/private/subir_listas.py",
    title="Subir Listas",
    icon=":material/upload_file:",
)
emissao_ead_page = st.Page(
    "src/pages/private/emissao_ead.py",
    title="Emissão EAD",
    icon=":material/computer:",
)
pacote_grupo_page = st.Page(
    "src/pages/private/pacote_grupo.py",
    title="Pacote Período",
    icon=":material/inventory_2:",
)
imprimir_doc_page = st.Page(
    "src/pages/private/imprimir_documentacao.py",
    title="Imprimir Documentação",
    icon=":material/print:",
)
mc_page = st.Page(
    "src/pages/private/mcDonalds.py",
    title="McDonalds",
    icon=":material/restaurant:",
)
configs_page = st.Page(
    "src/pages/private/configs.py",
    title="Configs",
    icon=":material/settings:",
)

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
    "imprimir_documentacao": imprimir_doc_page,
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
        "imprimir_documentacao",
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
        st.markdown(f"**{email}**")
        st.caption(f"Perfil: {label}")
        if st.button("Sair", width="stretch"):
            st.session_state.user = None
            st.session_state.perfil = None
            st.session_state.role = None
            st.rerun()

pg.run()
