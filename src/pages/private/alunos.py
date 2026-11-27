import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo
from src.config.database import supabase
from src.auth.permissions import ct_id_atual, is_consulta
from src.ui.styles import page_header
from src.utils.qrcode_turma import link_cadastro_turma, qrcode_png

page_header(
    "Alunos",
    "Gere o QR Code para a turma se cadastrar sozinha ou matricule manualmente.",
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
data_sel = st.date_input(
    "Data do treinamento",
    value=datetime.now(ZoneInfo("America/Sao_Paulo")).date(),
    format="DD/MM/YYYY",
)
hoje = data_sel.isoformat()  # YYYY-MM-DD
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
    st.info("Nenhuma turma pendente nesta data"+ (" neste CT." if is_consulta() else "."))
    st.stop()

rotulo_sel = st.selectbox("Turma (pendente)*", options=list(turmas_dict.keys()))
turma_id = turmas_dict[rotulo_sel]
turma = turmas_info_completa.get(turma_id) or {}

st.caption(
    f"Data: {formatar_data_br(turma.get('data_treinamento'))} · "
    f"Carga: {turma.get('carga_horaria') or '—'}"
)

tab_qr, tab_manual = st.tabs([":material/qr_code_2: QR Code da turma", ":material/person_add: Cadastro manual"])

with tab_qr:
    link = link_cadastro_turma(str(turma_id))
    png = qrcode_png(link)
    col_qr, col_info = st.columns([1, 1.3])
    with col_qr:
        st.image(png, width=260)
    with col_info:
        st.markdown(f"**{rotulo_sel}**")
        st.caption(
            "Os alunos escaneiam e preenchem Nome e CPF (Bombeiro Civil: Nome, CPF, RG e RE). "
            "Não precisa de login. O cadastro fecha quando os documentos forem emitidos."
        )
        st.code(link, language=None)
        st.download_button(
            "Baixar QR Code (PNG)",
            data=png,
            file_name=f"qrcode_{rotulo_sel[:40].replace(' ', '_')}.png",
            mime="image/png",
            type="primary",
            width="stretch",
        )
        st.link_button("Abrir formulário", link, width="stretch")

with tab_manual, st.form("form_matricula_manual", clear_on_submit=True):
    nome = st.text_input("Nome completo*")
    c1, c2 = st.columns(2)
    cpf = c1.text_input("CPF")
    rg = c2.text_input("RG")
    c3, c4 = st.columns(2)
    email = c3.text_input("E-mail")
    phone = c4.text_input("Telefone")
    ok = st.form_submit_button("Matricular", type="primary", width="stretch")

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
