import streamlit as st
from src.config.database import supabase

st.title("🏢 Gestão de Empresas")
st.markdown("Cadastre e gerencie os clientes e empresas para vinculá-los às turmas.")

tab_listar, tab_cadastrar = st.tabs(["📋 Empresas Cadastradas", "➕ Nova Empresa"])


@st.dialog("✏️ Editar Empresa", width="medium")
def modal_editar_empresa(
    empresa_id,
    nome_atual,
    unidade_atual,
    cnpj_atual,
    endereco_atual,
    responsavel_atual,
    phone_atual,
    email_atual,
):
    with st.form(f"form_edit_empresa_{empresa_id}"):
        novo_nome = st.text_input("Razão Social*", value=nome_atual)

        col1, col2 = st.columns(2)
        with col1:
            nova_unidade = st.text_input(
                "Unidade",
                value=unidade_atual if unidade_atual else "",
                help="Identificação livre da unidade (ex.: Indaiatuba, SP-075, Planta 2).",
            )
            novo_cnpj = st.text_input(
                "CNPJ (Até 14 dígitos)",
                value=cnpj_atual if cnpj_atual else "",
                max_chars=14,
            )
            novo_telefone = st.text_input(
                "Telefone", value=phone_atual if phone_atual else ""
            )
        with col2:
            novo_responsavel = st.text_input(
                "Responsável", value=responsavel_atual if responsavel_atual else ""
            )
            novo_email = st.text_input(
                "E-mail", value=email_atual if email_atual else ""
            )

        novo_endereco = st.text_input(
            "Endereço Completo",
            value=endereco_atual if endereco_atual else "",
        )

        salvar = st.form_submit_button(
            "💾 Salvar Alterações", type="primary", use_container_width=True
        )

        if salvar:
            if not novo_nome.strip():
                st.warning("⚠️ A Razão Social é obrigatória.")
            else:
                try:
                    payload = {
                        "name": novo_nome.strip(),
                        "sigla": nova_unidade.strip() if nova_unidade else None,
                        "cnpj": novo_cnpj.strip() if novo_cnpj else None,
                        "full_address": novo_endereco.strip()
                        if novo_endereco
                        else None,
                        "responsavel": novo_responsavel.strip()
                        if novo_responsavel
                        else None,
                        "phone": novo_telefone.strip() if novo_telefone else None,
                        "email": novo_email.strip() if novo_email else None,
                    }
                    supabase.table("clients").update(payload).eq(
                        "id", empresa_id
                    ).execute()
                    st.success("✅ Empresa atualizada com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Erro ao atualizar empresa: {e}")


with tab_listar:
    st.subheader("Empresas e Clientes")

    busca = st.text_input(
        "🔍 Buscar por nome, unidade ou CNPJ",
        placeholder="Ex: Indaiatuba, KION, 42365296001085...",
        key="busca_empresa",
    )

    try:
        response = supabase.table("clients").select("*").order("name").execute()

        if response and isinstance(response.data, list) and len(response.data) > 0:
            lista = response.data
            if busca.strip():
                q = busca.strip().lower()
                q_digits = "".join(ch for ch in q if ch.isdigit())
                filtradas = []
                for emp in lista:
                    nome = str(emp.get("name") or "").lower()
                    unidade = str(emp.get("sigla") or "").lower()
                    cnpj = str(emp.get("cnpj") or "")
                    cnpj_digits = "".join(ch for ch in cnpj if ch.isdigit())
                    if (
                        q in nome
                        or q in unidade
                        or q in cnpj.lower()
                        or (q_digits and q_digits in cnpj_digits)
                    ):
                        filtradas.append(emp)
                lista = filtradas

            if not lista:
                st.info("Nenhuma empresa encontrada com esse filtro.")
            else:
                st.caption(f"Exibindo **{len(lista)}** empresa(s).")
                for emp in lista:
                    eid = emp.get("id")
                    nome = emp.get("name", "Sem Nome")
                    unidade = emp.get("sigla", "") or ""
                    cnpj = emp.get("cnpj", "")
                    endereco = emp.get("full_address", "")
                    responsavel = emp.get("responsavel", "")
                    phone = emp.get("phone", "")
                    email = emp.get("email", "")

                    unidade_display = f" · {unidade}" if unidade else ""

                    with st.container(border=True):
                        col_info, col_acoes = st.columns([5, 1])

                        with col_info:
                            st.markdown(f"**{nome}**{unidade_display}")

                            detalhes = []
                            if cnpj:
                                detalhes.append(f"**CNPJ:** {cnpj}")
                            if unidade:
                                detalhes.append(f"**Unidade:** {unidade}")
                            if responsavel:
                                detalhes.append(f"**Resp.:** {responsavel}")
                            if phone:
                                detalhes.append(f"**Tel:** {phone}")
                            if email:
                                detalhes.append(f"**E-mail:** {email}")

                            if detalhes:
                                st.caption(" | ".join(detalhes))

                            if endereco:
                                st.caption(f"📍 {endereco}")

                        with col_acoes:
                            st.markdown(
                                "<div style='height: 10px;'></div>",
                                unsafe_allow_html=True,
                            )
                            if st.button(
                                "✏️",
                                key=f"edit_emp_{eid}",
                                help="Editar empresa",
                                use_container_width=True,
                            ):
                                modal_editar_empresa(
                                    eid,
                                    nome,
                                    unidade,
                                    cnpj,
                                    endereco,
                                    responsavel,
                                    phone,
                                    email,
                                )
        else:
            st.info("ℹ️ Nenhuma empresa cadastrada no momento.")

    except Exception as e:
        st.error(f"Erro ao carregar empresas: {e}")


with tab_cadastrar:
    st.subheader("Cadastrar Nova Empresa")

    with st.form("form_nova_empresa", clear_on_submit=True):
        nome_empresa = st.text_input("Razão Social*")

        col1, col2 = st.columns(2)
        with col1:
            unidade_empresa = st.text_input(
                "Unidade",
                help="Identificação livre da unidade (ex.: Indaiatuba, SP-075, Planta 2).",
            )
            cnpj_empresa = st.text_input("CNPJ (Até 14 dígitos)", max_chars=14)
            phone_empresa = st.text_input("Telefone")
        with col2:
            responsavel_empresa = st.text_input("Responsável")
            email_empresa = st.text_input("E-mail")

        endereco_empresa = st.text_input("Endereço Completo")

        submit_btn = st.form_submit_button("Criar Empresa", type="primary")

        if submit_btn:
            if not nome_empresa.strip():
                st.warning("⚠️ A Razão Social é obrigatória.")
            else:
                try:
                    novo_payload = {
                        "name": nome_empresa.strip(),
                        "sigla": unidade_empresa.strip()
                        if unidade_empresa
                        else None,
                        "cnpj": cnpj_empresa.strip() if cnpj_empresa else None,
                        "full_address": endereco_empresa.strip()
                        if endereco_empresa
                        else None,
                        "responsavel": responsavel_empresa.strip()
                        if responsavel_empresa
                        else None,
                        "phone": phone_empresa.strip() if phone_empresa else None,
                        "email": email_empresa.strip() if email_empresa else None,
                    }
                    supabase.table("clients").insert(novo_payload).execute()
                    st.success(f"✅ Empresa '{nome_empresa}' cadastrada com sucesso!")
                    st.balloons()
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Erro ao cadastrar empresa: {e}")
