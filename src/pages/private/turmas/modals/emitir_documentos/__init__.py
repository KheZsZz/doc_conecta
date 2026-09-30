from typing import Any

import streamlit as st

from .data import fetch_turma, fetch_curso
from .responsavel import ui_selecionar_responsavel
from .atestado import gerar_atestado
from .certificado_empresa import gerar_certificado_empresa
from .certificados_individuais import gerar_certificados_individuais
from .lista_presenca import gerar_lista_presenca


@st.dialog("📄 Emitir Documentos", width="large")
def modal_emitir_documentacao(tid, titulo_turma, client_id, ct_id=None):
    st.write(f"**Turma:** {titulo_turma}")

    turma_data = fetch_turma(tid)
    curso_data = fetch_curso(turma_data.get("curso_id"))
    exige_atestado = curso_data.get("exige_atestado", True)

    st.markdown("Selecione o documento desejado para emissão:")
    st.markdown("---")

    opcoes = [
        "Certificado da Empresa",
        "Certificados Individuais (Alunos)",
        "Lista de Presença",
    ]
    if exige_atestado:
        opcoes.insert(0, "Atestado de Brigada (Empresa)")
    else:
        st.info("ℹ️ Este curso está configurado para **NÃO emitir Atestado**.")

    tipo = st.selectbox("Tipo de Documento", opcoes)

    dados_resp: dict[str, Any] = {}
    if tipo in ("Certificado da Empresa", "Certificados Individuais (Alunos)"):
        dados_resp = ui_selecionar_responsavel(tid, tipo)
        st.markdown("---")

    if tipo == "Atestado de Brigada (Empresa)":
        gerar_atestado(tid, titulo_turma, client_id, ct_id, turma_data, curso_data)

    elif tipo == "Certificado da Empresa":
        gerar_certificado_empresa(
            tid, titulo_turma, client_id, ct_id, turma_data, curso_data, dados_resp
        )

    elif tipo == "Certificados Individuais (Alunos)":
        gerar_certificados_individuais(
            tid, titulo_turma, client_id, ct_id, turma_data, curso_data, dados_resp
        )

    elif tipo == "Lista de Presença":
        gerar_lista_presenca(tid, titulo_turma)