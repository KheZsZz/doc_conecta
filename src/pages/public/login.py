import time

import streamlit as st

from src.auth.local_auth import autenticar
from src.auth.permissions import normalizar_role

_MAX_TENTATIVAS = 5
_JANELA_SEG = 15 * 60  # 15 min
_BLOQUEIO_SEG = 15 * 60


def _estado_login() -> dict:
    if "login_security" not in st.session_state:
        st.session_state["login_security"] = {
            "falhas": 0,
            "primeira_falha": 0.0,
            "bloqueado_ate": 0.0,
        }
    return st.session_state["login_security"]


def _registrar_falha(sec: dict) -> None:
    agora = time.time()
    if agora - sec.get("primeira_falha", 0) > _JANELA_SEG:
        sec["falhas"] = 0
        sec["primeira_falha"] = agora
    if sec["falhas"] == 0:
        sec["primeira_falha"] = agora
    sec["falhas"] = int(sec.get("falhas") or 0) + 1
    if sec["falhas"] >= _MAX_TENTATIVAS:
        sec["bloqueado_ate"] = agora + _BLOQUEIO_SEG


def _registrar_sucesso(sec: dict) -> None:
    sec["falhas"] = 0
    sec["primeira_falha"] = 0.0
    sec["bloqueado_ate"] = 0.0


st.markdown(
    """
<div class="df-login-wrap">
  <div class="df-login-brand">
    <h1>DocFacil</h1>
    <p>Acesse com seu e-mail institucional</p>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

sec = _estado_login()
agora = time.time()
bloqueado_ate = float(sec.get("bloqueado_ate") or 0)

_, col, _ = st.columns([1, 1.2, 1])
with col:
    if bloqueado_ate > agora:
        mins = int((bloqueado_ate - agora) // 60) + 1
        st.error(
            f"Muitas tentativas de login. Tente novamente em cerca de **{mins} min**."
        )
        st.stop()

    with st.form("form_login", border=True):
        email = st.text_input("E-mail", placeholder="seu@email.com")
        senha = st.text_input("Senha", type="password", placeholder="••••••••")
        submit = st.form_submit_button(
            "Entrar",
            type="primary",
            use_container_width=True
        )

        if submit:
            if not email or not senha:
                st.warning("Informe e-mail e senha.")
            else:
                user, perfil, erro = autenticar(email.strip(), senha)
                if erro or not user:
                    _registrar_falha(sec)
                    restante = _MAX_TENTATIVAS - int(sec.get("falhas") or 0)
                    msg = erro or "Não foi possível entrar."
                    if restante > 0:
                        st.error(f"{msg} (tentativas restantes: {restante})")
                    else:
                        st.error(f"{msg} Acesso temporariamente bloqueado.")
                else:
                    role = normalizar_role((perfil or {}).get("role"))
                    if not role:
                        st.error(
                            "Usuário sem perfil de acesso válido. Contate o administrador."
                        )
                    else:
                        _registrar_sucesso(sec)
                        st.session_state.user = user
                        st.session_state.perfil = perfil or {}
                        st.session_state.role = role
                        st.rerun()
