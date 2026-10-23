from datetime import datetime
import pandas as pd
import streamlit as st
from src.config.database import supabase

def _fmt_cpf(cpf: str) -> str:
    c = "".join(ch for ch in str(cpf or "") if ch.isdigit())
    if len(c) == 11:
        return f"{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}"
    return cpf or ""

def _cpf_limpo(val) -> str | None:
    c = "".join(ch for ch in str(val or "") if ch.isdigit())
    if not c or len(c) > 11:
        return None
    return c.zfill(11)

def _data_br(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    s = str(val).split("T")[0][:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return s if s not in ("nan", "None", "NaT") else ""

def _data_iso(val) -> str | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if hasattr(val, "strftime"):
        try:
            return val.strftime("%Y-%m-%d")
        except Exception:
            pass
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "nat", ""):
        return None
    s = s.split(" ")[0].split("T")[0]
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s[:10], fmt).strftime("%Y-%m-%d")
        except Exception:
            continue
    try:
        dt = pd.to_datetime(s, dayfirst=True, errors="coerce")
        if pd.notnull(dt):
            return dt.strftime("%Y-%m-%d")
    except Exception:
        pass
    return None

def _carregar_matriculas(tid: str) -> list[dict]:
    try:
        mat_res = (
            supabase.table("matriculas")
            .select("id, aluno_id, carga_horaria, data_treinamento, alunos(id, name, cpf, rg, data_nasc, email, re)")
            .eq("turma_id", tid).execute()
        )
        tem_re = True
    except Exception:
        mat_res = (
            supabase.table("matriculas")
            .select("id, aluno_id, carga_horaria, data_treinamento, alunos(id, name, cpf, rg, data_nasc, email)")
            .eq("turma_id", tid).execute()
        )
        tem_re = False
    if not mat_res or not mat_res.data:
        return []
    lista = []
    for m in mat_res.data:
        info = m.get("alunos") or {}
        lista.append({
            "matricula_id": m.get("id"),
            "aluno_id": m.get("aluno_id") or info.get("id"),
            "nome": info.get("name") or "Sem Nome",
            "cpf": info.get("cpf") or "",
            "rg": info.get("rg") or "",
            "re": (info.get("re") or "") if tem_re else "",
            "data_nasc": info.get("data_nasc") or "",
            "email": info.get("email") or "",
            "carga_horaria": m.get("carga_horaria") or "",
            "_tem_re": tem_re,
        })
    lista.sort(key=lambda x: (x["nome"] or "").upper())
    return lista

def _carregar_outras_turmas(turma_atual_id: str) -> list[dict]:
    res = (
        supabase.table("turmas")
        .select("id, titulo, data_treinamento, carga_horaria, clients(name)")
        .order("data_treinamento", desc=True).limit(100).execute()
    )
    turmas = []
    for t in res.data or []:
        if t.get("id") == turma_atual_id:
            continue
        emp = (t.get("clients") or {}).get("name") or "—"
        data = str(t.get("data_treinamento") or "")[:10]
        turmas.append({
            "id": t.get("id"),
            "titulo": t.get("titulo") or "Sem título",
            "data": data,
            "carga_horaria": t.get("carga_horaria") or "8 Horas",
            "empresa": emp,
            "label": f"{_data_br(data)} · {t.get('titulo') or 'Sem título'} · {emp}",
        })
    return turmas

def _df_from_matriculas(matriculas: list[dict]) -> pd.DataFrame:
    rows = []
    for m in matriculas:
        rows.append({
            "matricula_id": m["matricula_id"],
            "aluno_id": m["aluno_id"],
            "Nome": m["nome"],
            "CPF": _fmt_cpf(m["cpf"]) if m["cpf"] else m["cpf"],
            "RG": m["rg"] or "",
            "RE": m.get("re") or "",
            "Nascimento": _data_br(m["data_nasc"]),
            "E-mail": m["email"] or "",
            "Carga": m["carga_horaria"] or "",
        })
    return pd.DataFrame(rows)

