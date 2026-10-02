import streamlit as st

from src.utils.carteirinha import gerar_carteirinhas_pdf

from .data import (
    fetch_ct,
    fetch_instrutor,
    fetch_matriculas,
    marcar_documento_emitido,
)
from .alunos import alunos_para_certificado


def _ss_key(tid: str) -> str:
    return f"carteirinhas_pdf_{tid}"


def _ss_meta_key(tid: str) -> str:
    return f"carteirinhas_meta_{tid}"


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
    safe = (titulo_turma or "turma").replace(" ", "_")

    st.info(
        f"Carteirinhas em lote (**4 por página A4**).  \n"
        f"**Curso:** {curso_nome} · **Carga:** {carga} · **Conclusão:** {str(data_trein)[:10]}"
    )
    st.caption(
        "O fundo vem do cadastro do CT (**Fundo de Carteirinha**). "
        "Se não houver, a carteirinha sai com layout limpo."
    )

    # PDF já gerado nesta sessão — mantém download sem fechar o modal
    pdf_pronto = st.session_state.get(_ss_key(tid))
    meta = st.session_state.get(_ss_meta_key(tid)) or {}

    if pdf_pronto:
        qtd = meta.get("qtd") or "?"
        st.success(f"✅ {qtd} carteirinha(s) pronta(s) para download.")
        if meta.get("marcado"):
            st.success("✅ Turma marcada como documentação emitida.")
        elif meta.get("erro_marca"):
            st.warning(f"⚠️ {meta['erro_marca']}")

        st.download_button(
            "📥 Baixar Carteirinhas (PDF)",
            data=pdf_pronto,
            file_name=f"carteirinhas_{safe}.pdf",
            mime="application/pdf",
            use_container_width=True,
            key=f"dl_carteirinha_{tid}",
        )
        st.caption("Baixe quantas vezes quiser. Feche o modal quando terminar.")

        if st.button(
            "🔄 Gerar novamente",
            use_container_width=True,
            key=f"btn_regen_cart_{tid}",
        ):
            st.session_state.pop(_ss_key(tid), None)
            st.session_state.pop(_ss_meta_key(tid), None)
            st.rerun()
        return

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

            st.session_state[_ss_key(tid)] = pdf_bytes
            st.session_state[_ss_meta_key(tid)] = {
                "qtd": len(alunos),
                "marcado": ok,
                "erro_marca": None if ok else msg,
            }

            st.success(f"✅ {len(alunos)} carteirinha(s) gerada(s).")
            if ok:
                st.success("✅ Turma marcada como documentação emitida.")
            else:
                st.warning(f"⚠️ Status do card: {msg}")

            st.download_button(
                "📥 Baixar Carteirinhas (PDF)",
                data=pdf_bytes,
                file_name=f"carteirinhas_{safe}.pdf",
                mime="application/pdf",
                use_container_width=True,
                key=f"dl_carteirinha_{tid}",
            )
            st.caption("Baixe o arquivo antes de fechar o modal.")

    except Exception as e:
        st.error(f"❌ Erro ao gerar carteirinhas: {e}")
