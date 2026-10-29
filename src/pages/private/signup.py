from datetime import datetime

import streamlit as st

from src.config.database import supabase
from src.auth.local_auth import atualizar_senha, criar_usuario
from src.auth.permissions import (
    ROLE_CONSULTA,
    ROLE_HELP,
    ROLE_LABELS,
    ROLE_OPERACIONAL,
    ROLES,
    exigir_permissao,
    is_admin,
    normalizar_role,
)

exigir_permissao("usuarios")

st.title("👤 Gestão de Usuários")
st.markdown("Cadastre, liste e defina o perfil de acesso de cada usuário.")

with st.expander("O que cada perfil pode fazer", expanded=False):
    for r in ROLES:
        st.markdown(f"- **{ROLE_LABELS[r]}**: {ROLE_HELP[r]}")


def _listar_cts() -> list[dict]:
    try:
        res = supabase.table("cts").select("id, name, full_name").order("name").execute()
        return res.data if res and isinstance(res.data, list) else []
    except Exception:
        return []


def _cts_opcoes() -> tuple[list[str], dict[str, str]]:
    """Retorna labels e mapa label→id (inclui '— Sem CT —')."""
    cts = _listar_cts()
    labels = ["— Sem CT —"]
    mapa = {"— Sem CT —": ""}
    for c in cts:
        lab = c.get("name") or c.get("full_name") or str(c.get("id"))
        labels.append(lab)
        mapa[lab] = c["id"]
    return labels, mapa


def _label_ct_por_id(ct_id, labels, mapa) -> str:
    if not ct_id:
        return "— Sem CT —"
    for lab, cid in mapa.items():
        if str(cid) == str(ct_id):
            return lab
    return "— Sem CT —"


tab_listar, tab_cadastrar = st.tabs(["📋 Usuários Cadastrados", "➕ Cadastrar Usuário"])


def _opcoes_role() -> list[str]:
    return [ROLE_LABELS[r] for r in ROLES]


def _label_para_role(label: str) -> str:
    for r, lab in ROLE_LABELS.items():
        if lab == label:
            return r
    return ROLE_OPERACIONAL


@st.dialog("✏️ Editar Usuário", width="medium")
def modal_editar_usuario(
    usuario_id,
    nome_atual,
    email_atual,
    phone_atual,
    ativo_atual,
    role_atual_user,
    ct_id_atual_user=None,
):
    st.caption(f"E-mail: **{email_atual or '—'}**")
    ct_labels, ct_mapa = _cts_opcoes()

    with st.form(f"form_edit_usuario_{usuario_id}"):
        novo_nome = st.text_input("Nome Completo*", value=nome_atual or "")
        novo_phone = st.text_input("Telefone", value=phone_atual or "")
        novo_ativo = st.checkbox("Usuário ativo", value=bool(ativo_atual))

        role_norm = normalizar_role(role_atual_user)
        idx = ROLES.index(role_norm) if role_norm in ROLES else 1
        novo_role_label = st.selectbox("Perfil de acesso*", options=_opcoes_role(), index=idx)

        ct_default = _label_ct_por_id(ct_id_atual_user, ct_labels, ct_mapa)
        idx_ct = ct_labels.index(ct_default) if ct_default in ct_labels else 0
        ct_label = st.selectbox(
            "CT vinculado (obrigatório para Adm. de CT)",
            options=ct_labels,
            index=idx_ct,
        )

        st.markdown("---")
        st.caption("Preencha apenas se quiser trocar a senha.")
        nova_senha = st.text_input("Nova senha", type="password")
        conf_senha = st.text_input("Confirmar nova senha", type="password")

        salvar = st.form_submit_button("💾 Salvar", type="primary", use_container_width=True)

        if salvar:
            role_novo = _label_para_role(novo_role_label)
            ct_novo = ct_mapa.get(ct_label) or None
            if not novo_nome.strip():
                st.warning("Nome obrigatório.")
            elif role_novo == ROLE_CONSULTA and not ct_novo:
                st.warning("Perfil Adm. de CT exige um CT vinculado.")
            elif nova_senha and len(nova_senha) < 6:
                st.warning("Senha mínima: 6 caracteres.")
            elif nova_senha and nova_senha != conf_senha:
                st.warning("Confirmação de senha não confere.")
            else:
                try:
                    payload = {
                        "nome": novo_nome.strip(),
                        "phone": novo_phone.strip() if novo_phone else None,
                        "is_active": novo_ativo,
                        "role": role_novo,
                        "ct_id": ct_novo if role_novo == ROLE_CONSULTA else None,
                        "updated_at": datetime.now().isoformat(),
                    }
                    supabase.table("usuarios").update(payload).eq("id", usuario_id).execute()
                    if nova_senha:
                        ok, msg = atualizar_senha(usuario_id, nova_senha)
                        if not ok:
                            st.error(msg)
                            st.stop()
                    st.success("Usuário atualizado.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")


