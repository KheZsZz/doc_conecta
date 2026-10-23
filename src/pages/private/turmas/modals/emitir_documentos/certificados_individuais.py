import streamlit as st

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
from .alunos import alunos_para_certificado


FUNDO_TREINNAR = (
    "https://vesgrrejcehseygchigh.supabase.co/storage/v1/object/public/logos/Certificados_treinnar.jpg"
)


def _fundo_do_ct(ct: dict | None) -> str | None:
    ct = ct or {}
    for key in (
        "fundo_certificado_url",
        "fundo_certificado",
        "certificado_fundo_url",
        "fundo_url",
        "url_fundo_certificado",
    ):
        val = (ct.get(key) or "").strip()
        if val.startswith(("http://", "https://", "data:")):
            return val
    for k, v in ct.items():
        if isinstance(v, str) and v.startswith("http") and "certificado" in v.lower():
            return v.strip()
    nome = f"{ct.get('name') or ''} {ct.get('full_name') or ''}".lower()
    if "treinnar" in nome:
        return FUNDO_TREINNAR
    return None


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

    if not st.button(
        "🚀 Processar e Baixar Lote (ZIP)",
        type="primary",
        use_container_width=True,
    ):
        return

    try:
        with st.spinner("Processando certificados individuais..."):
            ct_id_resolvido = ct_id or turma_data.get("ct_id")
            ct_data = fetch_ct(ct_id_resolvido) if ct_id_resolvido else {}
            fundo = _fundo_do_ct(ct_data)

            cidade = resolver_cidade(ct_id_resolvido, turma_data)
            cidade_data = formatar_data_extenso(
                turma_data.get("data_treinamento", ""), cidade=cidade
            )

            empresa_data = fetch_empresa(client_id)
            instrutor_data = fetch_instrutor(turma_data.get("instrutor_id"))
            matriculas = fetch_matriculas(tid)
            alunos = alunos_para_certificado(matriculas, carga, incluir_nasc=True)

            if not alunos:
                st.warning("⚠️ Nenhum aluno matriculado nesta turma.")
                return

            if fundo:
                st.caption(f"🖼️ Fundo: `{fundo[:90]}{'…' if len(fundo) > 90 else ''}`")
            else:
                st.warning(
                    "⚠️ CT sem fundo de certificado cadastrado "
                    "(`fundo_certificado_url`). Será usado o fundo padrão Conecta."
                )

            turma_cert = {
                "modalidade": modalidade,
                "nivel": nivel,
                "carga_horaria": carga,
                "resp_tecnico": dados_resp.get("nome", ""),
                "cpf_resp_tecnico": dados_resp.get("cpf", ""),
                "re_resp_tecnico": dados_resp.get("re", ""),
                "assinatura_resp_url": dados_resp.get("assinatura_url"),
                "curso_nome": curso_data.get("name", "Treinamento"),
                "dizeres_certificado_aluno": curso_data.get(
                    "dizeres_certificado_aluno", ""
                ),
            }

            zip_bytes = gerar_certificados_pdf_zip(
                alunos_matriculas=alunos,
                turma=turma_cert,
                instrutor=instrutor_data,
                empresa=empresa_data,
                ct=ct_data or None,
                normativa=turma_data.get("normativa", "") or curso_data.get("normativa", ""),
                cidade_data=cidade_data,
                caminho_fundo=fundo,
            )

            ok, msg = marcar_documento_emitido(tid)
            if ok:
                st.success("✅ Certificados gerados e **turma marcada como emitida**!")
            else:
                st.success("✅ Certificados gerados com sucesso!")
                st.warning(f"⚠️ Status do card: {msg}")

            st.download_button(
                "📥 Baixar Certificados (ZIP)",
                data=zip_bytes,
                file_name=f"certificados_{titulo_turma.replace(' ', '_')}.zip",
                mime="application/zip",
                use_container_width=True,
                key=f"dl_cert_zip_{tid}",
            )
    except Exception as e:
        st.error(f"❌ Erro ao gerar os certificados: {e}")
