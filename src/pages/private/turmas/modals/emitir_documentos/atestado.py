import streamlit as st

from src.utils.atestado import gerar_atestado_pdf_de_arquivo
from src.pages.private.turmas.helpers import formatar_data_extenso

from .data import (
    fetch_ct,
    fetch_empresa,
    fetch_instrutor,
    fetch_matriculas,
    resolver_cidade,
    marcar_documento_emitido,
)
from .alunos import alunos_para_atestado


def gerar_atestado(
    tid: str,
    titulo_turma: str,
    client_id: str | None,
    ct_id: str | None,
    turma_data: dict,
    curso_data: dict,
) -> None:
    modalidade = turma_data.get("modalidade", "Presencial")
    nivel = turma_data.get("nivel", "Basico")
    carga = turma_data.get("carga_horaria", "8 Horas")

    st.info(
        f"ℹ️ O atestado usara os dados oficiais da turma: "
        f"**{modalidade} | {nivel} | {carga}**"
    )

    if not st.button(
        "🚀 Processar e Gerar Atestado", type="primary", use_container_width=True
    ):
        return

    try:
        with st.spinner("Buscando dados e gerando atestado..."):
            cidade = resolver_cidade(ct_id, turma_data)
            cidade_data = formatar_data_extenso(
                turma_data.get("data_treinamento", ""), cidade=cidade
            )

            ct_data = fetch_ct(ct_id or turma_data.get("ct_id"))
            empresa_data = fetch_empresa(client_id)
            instrutor_data = fetch_instrutor(turma_data.get("instrutor_id"))
            matriculas = fetch_matriculas(tid)
            alunos = alunos_para_atestado(matriculas, carga, nivel)

            if not alunos:
                st.warning("⚠️ Nenhum aluno matriculado nesta turma.")
                return

            pdf_bytes = gerar_atestado_pdf_de_arquivo(
                alunos=alunos,
                turma=turma_data,
                empresa=empresa_data,
                curso=curso_data or None,
                instrutor=instrutor_data,
                ct=ct_data or None,
                cidade_data_formatada=cidade_data,
            )

            marcar_documento_emitido(tid)

            st.success("✅ Atestado gerado com sucesso!")
            st.download_button(
                "📥 Baixar Atestado (PDF)",
                data=pdf_bytes,
                file_name=f"atestado_{titulo_turma.replace(' ', '_')}.pdf",
                mime="application/pdf",
                use_container_width=True,
                key=f"dl_atest_{tid}",
            )
    except Exception as e:
        st.error(f"❌ Erro ao gerar o atestado: {e}")
