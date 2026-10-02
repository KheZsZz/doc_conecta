import streamlit as st

from src.utils.carteirinha import gerar_carteirinhas_pdf
from src.pages.private.turmas.helpers import formatar_data_extenso  # noqa: F401

from .data import (
    fetch_ct,
    fetch_instrutor,
    fetch_matriculas,
    marcar_documento_emitido,
)
from .alunos import alunos_para_certificado


def gerar_carteirinhas(
    tid: str,
    titulo_turma: str,
    client_id: str | None,
    ct_id: str | None,
    turma_data: dict,
    curso_data: dict,
) -> None:
    carga = (turma_data.get("carga_horaria") or "").strip() or "8 Horas"
    curso_nome = curso_data.get("name") or "Treinamento"
    data_trein = turma_data.get("data_treinamento") or ""

    st.info(
        f"Carteirinhas em lote (4 por página A4).  \n"
        f"**Curso:** {curso_nome} · **Carga:** {carga} · **Conclusão:** {str(data_trein)[:10]}"
    )
    st.caption(
        "O fundo vem do cadastro do CT (campo Fundo de Carteirinha). "
        "Se não houver, a carteirinha sai com layout limpo."
    )

    if not st.button(
        "🚀 Gerar Carteirinhas (PDF)",
        type="primary",
        use_container_width=True,
        key=f"btn_carteirinha_{tid}",
    ):
        return

    try:
        with st.spinner("Gerando carteirinhas..."):
            ct_data = fetch_ct(ct_id or turma_data.get("ct_id"))
            instrutor_data = fetch_instrutor(turma_data.get("instrutor_id"))
            matriculas = fetch_matriculas(tid)
            alunos = alunos_para_certificado(matriculas, carga, incluir_nasc=False)

            if not alunos:
                st.warning("⚠️ Nenhum aluno matriculado nesta turma.")
                return

            pdf_bytes = gerar_carteirinhas_pdf(
                alunos=alunos,
                curso_nome=curso_nome,
                carga_horaria=carga,
                data_conclusao=str(data_trein),
                instrutor=instrutor_data,
                ct=ct_data or None,
            )

            ok, msg = marcar_documento_emitido(tid)
            if ok:
                st.success(
                    f"✅ {len(alunos)} carteirinha(s) gerada(s) e turma marcada como emitida."
                )
            else:
                st.success(f"✅ {len(alunos)} carteirinha(s) gerada(s).")
                st.warning(f"⚠️ Status do card: {msg}")

            safe = titulo_turma.replace(" ", "_")
            st.download_button(
                "📥 Baixar Carteirinhas (PDF)",
                data=pdf_bytes,
                file_name=f"carteirinhas_{safe}.pdf",
                mime="application/pdf",
                use_container_width=True,
                key=f"dl_carteirinha_{tid}",
            )
    except Exception as e:
        st.error(f"❌ Erro ao gerar carteirinhas: {e}")
