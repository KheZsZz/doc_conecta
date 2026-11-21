from typing import Any

import streamlit as st

from src.utils.checkin_token import gerar_token, montar_url_checkin

from .data import fetch_turma, fetch_curso
from .responsavel import ui_selecionar_responsavel
from .atestado import gerar_atestado
from .certificado_empresa import gerar_certificado_empresa
from .certificados_individuais import gerar_certificados_individuais
from .lista_presenca import gerar_lista_presenca
from .documentacao_completa import gerar_documentacao_completa
from .carteirinhas import gerar_carteirinhas


@st.dialog("Emitir Documentos", width="large")
def modal_emitir_documentacao(tid, titulo_turma, client_id, ct_id=None):
    st.write(f"**Turma:** {titulo_turma}")

    with st.expander("Link de check-in (alunos)", expanded=False):
        horas = st.slider(
            "Validade do link (horas)",
            min_value=4,
            max_value=168,
            value=48,
            step=4,
            key=f"checkin_horas_{tid}",
        )
        token = gerar_token(str(tid), horas_validade=int(horas))
        # base da URL da sessão Streamlit (quando disponível)
        try:
            base = st.context.headers.get("origin")  # type: ignore[attr-defined]
        except Exception:
            base = None
        if not base:
            base = st.secrets.get("APP_BASE_URL") or ""
        if base:
            url = montar_url_checkin(str(base), token)
            st.code(url, language=None)
            st.caption("Compartilhe apenas com a turma. O link expira após o prazo definido.")
        else:
            st.code(f"?page=checkin&t={token}", language=None)
            st.caption(
                "Defina APP_BASE_URL nos secrets para gerar a URL completa "
                "(ex.: https://seu-app.streamlit.app)."
            )

    turma_data = fetch_turma(tid)
    curso_data = fetch_curso(turma_data.get("curso_id"))
    exige_atestado = curso_data.get("exige_atestado", True)

    st.markdown("Selecione o documento desejado para emissão:")
    st.markdown("---")

    opcoes = [
        "Documentação Completa (tudo em ZIP)",
        "Certificado da Empresa",
        "Certificados Individuais (Alunos)",
        "Carteirinhas (Alunos)",
        "Lista de Presença",
    ]
    if exige_atestado:
        opcoes.insert(1, "Atestado de Brigada (Empresa)")
    else:
        st.info("Este curso está configurado para **NÃO emitir Atestado**.")

    tipo = st.selectbox("Tipo de Documento", opcoes)

    dados_resp: dict[str, Any] = {}
    precisa_resp = tipo in (
        "Documentação Completa (tudo em ZIP)",
        "Certificado da Empresa",
        "Certificados Individuais (Alunos)",
    )
    if precisa_resp:
        dados_resp = ui_selecionar_responsavel(
            tid,
            tipo,
            curso_id=turma_data.get("curso_id"),
            responsavel_id_turma=turma_data.get("responsavel_id"),
        )
        st.markdown("---")

    if tipo == "Documentação Completa (tudo em ZIP)":
        gerar_documentacao_completa(
            tid,
            titulo_turma,
            client_id,
            ct_id,
            turma_data,
            curso_data,
            dados_resp,
            exige_atestado=exige_atestado,
        )

    elif tipo == "Atestado de Brigada (Empresa)":
        gerar_atestado(tid, titulo_turma, client_id, ct_id, turma_data, curso_data)

    elif tipo == "Certificado da Empresa":
        gerar_certificado_empresa(
            tid, titulo_turma, client_id, ct_id, turma_data, curso_data, dados_resp
        )

    elif tipo == "Certificados Individuais (Alunos)":
        gerar_certificados_individuais(
            tid, titulo_turma, client_id, ct_id, turma_data, curso_data, dados_resp
        )

    elif tipo == "Carteirinhas (Alunos)":
        gerar_carteirinhas(tid, titulo_turma, client_id, ct_id, turma_data, curso_data)

    elif tipo == "Lista de Presença":
        gerar_lista_presenca(tid, titulo_turma)