@st.dialog("🗑️ Remover Usuário", width="small")
def modal_remover_usuario(usuario_id, nome, email):
    st.warning(f"Remover **{nome}** ({email})?")
    confirmar = st.checkbox("Confirmo a exclusão", key=f"conf_del_{usuario_id}")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Cancelar", key=f"c_{usuario_id}", use_container_width=True):
            st.rerun()
    with c2:
        if st.button(
            "Excluir",
            type="primary",
            disabled=not confirmar,
            key=f"d_{usuario_id}",
            use_container_width=True,
        ):
            try:
                supabase.table("usuarios").delete().eq("id", usuario_id).execute()
                st.success("Removido.")
                st.rerun()
            except Exception as e:
                st.error(str(e))


with tab_listar:
    try:
        res = supabase.table("usuarios").select("*").order("nome").execute()
        usuarios = res.data if res and res.data else []
        if not usuarios:
            st.info("Nenhum usuário cadastrado.")
        else:
            ct_labels, ct_mapa = _cts_opcoes()
            id_para_nome = {v: k for k, v in ct_mapa.items() if v}

            for u in usuarios:
                uid = u.get("id")
                nome = u.get("nome") or "—"
                email = u.get("email") or ""
                phone = u.get("phone") or ""
                ativo = u.get("is_active", True)
                role_u = normalizar_role(u.get("role"))
                tem_senha = bool(u.get("password_hash"))
                status = "✅ Ativo" if ativo else "⛔ Inativo"
                senha_flag = "🔑 Senha ok" if tem_senha else "⚠️ Sem senha"
                ct_nome = id_para_nome.get(str(u.get("ct_id") or ""), "")

                with st.container(border=True):
                    c1, c2, c3 = st.columns([4, 1.2, 1.2])
                    with c1:
                        st.markdown(
                            f"**{nome}** · {status} · **{ROLE_LABELS.get(role_u, role_u)}** · {senha_flag}"
                        )
                        parts = [f"📧 {email}"]
                        if phone:
                            parts.append(f"📞 {phone}")
                        if ct_nome and ct_nome != "— Sem CT —":
                            parts.append(f"🏢 CT: {ct_nome}")
                        st.caption(" · ".join(parts))
                    with c2:
                        if st.button("✏️ Editar", key=f"e_{uid}", use_container_width=True):
                            modal_editar_usuario(
                                uid,
                                nome,
                                email,
                                phone,
                                ativo,
                                role_u,
                                u.get("ct_id"),
                            )
                    with c3:
                        if st.button("🗑️ Remover", key=f"r_{uid}", use_container_width=True):
                            modal_remover_usuario(uid, nome, email)
    except Exception as e:
        st.error(f"Erro ao listar usuários: {e}")


with tab_cadastrar:
    if not is_admin():
        st.error("Apenas administradores podem cadastrar usuários.")
        st.stop()

    st.subheader("Cadastrar Usuário")
    ct_labels, ct_mapa = _cts_opcoes()

    with st.form("form_novo_user", clear_on_submit=True):
        nome = st.text_input("Nome Completo*")
        phone = st.text_input("Telefone")
        email = st.text_input("E-mail*")
        role_label = st.selectbox("Perfil*", options=_opcoes_role(), index=1)
        st.caption(ROLE_HELP.get(_label_para_role(role_label), ""))
        ct_label = st.selectbox(
            "CT vinculado (obrigatório se perfil = Adm. de CT)",
            options=ct_labels,
            index=0,
        )
        senha = st.text_input("Senha*", type="password")
        conf = st.text_input("Confirmar Senha*", type="password")
        ok = st.form_submit_button("✅ Cadastrar", type="primary", use_container_width=True)

        if ok:
            role = _label_para_role(role_label)
            ct_id = ct_mapa.get(ct_label) or None
            if not nome or not email or not senha:
                st.warning("Preencha os campos obrigatórios.")
            elif senha != conf:
                st.warning("Senhas não coincidem.")
            elif len(senha) < 6:
                st.warning("Senha mínima: 6 caracteres.")
            elif role == ROLE_CONSULTA and not ct_id:
                st.warning("Perfil Adm. de CT exige selecionar um CT.")
            else:
                reg, erro = criar_usuario(
                    nome=nome,
                    email=email,
                    senha=senha,
                    phone=phone,
                    role=role,
                    ct_id=ct_id if role == ROLE_CONSULTA else None,
                )
                if erro:
                    st.error(erro)
                else:
                    extra = f" · CT vinculado" if role == ROLE_CONSULTA else ""
                    st.success(
                        f"Usuário **{nome}** cadastrado como **{role_label}**{extra}."
                    )
