import streamlit as st
from src.pages.private.turmas.tab_listar import render_tab_listar
from src.pages.private.turmas.tab_cadastrar import render_tab_cadastrar

st.title("📅 Abertura e Gestão de Turmas")
st.markdown(
    "Abra as turmas do centro de treinamento, importe listas de alunos e emita os documentos."
)

tab_listar, tab_cadastrar = st.tabs(["📋 Turmas Abertas", "➕ Abrir Nova Turma"])

with tab_listar:
    render_tab_listar()

with tab_cadastrar:
    render_tab_cadastrar()