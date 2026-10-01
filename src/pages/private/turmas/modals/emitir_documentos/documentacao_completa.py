"""Gera todos os documentos da turma em um unico arquivo ZIP."""
from __future__ import annotations

import io
import zipfile

import pandas as pd
import streamlit as st

from src.utils.atestado import gerar_atestado_pdf_de_arquivo
from src.utils.certificado_empresa import gerar_certificado_empresa_pdf
from src.utils.certificado import gerar_certificados_pdf_zip
from src.pages.private.turmas.helpers import formatar_data_extenso

from .data import (
    fetch_ct,
    fetch_empresa,
    fetch_instrutor,
    fetch_matriculas,
    resolver_cidade,
    marcar_documento_emitido,
)
from .alunos import (
    alunos_para_atestado,
    alunos_para_certificado,
    alunos_para_lista_presenca,
)


def _slug(texto: str) -> str:
    s = (texto or "turma").strip().replace(" ", "_")
    return "".join(c for c in s if c.isalnum() or c in ("_", "-"))[:80] or "turma"


def gerar_documentacao_completa(
    tid: str,
    titulo_turma: str,
    client_id: str | None,
    ct_id: str | None,
    turma_data: dict,
    curso_data: dict,
    dados_resp: dict,
    exige_atestado: bool,
) -> None:
    nivel = (turma_data.get("nivel") or "").strip() or "Formação"
    modalidade = (turma_data.get("modalidade") or "").strip() or "Presencial"
    carga = (turma_data.get("carga_horaria") or "").strip() or "8 Horas"
    normativa = turma_data.get("normativa") or curso_data.get("normativa") or ""

    incluidos = [
        "Certificado da Empresa",
        "Certificados Individuais (ZIP interno)",
        "Lista de Presença (.xlsx)",
    ]
    if exige_atestado:
        incluidos.insert(0, "Atestado de Brigada")

    st.info(
        "Este pacote inclui:\n\n- "
        + "\n- ".join(incluidos)
        + f"\n\n**Turma:** {nivel} | {modalidade} | {carga}"
    )

    if not st.button(
        "🚀 Gerar documentação completa (ZIP)",
        type="primary",
        use_container_width=True,
        key=f"btn_doc_completa_{tid}",
    ):
        return

    try:
        with st.spinner("Gerando todos os documentos da turma... isso pode levar alguns segundos."):
            cidade = resolver_cidade(ct_id, turma_data)
            cidade_data = formatar_data_extenso(
                turma_data.get("data_treinamento", ""), cidade=cidade
            )

            ct_data = fetch_ct(ct_id or turma_data.get("ct_id"))
            empresa_data = fetch_empresa(client_id)
            instrutor_data = fetch_instrutor(turma_data.get("instrutor_id"))
            matriculas = fetch_matriculas(tid)

            if not matriculas:
                st.warning("⚠️ Nenhum aluno matriculado nesta turma.")
                return

            alunos_cert = alunos_para_certificado(matriculas, carga, incluir_nasc=True)
            alunos_atest = alunos_para_atestado(matriculas, carga, nivel)
            alunos_lista = alunos_para_lista_presenca(matriculas)

            turma_cert = {
                "modalidade": modalidade,
                "nivel": nivel,
                "carga_horaria": carga,
                "resp_tecnico": dados_resp.get("nome", ""),
                "cpf_resp_tecnico": dados_resp.get("cpf", ""),
                "assinatura_resp_url": dados_resp.get("assinatura_url"),
                "curso_nome": curso_data.get("name", "Treinamento"),
                "dizeres_certificado_empresa": curso_data.get(
                    "dizeres_certificado_empresa", ""
                ),
                "dizeres_certificado_aluno": curso_data.get(
                    "dizeres_certificado_aluno", ""
                ),
            }

            base = _slug(titulo_turma)
            gerados: list[str] = []
            erros: list[str] = []

            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:

                # ---- Atestado ----
                if exige_atestado:
                    try:
                        pdf_atest = gerar_atestado_pdf_de_arquivo(
                            alunos=alunos_atest,
                            turma=turma_data,
                            empresa=empresa_data,
                            curso=curso_data or None,
                            instrutor=instrutor_data,
                            ct=ct_data or None,
                            cidade_data_formatada=cidade_data,
                        )
                        zf.writestr(f"{base}/01_atestado.pdf", pdf_atest)
                        gerados.append("Atestado")
                    except Exception as e:
                        erros.append(f"Atestado: {e}")

                # ---- Certificado Empresa ----
                try:
                    pdf_emp = gerar_certificado_empresa_pdf(
                        turma=turma_cert,
                        instrutor=instrutor_data,
                        empresa=empresa_data,
                        alunos=alunos_cert,
                        normativa=normativa,
                        cidade_data=cidade_data,
                    )
                    zf.writestr(f"{base}/02_certificado_empresa.pdf", pdf_emp)
                    gerados.append("Certificado Empresa")
                except Exception as e:
                    erros.append(f"Certificado Empresa: {e}")

                # ---- Certificados individuais (ZIP interno) ----
                try:
                    zip_alunos = gerar_certificados_pdf_zip(
                        alunos_matriculas=alunos_cert,
                        turma=turma_cert,
                        instrutor=instrutor_data,
                        empresa=empresa_data,
                        ct=None,
                        normativa=normativa,
                        cidade_data=cidade_data,
                    )
                    zf.writestr(
                        f"{base}/03_certificados_individuais.zip", zip_alunos
                    )
                    gerados.append("Certificados Individuais")
                except Exception as e:
                    erros.append(f"Certificados Individuais: {e}")

                # ---- Lista de presença ----
                try:
                    df = pd.DataFrame(alunos_lista)
                    xlsx_buf = io.BytesIO()
                    with pd.ExcelWriter(xlsx_buf, engine="openpyxl") as writer:
                        df.to_excel(
                            writer, index=False, sheet_name="Lista de Presença"
                        )
                    zf.writestr(
                        f"{base}/04_lista_presenca.xlsx", xlsx_buf.getvalue()
                    )
                    gerados.append("Lista de Presença")
                except Exception as e:
                    erros.append(f"Lista de Presença: {e}")

            if not gerados:
                st.error(
                    "❌ Nenhum documento pôde ser gerado.\n\n"
                    + "\n".join(f"- {e}" for e in erros)
                )
                return

            marcar_documento_emitido(tid)

            zip_buffer.seek(0)
            st.success(
                "✅ Documentação gerada: **" + "**, **".join(gerados) + "**."
            )
            if erros:
                with st.expander("⚠️ Alguns itens falharam", expanded=True):
                    for e in erros:
                        st.write(f"- {e}")

            st.download_button(
                "📥 Baixar documentação completa (ZIP)",
                data=zip_buffer.getvalue(),
                file_name=f"documentacao_{base}.zip",
                mime="application/zip",
                use_container_width=True,
                key=f"dl_doc_completa_{tid}",
            )

    except Exception as e:
        st.error(f"❌ Erro ao gerar documentação completa: {e}")
