import streamlit as st

from src.utils.certificado_empresa import gerar_certificado_empresa_pdf
from src.pages.private.turmas.helpers import formatar_data_extenso

from .data import (
    fetch_empresa,
    fetch_instrutor,
    fetch_matriculas,
    resolver_cidade,
    marcar_documento_emitido,
)
from .alunos import alunos_para_certificado


def gerar_certificado_empresa(
    tid: str,
    titulo_turma: str,
    client_id: str | None,
    ct_id: str | None,
    turma_data: dict,
    curso_data: dict,
    dados_resp: dict,
) -> None:
    if not st.button(
        "🚀 Processar e Gerar Certificado (Empresa)",
        type="primary",
        use_container_width=True,
    ):
        return

    try:
        with st.spinner("Gerando certificado corporativo..."):
            cidade = resolver_cidade(ct_id, turma_data)
            cidade_data = formatar_data_extenso(
                turma_data.get("data_treinamento", ""), cidade=cidade
            )

            carga = turma_data.get("carga_horaria", "8 Horas")
            empresa_data = fetch_empresa(client_id)
            instrutor_data = fetch_instrutor(turma_data.get("instrutor_id"))
            matriculas = fetch_matriculas(tid)
            alunos = alunos_para_certificado(matriculas, carga)

            turma_cert = {
                "modalidade": turma_data.get("modalidade", "Presencial"),
                "nivel": turma_data.get("nivel", "Formação"),
                "carga_horaria": carga,
                "resp_tecnico": dados_resp.get("nome", ""),
                "cpf_resp_tecnico": dados_resp.get("cpf", ""),
                "assinatura_resp_url": dados_resp.get("assinatura_url"),
                "curso_nome": curso_data.get("name", "Treinamento"),
                "dizeres_certificado_empresa": curso_data.get(
                    "dizeres_certificado_empresa", ""
                ),
            }

            pdf_bytes = gerar_certificado_empresa_pdf(
                turma=turma_cert,
                instrutor=instrutor_data,
                empresa=empresa_data,
                alunos=alunos,
                normativa=turma_data.get("normativa", ""),
                cidade_data=cidade_data,
            )

            marcar_documento_emitido(tid)

            st.success("✅ Certificado da Empresa gerado com sucesso!")
            st.download_button(
                "📥 Baixar Certificado Empresa (PDF)",
                data=pdf_bytes,
                file_name=f"certificado_empresa_{titulo_turma.replace(' ', '_')}.pdf",
                mime="application/pdf",
                use_container_width=True,
                key=f"dl_cert_emp_{tid}",
            )
    except Exception as e:
        st.error(f"❌ Erro ao gerar certificado corporativo: {e}")