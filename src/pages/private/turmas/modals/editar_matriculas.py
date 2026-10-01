from datetime import date, datetime

import streamlit as st

from src.config.database import supabase


def _fmt_cpf(cpf: str) -> str:
    c = "".join(ch for ch in str(cpf or "") if ch.isdigit())
    if len(c) == 11:
        return f"{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}"
    return cpf or "—"


def _parse_data_nasc(val):
    if not val:
        return None
    try:
        s = str(val).split("T")[0][:10]
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def _carregar_matriculas(tid: str) -> list[dict]:
    mat_res = (
        supabase.table("matriculas")
        .select(
            "id, aluno_id, carga_horaria, data_treinamento, "
            "alunos(id, name, cpf, rg, data_nasc, email)"
        )
        .eq("turma_id", tid)
        .execute()
    )
    if not mat_res or not mat_res.data:
        return []

    lista = []
    for m in mat_res.data:
        info = m.get("alunos") or {}
        lista.append(
            {
                "matricula_id": m.get("id"),
                "aluno_id": m.get("aluno_id") or info.get("id"),
                "nome": info.get("name") or "Sem Nome",
                "cpf": info.get("cpf") or "",
                "rg": info.get("rg") or "",
                "data_nasc": info.get("data_nasc") or "",
                "email": info.get("email") or "",
                "carga_horaria": m.get("carga_horaria") or "",
                "data_treinamento": m.get("data_treinamento") or "",
            }
        )
    lista.sort(key=lambda x: x["nome"])
    return lista


def _carregar_outras_turmas(turma_atual_id: str) -> list[dict]:
    res = (
        supabase.table("turmas")
        .select("id, titulo, data_treinamento, carga_horaria, clients(name)")
        .order("data_treinamento", desc=True)
        .limit(80)
        .execute()
    )
    turmas = []
    for t in res.data or []:
        if t.get("id") == turma_atual_id:
            continue
        emp = (t.get("clients") or {}).get("name") or "—"
        data = str(t.get("data_treinamento") or "")[:10]
        turmas.append(
            {
                "id": t.get("id"),
                "titulo": t.get("titulo") or "Sem título",
                "data": data,
                "carga_horaria": t.get("carga_horaria") or "8 Horas",
                "empresa": emp,
                "label": f"{data} · {t.get('titulo') or 'Sem título'} · {emp}",
            }
        )
    return turmas


