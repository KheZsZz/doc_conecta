import streamlit as st

from src.config.database import supabase
from src.utils.carteirinha import (
    gerar_carteirinhas_pdf,
    _eh_curso_bombeiro,
    _eh_reciclagem,
)

from .data import (
    fetch_ct,
    fetch_instrutor,
    fetch_matriculas,
    marcar_documento_emitido,
)
from .alunos import alunos_para_certificado
from .responsavel import ui_selecionar_responsavel


def _ss_key(tid: str) -> str:
    return f"carteirinhas_pdf_{tid}"


def _ss_meta_key(tid: str) -> str:
    return f"carteirinhas_meta_{tid}"


def _persistir_re_alunos(alunos_com_re: list[dict]) -> int:
    """Grava RE gerado no cadastro do aluno (formacao Bombeiro)."""
    gravados = 0
    for item in alunos_com_re or []:
        if not item.get("gerado"):
            continue
        re_val = (item.get("re") or "").strip()
        if not re_val:
            continue
        aluno_id = (item.get("aluno_id") or "").strip()
        cpf = "".join(ch for ch in str(item.get("cpf") or "") if ch.isdigit())
        try:
            if aluno_id:
                supabase.table("alunos").update({"re": re_val}).eq(
                    "id", aluno_id
                ).execute()
                gravados += 1
            elif cpf:
                cpf11 = cpf.zfill(11) if len(cpf) <= 11 else cpf[:11]
                supabase.table("alunos").update({"re": re_val}).eq(
                    "cpf", cpf11
                ).execute()
                gravados += 1
        except Exception:
            try:
                if cpf:
                    supabase.table("alunos").update({"re": re_val}).eq(
                        "cpf", cpf
                    ).execute()
                    gravados += 1
            except Exception:
                pass
    return gravados


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
    curso_sigla = (curso_data.get("sigla") or "").strip()
    data_trein = turma_data.get("data_treinamento") or ""
    nivel = (turma_data.get("nivel") or "").strip()
    safe = (titulo_turma or "turma").replace(" ", "_")

    is_bombeiro = _eh_curso_bombeiro(curso_nome, curso_sigla)
    modelo = "bombeiro" if is_bombeiro else "padrao"
    reciclagem = _eh_reciclagem(nivel, curso_nome)

    st.info(
        f"Carteirinhas em lote (**layout ETEPS · 4 por página A4**).  \n"
        f"**Curso:** {curso_nome} · **Nível:** {nivel or '—'} · "
        f"**Carga:** {carga} · **Conclusão:** {str(data_trein)[:10]}"
    )
    st.caption(
        "Mesmo visual do Bombeiro Civil para todos os cursos. "
        "Assinatura e dados do Responsável Técnico (quando selecionado) "
        "aparecem no verso."
    )

    dados_resp = ui_selecionar_responsavel(tid, f"carteirinha_{tid}")

    numero_cartao_base = None
    if is_bombeiro:
        if reciclagem:
            st.warning(
                "**Reciclagem (Bombeiro):** o RE/Cartão nº deve vir na lista "
                "do aluno (coluna **RE** no Subir Listas). O sistema **não gera** RE novo."
            )
        else:
            st.info(
                "**Formação (Bombeiro):** se o aluno não tiver RE, o sistema "
                "**gera** o número e grava no cadastro do aluno."
            )
            numero_base = st.number_input(
                "Número inicial do cartão / RE (opcional)",
                min_value=0,
                value=0,
                step=1,
                help=(
                    "Se 0, usa os últimos 5 dígitos do CPF. "
                    "Se > 0, numera em sequência a partir desse valor."
                ),
                key=f"num_cart_base_{tid}",
            )
            numero_cartao_base = (
                int(numero_base) if numero_base and numero_base > 0 else None
            )
    else:
        st.caption(
            "Para cursos gerais, o campo **Cartão nº / RE** usa o RE do aluno "
            "se existir; caso contrário fica em branco."
        )

    pdf_pronto = st.session_state.get(_ss_key(tid))
    meta = st.session_state.get(_ss_meta_key(tid)) or {}

    if pdf_pronto:
        qtd = meta.get("qtd") or "?"
        st.success(f"✅ {qtd} carteirinha(s) pronta(s) para download.")
        if meta.get("re_gravados"):
            st.success(
                f"✅ {meta['re_gravados']} RE(s) gerado(s) e gravado(s) no cadastro."
            )
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

            if is_bombeiro and reciclagem:
                sem_re = [a for a in alunos if not (a.get("re") or "").strip()]
                if sem_re:
                    st.error(
                        f"❌ Reciclagem: {len(sem_re)} aluno(s) sem RE no cadastro. "
                        "Suba a lista com a coluna **RE** preenchida (Subir Listas)."
                    )
                    nomes = ", ".join((a.get("name") or "?") for a in sem_re[:8])
                    st.caption(f"Exemplos: {nomes}")
                    return

            pdf_bytes, alunos_com_re = gerar_carteirinhas_pdf(
                alunos=alunos,
                curso_nome=curso_nome,
                carga_horaria=carga,
                data_conclusao=str(data_trein),
                instrutor=instrutor_data,
                ct=ct_data or None,
                curso_sigla=curso_sigla,
                modelo=modelo,
                numero_cartao_base=numero_cartao_base,
                responsavel=dados_resp,
                nivel=nivel,
            )

            re_gravados = 0
            if is_bombeiro and not reciclagem:
                re_gravados = _persistir_re_alunos(alunos_com_re)

            ok, msg = marcar_documento_emitido(tid)

            st.session_state[_ss_key(tid)] = pdf_bytes
            st.session_state[_ss_meta_key(tid)] = {
                "qtd": len(alunos),
                "marcado": ok,
                "erro_marca": None if ok else msg,
                "re_gravados": re_gravados,
            }

            st.success(f"✅ {len(alunos)} carteirinha(s) gerada(s).")
            if re_gravados:
                st.success(
                    f"✅ {re_gravados} RE(s) gerado(s) e gravado(s) nos alunos."
                )
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
