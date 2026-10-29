import streamlit as st
from datetime import date, datetime
from src.config.database import supabase
from src.auth.permissions import ct_id_atual, is_consulta

st.title("🎓 Cadastro Individual de Alunos")
st.markdown(
    "Matricule alunos manualmente em turmas com documentação **pendente** "
    "**do dia de hoje**."
)

if is_consulta() and ct_id_atual():
    st.caption("Exibindo apenas turmas do **seu CT**.")


def formatar_data_br(data_str) -> str:
    if not data_str:
        return "—"
    s = str(data_str).strip()[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return s


# ==========================================
# 1. BUSCAR TURMAS PENDENTES DO DIA (hoje)
# ==========================================
hoje = date.today().isoformat()  # YYYY-MM-DD
turmas_dict = {}
turmas_info_completa = {}

try:
    res_turmas = (
        supabase.table("turmas")
        .select("*")
        .eq("data_treinamento", hoje)
        .order("titulo")
        .execute()
    )

    if res_turmas and res_turmas.data:
        for t in res_turmas.data:
            doc_emitido = bool(t.get("documento_emitido", False))
            # Empresas/turmas já emitidas não aparecem
            if doc_emitido:
                continue
            if is_consulta() and ct_id_atual():
                if str(t.get("ct_id") or "") != str(ct_id_atual()):
                    continue

            tid = t.get("id")
            titulo = (t.get("titulo") or "Sem título").strip()

            # Só o título na listagem (sem data e sem status)
            rotulo = titulo
            if rotulo in turmas_dict:
                rotulo = f"{titulo} ({str(tid)[:8]})"

            turmas_dict[rotulo] = tid
            turmas_info_completa[tid] = t

except Exception as e:
    st.error(f"Erro ao buscar turmas: {e}")

if not turmas_dict:
    st.info("Nenhuma turma pendente para hoje" + (" neste CT." if is_consulta() else "."))
    st.stop()

rotulo_sel = st.selectbox("Turma (hoje, pendente)*", options=list(turmas_dict.keys()))
turma_id = turmas_dict[rotulo_sel]
turma = turmas_info_completa.get(turma_id) or {}

st.caption(
    f"Data: {formatar_data_br(turma.get('data_treinamento'))} · "
    f"Carga: {turma.get('carga_horaria') or '—'}"
)

with st.form("form_matricula_manual", clear_on_submit=True):
    nome = st.text_input("Nome completo*")
    cpf = st.text_input("CPF")
    rg = st.text_input("RG")
    email = st.text_input("E-mail")
    phone = st.text_input("Telefone")
    ok = st.form_submit_button("✅ Matricular", type="primary", use_container_width=True)

    if ok:
        if not nome.strip():
            st.warning("Informe o nome do aluno.")
        else:
            try:
                # Garante aluno
                aluno_id = None
                cpf_digits = "".join(ch for ch in (cpf or "") if ch.isdigit())
                if cpf_digits:
                    r = (
                        supabase.table("alunos")
                        .select("id")
                        .eq("cpf", cpf_digits)
                        .limit(1)
                        .execute()
                    )
                    if r and r.data:
                        aluno_id = r.data[0]["id"]

                if not aluno_id:
                    payload_aluno = {
                        "name": nome.strip().upper(),
                        "cpf": cpf_digits or None,
                        "rg": (rg or "").strip() or None,
                        "email": (email or "").strip() or None,
                        "phone": (phone or "").strip() or None,
                    }
                    r = supabase.table("alunos").insert(payload_aluno).execute()
                    if r and r.data:
                        aluno_id = r.data[0]["id"]

                if not aluno_id:
                    st.error("Não foi possível criar/localizar o aluno.")
                else:
                    mat = {
                        "turma_id": turma_id,
                        "aluno_id": aluno_id,
                        "client_id": turma.get("client_id"),
                        "data_treinamento": turma.get("data_treinamento"),
                        "carga_horaria": turma.get("carga_horaria"),
                    }
                    supabase.table("matriculas").insert(mat).execute()
                    st.success(f"Aluno **{nome.strip().upper()}** matriculado.")
            except Exception as e:
                st.error(f"Erro ao matricular: {e}")
