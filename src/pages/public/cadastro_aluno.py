from datetime import datetime

import streamlit as st

from src.config.database import supabase

st.title("📱 Cadastro de Presença - Centro de Treinamento")
st.write("Selecione a turma em que você está participando hoje e preencha seus dados.")


def formatar_data_br(data_str) -> str:
    if not data_str:
        return ""
    s = str(data_str).strip()[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return s


turmas_dict = {}
empresas_dict = {}

try:
    turmas_res = (
        supabase.table("turmas")
        .select("id, titulo, data_treinamento, documento_emitido")
        .order("data_treinamento", desc=True)
        .limit(50)
        .execute()
    )

    if turmas_res and isinstance(turmas_res.data, list):
        for t in turmas_res.data:
            if not isinstance(t, dict):
                continue
            if t.get("documento_emitido"):
                continue
            titulo = str(t.get("titulo") or "Sem Título")
            data_br = formatar_data_br(t.get("data_treinamento"))
            tid = t.get("id")
            if tid:
                turmas_dict[f"{data_br} | {titulo}"] = tid

    clients_res = supabase.table("clients").select("id, name, cnpj").execute()

    if clients_res and isinstance(clients_res.data, list):
        for c in clients_res.data:
            if not isinstance(c, dict):
                continue
            cname = str(c.get("name") or "Empresa Sem Nome")
            ccnjp = str(c.get("cnpj") or "")
            cid = c.get("id")
            if cid:
                empresas_dict[f"{cname} (CNPJ: {ccnjp})"] = cid

except Exception as e:
    st.error(f"Erro de conexão ao carregar dados do banco: {e}")

if not turmas_dict:
    st.warning(
        "⚠️ Nenhuma turma pendente disponível no momento."
    )
    st.stop()

if not empresas_dict:
    st.warning(
        "⚠️ Nenhuma empresa cadastrada no sistema. Contate o administrador."
    )
    st.stop()

# Formulário de check-in
with st.form("form_checkin_aluno", clear_on_submit=True):
    turma_rotulo = st.selectbox("Turma*", options=list(turmas_dict.keys()))
    empresa_rotulo = st.selectbox("Empresa*", options=list(empresas_dict.keys()))

    col1, col2 = st.columns(2)
    with col1:
        nome = st.text_input("Nome completo*")
        cpf = st.text_input("CPF* (somente números)", max_chars=14)
    with col2:
        rg = st.text_input("RG (opcional)")
        email = st.text_input("E-mail (opcional)")

    enviar = st.form_submit_button("Confirmar presença", type="primary", use_container_width=True)

    if enviar:
        cpf_limpo = "".join(ch for ch in (cpf or "") if ch.isdigit())
        if not nome or not cpf_limpo:
            st.warning("Nome e CPF são obrigatórios.")
        elif len(cpf_limpo) != 11:
            st.warning("CPF deve ter 11 dígitos.")
        else:
            try:
                turma_id = turmas_dict[turma_rotulo]
                client_id = empresas_dict[empresa_rotulo]

                aluno_id = None
                existente = (
                    supabase.table("alunos")
                    .select("id")
                    .eq("cpf", cpf_limpo)
                    .execute()
                )
                if existente and existente.data:
                    aluno_id = existente.data[0]["id"]
                    supabase.table("alunos").update(
                        {
                            "name": nome.strip().upper(),
                            "email": email.strip() if email else None,
                            "rg": rg.strip() if rg else None,
                        }
                    ).eq("id", aluno_id).execute()
                else:
                    res = (
                        supabase.table("alunos")
                        .insert(
                            {
                                "name": nome.strip().upper(),
                                "cpf": cpf_limpo,
                                "email": email.strip() if email else None,
                                "rg": rg.strip() if rg else None,
                            }
                        )
                        .execute()
                    )
                    aluno_id = res.data[0]["id"]

                turma = (
                    supabase.table("turmas")
                    .select("data_treinamento, carga_horaria")
                    .eq("id", turma_id)
                    .single()
                    .execute()
                )
                tdata = turma.data if turma else {}

                supabase.table("matriculas").insert(
                    {
                        "aluno_id": aluno_id,
                        "turma_id": turma_id,
                        "client_id": client_id,
                        "carga_horaria": (tdata or {}).get("carga_horaria") or "08 Horas",
                        "data_treinamento": (tdata or {}).get("data_treinamento"),
                    }
                ).execute()

                st.success("✅ Presença registrada com sucesso!")
            except Exception as e:
                st.error(f"Erro ao registrar: {e}")
