"""Cadastro público de alunos (acesso via QR Code, sem login).

URLs:
  /alunos?turma=<uuid>   -> turma fixa (link do QR Code da turma)
  /alunos                -> aluno escolhe entre as turmas pendentes de hoje
"""
from __future__ import annotations

import html
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

import streamlit as st

from src.config.database import supabase
from src.utils.cursos_helpers import (
    cpf_valido,
    eh_curso_bombeiro,
    formatar_cpf,
    somente_digitos,
)

TZ = ZoneInfo("America/Sao_Paulo")
UUID_RE = re.compile(r"^[0-9a-fA-F-]{36}$")
SS_SUCESSO = "cad_aluno_sucesso"


# ---------------------------------------------------------------------------
# Estilo (mobile-first, sem sidebar)
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
  [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"],
  [data-testid="stSidebarNav"], header[data-testid="stHeader"] { display: none !important; }
  .block-container { max-width: 560px !important; padding: 1.25rem 1rem 3rem !important; }

  .cad-brand { display:flex; align-items:center; gap:.6rem; margin:.25rem 0 1.1rem; }
  .cad-brand-mark { width:36px; height:36px; border-radius:10px; display:grid; place-items:center;
    background:linear-gradient(135deg,#c0392b,#e67e22); color:#fff; font-size:1.15rem; }
  .cad-brand-name { font-weight:700; font-size:1rem; letter-spacing:-.01em; }
  .cad-brand-sub { font-size:.78rem; opacity:.65; margin-top:-2px; }

  .cad-turma { border-radius:16px; padding:1.1rem 1.2rem; margin-bottom:1rem; color:#fff;
    background:linear-gradient(135deg,#0b1f3a 0%,#123a6b 60%,#1a5f9e 100%);
    box-shadow:0 8px 24px rgba(11,31,58,.18); }
  .cad-turma.bombeiro { background:linear-gradient(135deg,#5c1010 0%,#9b1c1c 55%,#d35400 100%); }
  .cad-turma-label { font-size:.72rem; text-transform:uppercase; letter-spacing:.08em; opacity:.75; }
  .cad-turma-titulo { font-size:1.2rem; font-weight:700; line-height:1.25; margin:.2rem 0 .6rem; }
  .cad-chips { display:flex; flex-wrap:wrap; gap:.4rem; }
  .cad-chip { background:rgba(255,255,255,.16); border:1px solid rgba(255,255,255,.22);
    border-radius:999px; padding:.18rem .65rem; font-size:.8rem; }

  .cad-secao { font-size:.78rem; font-weight:700; text-transform:uppercase; letter-spacing:.06em;
    opacity:.6; margin:.4rem 0 .2rem; }
  .cad-nota { font-size:.82rem; opacity:.7; margin:-.2rem 0 .6rem; }

  .cad-ok { text-align:center; padding:2rem 1.2rem 1.4rem; border-radius:18px;
    border:1px solid rgba(30,126,52,.25); background:rgba(30,126,52,.06); margin-top:1rem; }
  .cad-ok-icon { width:64px; height:64px; margin:0 auto .8rem; border-radius:50%;
    display:grid; place-items:center; background:#1e7e34; color:#fff; font-size:2rem; }
  .cad-ok h2 { font-size:1.35rem !important; margin:0 0 .35rem !important; }
  .cad-ok p { margin:.15rem 0; opacity:.8; }

  div[data-testid="stForm"] { border-radius:16px; }
  div[data-testid="stFormSubmitButton"] button { min-height:3rem; font-size:1rem; font-weight:600; }
  input { font-size:16px !important; } /* evita zoom no iOS */
</style>
<div class="cad-brand">
  <div class="cad-brand-mark">🔥</div>
  <div>
    <div class="cad-brand-name">DocFácil Conecta</div>
    <div class="cad-brand-sub">Cadastro de alunos para emissão de documentos</div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Dados
# ---------------------------------------------------------------------------
def formatar_data_br(valor) -> str:
    s = str(valor or "").strip()[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return s


def carregar_cursos(ids: list[str]) -> dict[str, dict]:
    ids = [i for i in {str(x) for x in ids if x}]
    if not ids:
        return {}
    res = supabase.table("cursos").select("id, name, sigla").in_("id", ids).execute()
    return {str(c["id"]): c for c in (res.data or [])}


@st.cache_data(ttl=60, show_spinner=False)
def carregar_turma(turma_id: str) -> dict | None:
    res = (
        supabase.table("turmas")
        .select("id, titulo, data_treinamento, carga_horaria, client_id, curso_id, documento_emitido")
        .eq("id", turma_id)
        .limit(1)
        .execute()
    )
    if not res.data:
        return None
    turma = res.data[0]
    turma["curso"] = carregar_cursos([turma.get("curso_id")]).get(str(turma.get("curso_id")), {})
    return turma


@st.cache_data(ttl=60, show_spinner=False)
def carregar_turmas_hoje(hoje: str) -> list[dict]:
    res = (
        supabase.table("turmas")
        .select("id, titulo, data_treinamento, carga_horaria, client_id, curso_id, documento_emitido")
        .eq("data_treinamento", hoje)
        .order("titulo")
        .execute()
    )
    turmas = [t for t in (res.data or []) if not t.get("documento_emitido")]
    cursos = carregar_cursos([t.get("curso_id") for t in turmas])
    for t in turmas:
        t["curso"] = cursos.get(str(t.get("curso_id")), {})
    return turmas


def salvar_cadastro(turma: dict, dados: dict) -> tuple[str, bool]:
    """Cria/atualiza o aluno e matricula na turma. Retorna (nome, ja_matriculado)."""
    cpf = dados["cpf"]
    existente = supabase.table("alunos").select("id").eq("cpf", cpf).limit(1).execute()

    # Só grava campos preenchidos, para não apagar dados já existentes.
    campos = {k: v for k, v in dados.items() if v not in (None, "")}

    if existente.data:
        aluno_id = existente.data[0]["id"]
        atualizar = {k: v for k, v in campos.items() if k != "cpf"}
        if atualizar:
            supabase.table("alunos").update(atualizar).eq("id", aluno_id).execute()
    else:
        res = supabase.table("alunos").insert(campos).execute()
        aluno_id = res.data[0]["id"]

    ja = (
        supabase.table("matriculas")
        .select("id")
        .eq("aluno_id", aluno_id)
        .eq("turma_id", turma["id"])
        .limit(1)
        .execute()
    )
    if ja.data:
        return dados["name"], True

    supabase.table("matriculas").insert(
        {
            "aluno_id": aluno_id,
            "turma_id": turma["id"],
            "client_id": turma.get("client_id"),
            "curso_id": turma.get("curso_id"),
            "carga_horaria": turma.get("carga_horaria"),
            "data_treinamento": str(turma.get("data_treinamento") or "")[:10] or None,
        }
    ).execute()
    return dados["name"], False


# ---------------------------------------------------------------------------
# Tela de sucesso
# ---------------------------------------------------------------------------
sucesso = st.session_state.get(SS_SUCESSO)
if sucesso:
    titulo_ok = "Você já estava cadastrado!" if sucesso["ja"] else "Cadastro concluído!"
    st.markdown(
        f"""
<div class="cad-ok">
  <div class="cad-ok-icon">✓</div>
  <h2>{titulo_ok}</h2>
  <p><strong>{html.escape(sucesso["nome"])}</strong></p>
  <p>CPF {html.escape(sucesso["cpf"])}</p>
  <p style="margin-top:.6rem">{html.escape(sucesso["turma"])}</p>
</div>
""",
        unsafe_allow_html=True,
    )
    st.write("")
    if st.button("Cadastrar outra pessoa", type="secondary", width="stretch"):
        del st.session_state[SS_SUCESSO]
        st.rerun()
    st.stop()


# ---------------------------------------------------------------------------
# Seleção da turma
# ---------------------------------------------------------------------------
turma_param = str(st.query_params.get("turma") or "").strip()
turma: dict | None = None

try:
    if turma_param:
        if not UUID_RE.match(turma_param):
            st.error("Link inválido. Peça ao instrutor um novo QR Code.")
            st.stop()
        turma = carregar_turma(turma_param)
        if not turma:
            st.error("Turma não encontrada. Peça ao instrutor um novo QR Code.")
            st.stop()
        if turma.get("documento_emitido"):
            st.warning("Os documentos desta turma já foram emitidos e o cadastro foi encerrado.")
            st.stop()
    else:
        hoje = datetime.now(TZ).date().isoformat()
        turmas = carregar_turmas_hoje(hoje)
        if not turmas:
            st.info("Nenhuma turma aberta para cadastro hoje. Confirme o QR Code com o instrutor.")
            st.stop()
        opcoes = {t["id"]: t for t in turmas}
        tid = st.selectbox(
            "Selecione sua turma",
            options=list(opcoes.keys()),
            format_func=lambda i: opcoes[i].get("titulo") or "Sem título",
            index=None,
            placeholder="Toque para escolher…",
        )
        if not tid:
            st.stop()
        turma = opcoes[tid]
except Exception as e:  # noqa: BLE001
    st.error(f"Não foi possível carregar as turmas. Tente novamente em instantes. ({e})")
    st.stop()

curso = turma.get("curso") or {}
bombeiro = eh_curso_bombeiro(curso.get("name", ""), curso.get("sigla", ""))

chips = [f"📅 {formatar_data_br(turma.get('data_treinamento'))}"]
if turma.get("carga_horaria"):
    chips.append(f"⏱ {turma['carga_horaria']}")
if curso.get("sigla") or curso.get("name"):
    chips.append(f"📘 {curso.get('sigla') or curso.get('name')}")

st.markdown(
    f"""
<div class="cad-turma{' bombeiro' if bombeiro else ''}">
  <div class="cad-turma-label">Sua turma</div>
  <div class="cad-turma-titulo">{html.escape(turma.get('titulo') or 'Sem título')}</div>
  <div class="cad-chips">{''.join(f'<span class="cad-chip">{html.escape(c)}</span>' for c in chips)}</div>
</div>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Formulário
# ---------------------------------------------------------------------------
with st.form("form_cadastro_publico", border=True):
    st.markdown('<div class="cad-secao">Dados obrigatórios</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="cad-nota">Preencha exatamente como no seu documento — '
        "é assim que sairá no certificado.</div>",
        unsafe_allow_html=True,
    )
    nome = st.text_input("Nome completo *", placeholder="Ex.: Maria da Silva Souza")
    cpf = st.text_input("CPF *", placeholder="000.000.000-00", max_chars=14)

    if bombeiro:
        rg = st.text_input("RG *", placeholder="Somente o número do RG")
        re_aluno = st.text_input("RE *", placeholder="Número do Registro (RE)")
        st.markdown('<div class="cad-secao">Opcionais</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="cad-secao">Opcionais</div>', unsafe_allow_html=True)
        rg = st.text_input("RG")
        re_aluno = ""

    data_nasc = st.date_input(
        "Data de nascimento",
        value=None,
        min_value=date(1930, 1, 1),
        max_value=date.today(),
        format="DD/MM/YYYY",
    )
    telefone = st.text_input("Telefone / WhatsApp", placeholder="(11) 90000-0000")
    email = st.text_input("E-mail", placeholder="voce@email.com")

    enviar = st.form_submit_button("Confirmar cadastro", type="primary", width="stretch")

if enviar:
    nome_ok = re.sub(r"\s+", " ", (nome or "")).strip().upper()
    cpf_ok = somente_digitos(cpf)
    rg_ok = (rg or "").strip().upper()
    re_ok = (re_aluno or "").strip().upper()
    email_ok = (email or "").strip().lower()

    erros: list[str] = []
    if len(nome_ok.split(" ")) < 2:
        erros.append("Informe o **nome completo** (nome e sobrenome).")
    if not cpf_ok:
        erros.append("Informe o **CPF**.")
    elif not cpf_valido(cpf_ok):
        erros.append("**CPF inválido.** Confira os números.")
    if bombeiro:
        if not rg_ok:
            erros.append("Informe o **RG**.")
        if not re_ok:
            erros.append("Informe o **RE**.")
    if email_ok and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email_ok):
        erros.append("**E-mail inválido.**")

    if erros:
        st.error("\n\n".join(erros))
    else:
        dados = {
            "name": nome_ok,
            "cpf": cpf_ok,
            "rg": rg_ok or None,
            "re": re_ok or None,
            "email": email_ok or None,
            "phone": (telefone or "").strip() or None,
            "data_nasc": data_nasc.isoformat() if data_nasc else None,
        }
        try:
            with st.spinner("Salvando…"):
                nome_salvo, ja = salvar_cadastro(turma, dados)
            st.session_state[SS_SUCESSO] = {
                "nome": nome_salvo,
                "cpf": formatar_cpf(cpf_ok),
                "turma": turma.get("titulo") or "",
                "ja": ja,
            }
            st.rerun()
        except Exception as e:  # noqa: BLE001
            st.error(f"Não foi possível salvar seu cadastro. Tente novamente. ({e})")

st.caption("Seus dados são usados apenas para emissão dos documentos do treinamento.")
