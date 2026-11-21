from datetime import datetime

import streamlit as st

from src.config.database import supabase
from src.utils.checkin_token import validar_token

st.title("Check-in de presença")
st.caption("Acesso apenas pelo link da turma fornecido pelo instrutor.")


def formatar_data_br(data_str) -> str:
    if not data_str:
        return ""
    s = str(data_str).strip()[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return s


token = st.query_params.get("t") or st.query_params.get("token")
turma_id, erro_token = validar_token(token)
if erro_token or not turma_id:
    st.error(erro_token or "Link inválido.")
    st.info(
        "Peça ao instrutor ou ao CT um **novo link de check-in** para a turma de hoje."
    )
    st.stop()

try:
    turma_res = (
        supabase.table("turmas")
        .select(
            "id, titulo, data_treinamento, documento_emitido, client_id, carga_horaria, "
            "clients(id, name, cnpj, sigla)"
        )
        .eq("id", turma_id)
        .limit(1)
        .execute()
    )
    turma = (turma_res.data or [None])[0] if turma_res else None
except Exception:
    turma = None

if not turma:
    st.error("Turma não encontrada para este link.")
    st.stop()

if turma.get("documento_emitido"):
    st.warning("Esta turma já teve a documentação emitida. Check-in encerrado.")
    st.stop()

cli = turma.get("clients") if isinstance(turma.get("clients"), dict) else {}
client_id = turma.get("client_id") or cli.get("id")
empresa_nome = (cli.get("name") or "Empresa da turma").strip()
data_br = formatar_data_br(turma.get("data_treinamento"))
titulo = turma.get("titulo") or "Turma"

st.success(f"**Turma:** {titulo}  \n**Data:** {data_br}  \n**Empresa:** {empresa_nome}")

if not client_id:
    st.error("Turma sem empresa vinculada. Contate o administrador.")
    st.stop()

with st.form("form_checkin_aluno", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        nome = st.text_input("Nome completo*")
        cpf = st.text_input("CPF* (somente números)", max_chars=14)
    with col2:
        rg = st.text_input("RG (opcional)")
        email = st.text_input("E-mail (opcional)")

    enviar = st.form_submit_button(
        "Confirmar presença", type="primary", use_container_width=True
    )

    if enviar:
        cpf_limpo = "".join(ch for ch in (cpf or "") if ch.isdigit())
        if not nome or not cpf_limpo:
            st.warning("Nome e CPF são obrigatórios.")
        elif len(cpf_limpo) != 11:
            st.warning("CPF deve ter 11 dígitos.")
        else:
            try:
                aluno_id = None
                existente = (
                    supabase.table("alunos")
                    .select("id")
                    .eq("cpf", cpf_limpo)
                    .limit(1)
                    .execute()
                )
                if existente and existente.data:
                    aluno_id = existente.data[0]["id"]
                    # atualização mínima — não sobrescreve com vazio
                    upd = {"name": nome.strip().upper()}
                    if email and email.strip():
                        upd["email"] = email.strip()
                    if rg and rg.strip():
                        upd["rg"] = rg.strip()
                    supabase.table("alunos").update(upd).eq("id", aluno_id).execute()
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

                # evita matrícula duplicada
                ja = (
                    supabase.table("matriculas")
                    .select("id")
                    .eq("turma_id", turma_id)
                    .eq("aluno_id", aluno_id)
                    .limit(1)
                    .execute()
                )
                if ja and ja.data:
                    st.info("Presença já registrada nesta turma.")
                else:
                    supabase.table("matriculas").insert(
                        {
                            "aluno_id": aluno_id,
                            "turma_id": turma_id,
                            "client_id": client_id,
                            "carga_horaria": turma.get("carga_horaria") or "08 Horas",
                            "data_treinamento": turma.get("data_treinamento"),
                        }
                    ).execute()
                    st.success("Presença registrada com sucesso!")
            except Exception:
                st.error(
                    "Não foi possível registrar a presença. Tente de novo ou avise o instrutor."
                )