@st.dialog("📝 Alunos da turma", width="large")
def modal_editar_matriculas(tid, titulo_turma):
    st.subheader(f"{titulo_turma}")
    try:
        matriculas = _carregar_matriculas(tid)
    except Exception as e:
        st.error(f"Erro ao buscar matrículas: {e}")
        return
    if not matriculas:
        st.info("Nenhum aluno matriculado nesta turma até o momento.")
        return
    tem_re = bool(matriculas and matriculas[0].get("_tem_re", True))
    if not tem_re:
        st.warning("Coluna `alunos.re` ausente. Rode: `ALTER TABLE alunos ADD COLUMN IF NOT EXISTS re TEXT;`")
    st.caption(f"**{len(matriculas)}** aluno(s). Edite a tabela (inclui **RE**) e clique em **Salvar**.")
    busca = st.text_input("🔍 Filtrar (nome ou CPF)", key=f"filtro_mat_tab_{tid}", placeholder="Digite...")
    df = _df_from_matriculas(matriculas)
    if busca.strip():
        q = busca.strip().lower()
        q_dig = "".join(ch for ch in q if ch.isdigit())
        mask = df["Nome"].str.lower().str.contains(q, na=False)
        if q_dig:
            mask = mask | df["CPF"].astype(str).str.replace(r"\D", "", regex=True).str.contains(q_dig, na=False)
        df = df[mask].copy()
    if df.empty:
        st.warning("Nenhum aluno com esse filtro.")
        return
    edited = st.data_editor(
        df, hide_index=True, use_container_width=True, num_rows="fixed", key=f"editor_mat_{tid}",
        column_config={
            "matricula_id": None, "aluno_id": None,
            "Nome": st.column_config.TextColumn("Nome", width="large", required=True),
            "CPF": st.column_config.TextColumn("CPF", width="medium"),
            "RG": st.column_config.TextColumn("RG", width="small"),
            "RE": st.column_config.TextColumn("RE / Cartão nº", help="Número do cartão (Bombeiro).", width="small"),
            "Nascimento": st.column_config.TextColumn("Nascimento", help="DD/MM/AAAA", width="small"),
            "E-mail": st.column_config.TextColumn("E-mail", width="medium"),
            "Carga": st.column_config.TextColumn("Carga horária", width="small"),
        },
        disabled=[],
    )
    if st.button("💾 Salvar alterações da tabela", type="primary", use_container_width=True, key=f"salvar_tab_{tid}"):
        originais = {m["matricula_id"]: m for m in matriculas}
        atualizados = 0
        erros = []
        for _, row in edited.iterrows():
            mid, aid = row.get("matricula_id"), row.get("aluno_id")
            if mid not in originais:
                continue
            orig = originais[mid]
            nome = str(row.get("Nome") or "").strip()
            if not nome:
                erros.append(f"Linha sem nome ({mid})")
                continue
            cpf = _cpf_limpo(row.get("CPF"))
            rg = str(row.get("RG") or "").strip() or None
            re_val = str(row.get("RE") or "").strip() or None
            email = str(row.get("E-mail") or "").strip() or None
            nasc = _data_iso(row.get("Nascimento"))
            carga = str(row.get("Carga") or "").strip() or "8 Horas"
            try:
                payload = {"name": nome.upper(), "cpf": cpf, "rg": rg, "email": email, "data_nasc": nasc}
                if tem_re:
                    payload["re"] = re_val
                payload = {k: v for k, v in payload.items() if v is not None or k in ("name", "re")}
                payload["name"] = nome.upper()
                mudou = (
                    nome.upper() != (orig["nome"] or "").upper()
                    or (cpf or "") != (orig["cpf"] or "")
                    or (rg or "") != (orig["rg"] or "")
                    or (re_val or "") != (orig.get("re") or "")
                    or (email or "") != (orig["email"] or "")
                    or (nasc or "") != str(orig.get("data_nasc") or "")[:10]
                )
                if mudou:
                    try:
                        supabase.table("alunos").update(payload).eq("id", aid).execute()
                    except Exception as e_up:
                        msg = str(e_up).lower()
                        if "23505" in str(e_up) or "duplicate" in msg:
                            payload.pop("rg", None)
                            supabase.table("alunos").update(payload).eq("id", aid).execute()
                        elif "re" in msg or "column" in msg:
                            payload.pop("re", None)
                            supabase.table("alunos").update(payload).eq("id", aid).execute()
                        else:
                            raise
                if carga != (orig.get("carga_horaria") or ""):
                    supabase.table("matriculas").update({"carga_horaria": carga}).eq("id", mid).execute()
                atualizados += 1
            except Exception as e:
                erros.append(f"{nome}: {e}")
        if erros:
            st.error("Algumas linhas falharam:")
            for e in erros:
                st.write(f"- {e}")
        if atualizados:
            st.success(f"✅ {atualizados} linha(s) processada(s).")
            st.rerun()
    st.markdown("---")
    st.markdown("### Excluir ou transferir")
    labels = {
        f"{m['nome']} · {_fmt_cpf(m['cpf'])}" + (f" · RE:{m['re']}" if m.get("re") else ""): m
        for m in matriculas
    }
    selecionados = st.multiselect(
        "Selecione alunos", options=list(labels.keys()), key=f"multi_mat_{tid}",
        help="Para excluir da turma ou transferir.",
    )
    if not selecionados:
        st.caption("Selecione alunos acima para excluir ou transferir.")
        return
    col_ex, col_tr = st.columns(2)
    with col_ex:
        st.markdown("**🗑️ Excluir da turma**")
        confirmar = st.checkbox(f"Confirmo excluir {len(selecionados)} matrícula(s)", key=f"conf_del_multi_{tid}")
        if st.button("Excluir selecionados", type="primary", disabled=not confirmar, use_container_width=True, key=f"btn_del_multi_{tid}"):
            ok, erros = 0, []
            for lab in selecionados:
                m = labels[lab]
                try:
                    supabase.table("matriculas").delete().eq("id", m["matricula_id"]).execute()
                    ok += 1
                except Exception as e:
                    erros.append(f"{m['nome']}: {e}")
            if ok:
                st.success(f"✅ {ok} matrícula(s) removida(s).")
                st.rerun()
            for e in erros:
                st.error(e)
    with col_tr:
        st.markdown("**🔄 Transferir de turma**")
        try:
            outras = _carregar_outras_turmas(tid)
        except Exception as e:
            st.error(f"Erro: {e}")
            outras = []
        if not outras:
            st.info("Não há outras turmas disponíveis.")
        else:
            mapa_t = {t["label"]: t for t in outras}
            dest_label = st.selectbox("Turma de destino", options=list(mapa_t.keys()), key=f"dest_multi_{tid}")
            dest = mapa_t[dest_label]
            herdar = st.checkbox("Herdar data e carga da turma destino", value=True, key=f"herdar_multi_{tid}")
            if st.button(f"Transferir {len(selecionados)} aluno(s)", type="primary", use_container_width=True, key=f"btn_transf_multi_{tid}"):
                ok, erros = 0, []
                for lab in selecionados:
                    m = labels[lab]
                    try:
                        dup = (
                            supabase.table("matriculas").select("id")
                            .eq("turma_id", dest["id"]).eq("aluno_id", m["aluno_id"]).execute()
                        )
                        if dup and dup.data:
                            erros.append(f"{m['nome']}: já está na turma destino")
                            continue
                        payload = {"turma_id": dest["id"]}
                        if herdar:
                            if dest.get("data"):
                                payload["data_treinamento"] = dest["data"]
                            if dest.get("carga_horaria"):
                                payload["carga_horaria"] = dest["carga_horaria"]
                        supabase.table("matriculas").update(payload).eq("id", m["matricula_id"]).execute()
                        ok += 1
                    except Exception as e:
                        erros.append(f"{m['nome']}: {e}")
                if ok:
                    st.success(f"✅ {ok} aluno(s) transferido(s) para **{dest['titulo']}**.")
                    st.rerun()
                for e in erros:
                    st.warning(e)