@st.dialog("📝 Visualizar / Editar Matrículas", width="large")
def modal_editar_matriculas(tid, titulo_turma):
    st.subheader(f"Matrículas: {titulo_turma}")

    try:
        matriculas = _carregar_matriculas(tid)
    except Exception as e:
        st.error(f"Erro ao buscar matrículas: {e}")
        return

    if not matriculas:
        st.info("Nenhum aluno matriculado nesta turma até o momento.")
        return

    st.caption(f"**{len(matriculas)}** aluno(s) matriculado(s).")

    # ---- Seleção do aluno ----
    opcoes = {f"{m['nome']}  ·  CPF {_fmt_cpf(m['cpf'])}": m for m in matriculas}
    rotulo = st.selectbox(
        "Selecione o aluno",
        options=list(opcoes.keys()),
        key=f"sel_mat_{tid}",
    )
    aluno = opcoes[rotulo]

    st.markdown("---")

    tab_edit, tab_transf, tab_excluir = st.tabs(
        ["✏️ Editar dados", "🔄 Trocar de turma", "🗑️ Excluir matrícula"]
    )

    # ======================================================================
    # ABA 1 — Editar dados do aluno + carga da matrícula
    # ======================================================================
    with tab_edit:
        st.markdown("Altera os dados do **aluno** e a **carga horária** desta matrícula.")

        with st.form(f"form_edit_aluno_{tid}_{aluno['matricula_id']}"):
            nome = st.text_input("Nome completo*", value=aluno["nome"])

            c1, c2 = st.columns(2)
            with c1:
                cpf = st.text_input("CPF (somente números)", value=aluno["cpf"], max_chars=14)
                rg = st.text_input("RG", value=aluno["rg"])
            with c2:
                nasc_val = _parse_data_nasc(aluno["data_nasc"])
                data_nasc = st.date_input(
                    "Data de nascimento",
                    value=nasc_val,
                    min_value=date(1920, 1, 1),
                    max_value=date.today(),
                )
                email = st.text_input("E-mail", value=aluno["email"])

            carga = st.text_input(
                "Carga horária (desta matrícula)",
                value=aluno["carga_horaria"] or "8 Horas",
            )

            salvar = st.form_submit_button(
                "💾 Salvar alterações", type="primary", use_container_width=True
            )

            if salvar:
                if not nome.strip():
                    st.warning("⚠️ O nome é obrigatório.")
                else:
                    try:
                        cpf_limpo = "".join(ch for ch in cpf if ch.isdigit()) or None
                        if cpf_limpo and len(cpf_limpo) < 11:
                            cpf_limpo = cpf_limpo.zfill(11)
                        if cpf_limpo and len(cpf_limpo) > 11:
                            st.warning("⚠️ CPF deve ter no máximo 11 dígitos.")
                            st.stop()

                        payload_aluno = {
                            "name": nome.strip().upper(),
                            "cpf": cpf_limpo,
                            "rg": rg.strip() or None,
                            "data_nasc": data_nasc.isoformat() if data_nasc else None,
                            "email": email.strip() or None,
                        }
                        # remove None opcionais se preferir manter o que já existe —
                        # aqui enviamos o que o usuário preencheu
                        supabase.table("alunos").update(
                            {k: v for k, v in payload_aluno.items() if v is not None}
                            | {"name": payload_aluno["name"]}
                        ).eq("id", aluno["aluno_id"]).execute()

                        supabase.table("matriculas").update(
                            {"carga_horaria": carga.strip() or "8 Horas"}
                        ).eq("id", aluno["matricula_id"]).execute()

                        st.success("✅ Dados atualizados com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Erro ao salvar: {e}")

    # ======================================================================
    # ABA 2 — Transferir para outra turma
    # ======================================================================
    with tab_transf:
        st.markdown(
            "Move a **matrícula** deste aluno para outra turma. "
            "Os dados do aluno permanecem; só muda o vínculo."
        )

        try:
            outras = _carregar_outras_turmas(tid)
        except Exception as e:
            st.error(f"Erro ao carregar turmas: {e}")
            outras = []

        if not outras:
            st.info("Não há outras turmas disponíveis para transferência.")
        else:
            mapa = {t["label"]: t for t in outras}
            destino_label = st.selectbox(
                "Turma de destino",
                options=list(mapa.keys()),
                key=f"transf_dest_{tid}_{aluno['matricula_id']}",
            )
            destino = mapa[destino_label]

            herdar = st.checkbox(
                "Herdar data e carga horária da turma de destino",
                value=True,
                key=f"transf_herdar_{tid}_{aluno['matricula_id']}",
            )

            if st.button(
                f"🔄 Transferir {aluno['nome']} para a turma selecionada",
                type="primary",
                use_container_width=True,
                key=f"btn_transf_{tid}_{aluno['matricula_id']}",
            ):
                try:
                    # Já existe matrícula na turma destino?
                    dup = (
                        supabase.table("matriculas")
                        .select("id")
                        .eq("turma_id", destino["id"])
                        .eq("aluno_id", aluno["aluno_id"])
                        .execute()
                    )
                    if dup and dup.data:
                        st.warning(
                            "⚠️ Este aluno já está matriculado na turma de destino."
                        )
                    else:
                        payload = {"turma_id": destino["id"]}
                        if herdar:
                            if destino.get("data"):
                                payload["data_treinamento"] = destino["data"]
                            if destino.get("carga_horaria"):
                                payload["carga_horaria"] = destino["carga_horaria"]

                        supabase.table("matriculas").update(payload).eq(
                            "id", aluno["matricula_id"]
                        ).execute()

                        st.success(
                            f"✅ {aluno['nome']} transferido para **{destino['titulo']}**."
                        )
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ Erro ao transferir: {e}")

    # ======================================================================
    # ABA 3 — Excluir matrícula
    # ======================================================================
    with tab_excluir:
        st.markdown(
            "Remove o aluno **desta turma**. "
            "O cadastro do aluno no sistema **não** é apagado."
        )
        st.warning(
            f"Você está prestes a remover **{aluno['nome']}** "
            f"(CPF {_fmt_cpf(aluno['cpf'])}) desta turma."
        )

        confirmar = st.checkbox(
            "Confirmo a exclusão desta matrícula",
            key=f"conf_del_{tid}_{aluno['matricula_id']}",
        )

        if st.button(
            f"🗑️ Excluir matrícula de {aluno['nome']}",
            type="primary",
            disabled=not confirmar,
            use_container_width=True,
            key=f"btn_del_{tid}_{aluno['matricula_id']}",
        ):
            try:
                supabase.table("matriculas").delete().eq(
                    "id", aluno["matricula_id"]
                ).execute()
                st.success("✅ Matrícula removida com sucesso!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Erro ao remover: {e}")
