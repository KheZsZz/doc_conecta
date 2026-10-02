import streamlit as st

from src.auth.local_auth import atualizar_senha, autenticar
from src.auth.permissions import ROLE_LABELS, role_atual

st.title("⚙️ Configurações")
st.markdown("Ajustes da sua conta e preferências do sistema.")

usuario = st.session_state.get("user")
email_logado = getattr(usuario, "email", None) if usuario else None
uid = getattr(usuario, "id", None) if usuario else None

if not email_logado or not uid:
    st.warning("Sessão inválida. Faça login novamente.")
    st.stop()

perfil = st.session_state.get("perfil") or {}
role = role_atual()
label = ROLE_LABELS.get(role, role)
nome = perfil.get("nome") or "—"

st.info(
    f"**Conta:** {email_logado}  \n"
    f"**Nome:** {nome}  \n"
    f"**Perfil:** {label}"
)

st.markdown("---")
st.subheader("🔑 Alterar minha senha")
st.caption("A senha fica na tabela de usuários (login local).")

with st.form("form_alterar_senha", clear_on_submit=True):
    senha_atual = st.text_input("Senha atual*", type="password")
    nova_senha = st.text_input(
        "Nova senha*", type="password", help="Mínimo de 6 caracteres."
    )
    confirmar = st.text_input("Confirmar nova senha*", type="password")

    enviar = st.form_submit_button(
        "💾 Salvar nova senha", type="primary", use_container_width=True
    )

    if enviar:
        if not senha_atual or not nova_senha or not confirmar:
            st.warning("⚠️ Preencha todos os campos.")
        elif len(nova_senha) < 6:
            st.warning("⚠️ A nova senha deve ter no mínimo 6 caracteres.")
        elif nova_senha != confirmar:
            st.warning("⚠️ A confirmação não confere com a nova senha.")
        elif nova_senha == senha_atual:
            st.warning("⚠️ A nova senha deve ser diferente da atual.")
        else:
            # Confere senha atual via auth local
            _, _, erro = autenticar(email_logado, senha_atual)
            if erro:
                st.error("❌ Senha atual incorreta.")
            else:
                ok, msg = atualizar_senha(str(uid), nova_senha)
                if ok:
                    st.success("✅ Senha alterada com sucesso!")
                else:
                    st.error(f"❌ {msg}")

st.markdown("---")
st.subheader("🚪 Sair do sistema")
st.caption("Encerra a sessão atual e volta para a tela de login.")

if st.button("🚪 Logout", type="primary", use_container_width=True):
    st.session_state.user = None
    st.session_state.perfil = None
    st.session_state.role = None
    st.rerun()
