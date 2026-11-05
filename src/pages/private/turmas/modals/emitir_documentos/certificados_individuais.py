import streamlit as st

from src.utils.certificado import gerar_certificados_pdf, gerar_certificados_pdf_zip
from src.pages.private.turmas.helpers import formatar_data_extenso

from .data import (
    fetch_ct,
    fetch_empresa,
    fetch_instrutor,
    fetch_matriculas,
    resolver_cidade,
    marcar_documento_emitido,
)
from .alunos import alunos_para_certificado


def gerar_certificados_individuais(
    tid: str,
    titulo_turma: str,
    client_id: str | None,
    ct_id: str | None,
    turma_data: dict,
    curso_data: dict,
    dados_resp: dict,
) -> None:
    nivel = (turma_data.get("nivel") or "").strip() or "Formação"
    modalidade = (turma_data.get("modalidade") or "").strip() or "Presencial"
    carga = (turma_data.get("carga_horaria") or "").strip() or "8 Horas"

    st.info(
        f"ℹ️ Nível / modalidade / carga da **turma**: **{nivel}** | **{modalidade}** | **{carga}**"
    )

    mostrar_endereco_ct = st.checkbox(
        "Exibir endereço do CT abaixo da modalidade",
        value=False,
        key=f"mostrar_end_ct_aluno_{tid}",
        help="Quando marcado, o endereço do Centro de Treinamento aparece abaixo da modalidade no certificado.",
    )

    formato = st.radio(
        "Formato do download",
        options=["PDF único (todos juntos)", "ZIP (um PDF por aluno)"],
        index=0,
        horizontal=True,
        key=f"formato_cert_alunos_{tid}",
        help="PDF único gera um arquivo com todos os certificados. ZIP gera um PDF separado por aluno.",
    )
    usar_zip = formato.startswith("ZIP")

    label_btn = (
        "Processar e Baixar Lote (ZIP)"
        if usar_zip
        else "Processar e Baixar Lote (PDF único)"
    )
    if not st.button(
        label_btn,
        type="primary",
        use_container_width=True,
        key=f"btn_cert_alunos_{tid}",
    ):
        return

    try:
        with st.spinner("Processando certificados individuais..."):
            cidade = resolver_cidade(ct_id, turma_data)
            cidade_data = formatar_data_extenso(
                turma_data.get("data_treinamento", ""), cidade=cidade
            )

            empresa_data = fetch_empresa(client_id)
            instrutor_data = fetch_instrutor(turma_data.get("instrutor_id"))
            ct_data = fetch_ct(ct_id or turma_data.get("ct_id"))
            matriculas = fetch_matriculas(tid)
            alunos = alunos_para_certificado(matriculas, carga, incluir_nasc=True)

            if not alunos:
                st.warning("⚠️ Nenhum aluno matriculado nesta turma.")
                return

            turma_cert = {
                "modalidade": modalidade,
                "nivel": nivel,
                "carga_horaria": carga,
                "mostrar_endereco_ct": mostrar_endereco_ct,
                "resp_tecnico": dados_resp.get("nome", ""),
                "cpf_resp_tecnico": dados_resp.get("cpf", ""),
                "re_resp_tecnico": dados_resp.get("re", ""),
                "formacao_resp_tecnico": dados_resp.get("formacao", ""),
                "assinatura_resp_url": dados_resp.get("assinatura_url"),
                "curso_nome": curso_data.get("name", "Treinamento"),
                "curso_sigla": (curso_data.get("sigla") or "").strip().upper(),
                "dizeres_certificado_aluno": curso_data.get(
                    "dizeres_certificado_aluno", ""
                ),
            }

            kwargs = dict(
                alunos_matriculas=alunos,
                turma=turma_cert,
                instrutor=instrutor_data,
                empresa=empresa_data,
                ct=ct_data or None,
                normativa=turma_data.get("normativa", "") or curso_data.get("normativa", ""),
                cidade_data=cidade_data,
            )

            if usar_zip:
                arquivo_bytes = gerar_certificados_pdf_zip(**kwargs)
                mime = "application/zip"
                file_name = f"certificados_{titulo_turma.replace(' ', '_')}.zip"
                label_dl = "Baixar Certificados (ZIP)"
            else:
                arquivo_bytes = gerar_certificados_pdf(**kwargs)
                mime = "application/pdf"
                file_name = f"certificados_{titulo_turma.replace(' ', '_')}.pdf"
                label_dl = "Baixar Certificados (PDF único)"

            ok, msg = marcar_documento_emitido(tid)
            if ok:
                st.success("✅ Certificados gerados e **turma marcada como emitida**!")
            else:
                st.success("✅ Certificados gerados com sucesso!")
                st.warning(f"⚠️ Status do card: {msg}")

            st.download_button(
                label_dl,
                data=arquivo_bytes,
                file_name=file_name,
                mime=mime,
                use_container_width=True,
                key=f"dl_cert_alunos_{tid}_{'zip' if usar_zip else 'pdf'}",
            )
    except Exception as e:
        st.error(f"❌ Erro ao gerar os certificados: {e}")
