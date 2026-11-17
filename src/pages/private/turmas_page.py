import streamlit as st
from src.pages.private.turmas.tab_listar import render_tab_listar
from src.pages.private.turmas.tab_cadastrar import render_tab_cadastrar
from src.pages.private.turmas.tab_lote import render_tab_lote
from src.pages.private.turmas.tab_buscar import render_tab_buscar
from src.ui.styles import page_header

page_header(
    "Turmas",
    "Abertura, busca e gestão das turmas de treinamento.",
)

tab_listar, tab_buscar, tab_cadastrar, tab_lote = st.tabs(
    [
        "Turmas abertas",
        "Buscar aluno",
        "Abrir nova turma",
        "Turmas em lote",
    ]
)

with tab_listar:
    render_tab_listar()

with tab_buscar:
    render_tab_buscar()

with tab_cadastrar:
    render_tab_cadastrar()

with tab_lote:
    render_tab_lote()
