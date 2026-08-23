import streamlit as st
from src.config.database import supabase

st.title("🏢 Gestão de Empresas")
st.markdown("Cadastre e gerencie os clientes e empresas para vinculá-los às turmas.")

tab_listar, tab_cadastrar = st.tabs(["📋 Empresas Cadastradas", "➕ Nova Empresa"])

# ==========================================
# 1. MODAL / POPUP DE EDIÇÃO DA EMPRESA
# ==========================================
@st.dialog("✏️ Editar Empresa", width="medium")
def modal_editar_empresa(empresa_id, nome_atual, sigla_atual, cnpj_atual, endereco_atual, responsavel_atual, phone_atual, email_atual):
    with st.form(f"form_edit_empresa_{empresa_id}"):
        novo_nome = st.text_input("Razão Social (name)*", value=nome_atual)
        
        col1, col2 = st.columns(2)
        with col1:
            nova_sigla = st.text_input("Sigla (Máx 5 caracteres)", value=sigla_atual if sigla_atual else "", max_chars=5)
            novo_cnpj = st.text_input("CNPJ (Até 14 dígitos)", value=cnpj_atual if cnpj_atual else "", max_chars=14)
            novo_telefone = st.text_input("Telefone (phone)", value=phone_atual if phone_atual else "")
        with col2:
            novo_responsavel = st.text_input("Responsável", value=responsavel_atual if responsavel_atual else "")
            novo_email = st.text_input("E-mail", value=email_atual if email_atual else "")
            
        novo_endereco = st.text_input("Endereço Completo (full_address)", value=endereco_atual if endereco_atual else "")
        
        salvar = st.form_submit_button("💾 Salvar Alterações", type="primary", use_container_width=True)
        
        if salvar:
            if not novo_nome.strip():
                st.warning("⚠️ A Razão Social é obrigatória.")
            else:
                try:
                    payload = {
                        "name": novo_nome.strip(),
                        "sigla": nova_sigla.strip().upper() if nova_sigla else None,
                        "cnpj": novo_cnpj.strip() if novo_cnpj else None,
                        "full_address": novo_endereco.strip() if novo_endereco else None,
                        "responsavel": novo_responsavel.strip() if novo_responsavel else None,
                        "phone": novo_telefone.strip() if novo_telefone else None,
                        "email": novo_email.strip() if novo_email else None
                    }
                    supabase.table("clients").update(payload).eq("id", empresa_id).execute()
                    st.success("✅ Empresa atualizada com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Erro ao atualizar empresa: {e}")

# ==========================================
# ABA 1: LISTAGEM DE EMPRESAS (EM CARDS)
# ==========================================
with tab_listar:
    st.subheader("Empresas e Clientes")
    
    try:
        response = supabase.table("clients").select("*").order("name").execute()
        
        if response and isinstance(response.data, list) and len(response.data) > 0:
            for emp in response.data:
                eid = emp.get("id")
                nome = emp.get("name", "Sem Nome")
                sigla = emp.get("sigla", "")
                cnpj = emp.get("cnpj", "")
                endereco = emp.get("full_address", "")
                responsavel = emp.get("responsavel", "")
                phone = emp.get("phone", "")
                email = emp.get("email", "")
                
                sigla_display = f" [{sigla}]" if sigla else ""
                
                # --- CARD EM LINHA COMPACTO ---
                with st.container(border=True):
                    col_info, col_acoes = st.columns([5, 1])
                    
                    with col_info:
                        st.markdown(f"**{nome}**{sigla_display}")
                        
                        detalhes = []
                        if cnpj: detalhes.append(f"**CNPJ:** {cnpj}")
                        if responsavel: detalhes.append(f"**Resp.:** {responsavel}")
                        if phone: detalhes.append(f"**Tel:** {phone}")
                        if email: detalhes.append(f"**E-mail:** {email}")
                        
                        if detalhes:
                            st.caption(" | ".join(detalhes))
                            
                        if endereco:
                            st.caption(f"📍 {endereco}")
                        
                    with col_acoes:
                        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                        if st.button("✏️", key=f"edit_emp_{eid}", help="Editar informações da empresa", use_container_width=True):
                            modal_editar_empresa(eid, nome, sigla, cnpj, endereco, responsavel, phone, email)
        else:
            st.info("ℹ️ Nenhuma empresa cadastrada no momento.")
            
    except Exception as e:
        st.error(f"Erro ao carregar empresas: {e}")

# ==========================================
# ABA 2: CADASTRO DE NOVA EMPRESA
# ==========================================
with tab_cadastrar:
    st.subheader("Cadastrar Nova Empresa")
    
    with st.form("form_nova_empresa", clear_on_submit=True):
        nome_empresa = st.text_input("Razão Social (name)*")
        
        col1, col2 = st.columns(2)
        with col1:
            sigla_empresa = st.text_input("Sigla (Máx 5 caracteres)", max_chars=5)
            cnpj_empresa = st.text_input("CNPJ (Até 14 dígitos)", max_chars=14)
            phone_empresa = st.text_input("Telefone (phone)")
        with col2:
            responsavel_empresa = st.text_input("Responsável")
            email_empresa = st.text_input("E-mail")
            
        endereco_empresa = st.text_input("Endereço Completo (full_address)")
        
        submit_btn = st.form_submit_button("Criar Empresa", type="primary")
        
        if submit_btn:
            if not nome_empresa.strip():
                st.warning("⚠️ A Razão Social é obrigatória.")
            else:
                try:
                    novo_payload = {
                        "name": nome_empresa.strip(),
                        "sigla": sigla_empresa.strip().upper() if sigla_empresa else None,
                        "cnpj": cnpj_empresa.strip() if cnpj_empresa else None,
                        "full_address": endereco_empresa.strip() if endereco_empresa else None,
                        "responsavel": responsavel_empresa.strip() if responsavel_empresa else None,
                        "phone": phone_empresa.strip() if phone_empresa else None,
                        "email": email_empresa.strip() if email_empresa else None
                    }
                    supabase.table("clients").insert(novo_payload).execute()
                    st.success(f"✅ Empresa '{nome_empresa}' cadastrada com sucesso!")
                    st.balloons()
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Erro ao cadastrar empresa: {e}")