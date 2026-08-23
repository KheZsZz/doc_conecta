import streamlit as st
import os
from src.config.database import supabase

st.title("👨‍🏫 Gestão de Instrutores")
st.markdown("Cadastre os instrutores e gerencie suas informações profissionais, status e assinaturas.")

# Cria a pasta de assinaturas caso não exista
PASTA_ASSINATURAS = "assets/assinaturas"
os.makedirs(PASTA_ASSINATURAS, exist_ok=True)

tab_listar, tab_cadastrar = st.tabs(["📋 Instrutores Cadastrados", "➕ Novo Instrutor"])

# ==========================================
# 1. MODAL / POPUP DE EDIÇÃO DO INSTRUTOR
# ==========================================
@st.dialog("✏️ Editar Instrutor", width="medium")
def modal_editar_instrutor(instrutor_id, nome_atual, cpf_atual, email_atual, phone_atual, cbo_atual, assinatura_atual, ativo_atual):
    with st.form(f"form_edit_instrutor_{instrutor_id}"):
        novo_nome = st.text_input("Nome Completo (name)*", value=nome_atual)
        
        col1, col2 = st.columns(2)
        with col1:
            novo_cpf = st.text_input("CPF (11 dígitos)*", value=cpf_atual if cpf_atual else "", max_chars=11)
            novo_phone = st.text_input("Telefone (phone)", value=phone_atual if phone_atual else "", max_chars=11)
            novo_cbo = st.text_input("CBO", value=cbo_atual if cbo_atual else "")
        with col2:
            novo_email = st.text_input("E-mail", value=email_atual if email_atual else "")
            
        st.markdown("---")
        st.write("✍️ **Assinatura do Instrutor**")
        if assinatura_atual:
            st.caption(f"Arquivo atual cadastrado: `{assinatura_atual}`")
            
        arquivo_assinatura = st.file_uploader("Enviar nova imagem de assinatura (PNG/JPG)", type=["png", "jpg", "jpeg"], key=f"up_edit_{instrutor_id}")
            
        novo_status = st.checkbox("Instrutor Ativo (is_active)", value=ativo_atual)
        
        salvar = st.form_submit_button("💾 Salvar Alterações", type="primary", use_container_width=True)
        
        if salvar:
            if not novo_nome.strip() or not novo_cpf.strip():
                st.warning("⚠️ Nome e CPF são campos obrigatórios.")
            else:
                try:
                    caminho_assinatura_final = assinatura_atual
                    
                    # Se um novo arquivo foi enviado, salva na pasta local
                    if arquivo_assinatura is not None:
                        nome_arquivo = f"assinatura_{novo_cpf}_{arquivo_assinatura.name}"
                        caminho_completo = os.path.join(PASTA_ASSINATURAS, nome_arquivo)
                        
                        with open(caminho_completo, "wb") as f:
                            f.write(arquivo_assinatura.getbuffer())
                        
                        caminho_assinatura_final = caminho_completo

                    payload = {
                        "name": novo_nome.strip(),
                        "cpf": novo_cpf.strip(),
                        "email": novo_email.strip() if novo_email else None,
                        "phone": novo_phone.strip() if novo_phone else None,
                        "cbo": novo_cbo.strip() if novo_cbo else None,
                        "assinatura": caminho_assinatura_final,
                        "is_active": novo_status
                    }
                    supabase.table("instrutores").update(payload).eq("id", instrutor_id).execute()
                    st.success("✅ Instrutor atualizado com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Erro ao atualizar instrutor: {e}")

# ==========================================
# ABA 1: LISTAGEM DE INSTRUTORES (EM CARDS)
# ==========================================
with tab_listar:
    st.subheader("Equipe de Instrutores")
    
    try:
        response = supabase.table("instrutores").select("*").order("name").execute()
        
        if response and isinstance(response.data, list) and len(response.data) > 0:
            for i in response.data:
                iid = i.get("id")
                nome = i.get("name", "Sem Nome")
                cpf = i.get("cpf", "")
                email = i.get("email", "")
                phone = i.get("phone", "")
                cbo = i.get("cbo", "")
                assinatura = i.get("assinatura", "")
                is_active = i.get("is_active", True)
                
                status_display = "🟢 **Ativo**" if is_active else "🔴 **Inativo**"
                cpf_fmt = f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}" if len(cpf) == 11 else cpf
                
                # --- CARD EM LINHA COMPACTO ---
                with st.container(border=True):
                    col_info, col_acoes = st.columns([5, 1])
                    
                    with col_info:
                        st.markdown(f"**{nome}** — Status: {status_display}")
                        
                        detalhes = []
                        if cpf: detalhes.append(f"**CPF:** {cpf_fmt}")
                        if cbo: detalhes.append(f"**CBO:** {cbo}")
                        if phone: detalhes.append(f"**Tel:** {phone}")
                        if email: detalhes.append(f"**E-mail:** {email}")
                        
                        if detalhes:
                            st.caption(" | ".join(detalhes))
                            
                        if assinatura:
                            st.caption(f"✍️ **Assinatura:** `{assinatura}`")
                        else:
                            st.caption(f"⚠️ *Sem assinatura cadastrada*")
                        
                    with col_acoes:
                        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                        if st.button("✏️", key=f"edit_instr_{iid}", help="Editar informações do instrutor", use_container_width=True):
                            modal_editar_instrutor(iid, nome, cpf, email, phone, cbo, assinatura, is_active)
        else:
            st.info("ℹ️ Nenhum instrutor cadastrado no momento.")
            
    except Exception as e:
        st.error(f"Erro ao carregar instrutores: {e}")

# ==========================================
# ABA 2: CADASTRO DE NOVO INSTRUTOR
# ==========================================
with tab_cadastrar:
    st.subheader("Cadastrar Novo Instrutor")
    
    with st.form("form_novo_instrutor", clear_on_submit=True):
        nome_instrutor = st.text_input("Nome Completo (name)*")
        
        col1, col2 = st.columns(2)
        with col1:
            cpf_instrutor = st.text_input("CPF (11 dígitos)*", max_chars=11)
            phone_instrutor = st.text_input("Telefone (phone)", max_chars=11)
            cbo_instrutor = st.text_input("CBO")
        with col2:
            email_instrutor = st.text_input("E-mail")
            
        st.markdown("---")
        st.write("✍️ **Assinatura do Instrutor**")
        arquivo_assinatura_novo = st.file_uploader("Enviar imagem de assinatura (PNG/JPG)", type=["png", "jpg", "jpeg"], key="up_novo_instr")
            
        status_instrutor = st.checkbox("Tornar instrutor ativo imediatamente (is_active)", value=True)
        
        submit_btn = st.form_submit_button("Criar Instrutor", type="primary")
        
        if submit_btn:
            if not nome_instrutor.strip() or not cpf_instrutor.strip():
                st.warning("⚠️ Nome e CPF são campos obrigatórios.")
            else:
                try:
                    caminho_assinatura_salva = None
                    
                    if arquivo_assinatura_novo is not None:
                        nome_arquivo = f"assinatura_{cpf_instrutor.strip()}_{arquivo_assinatura_novo.name}"
                        caminho_completo = os.path.join(PASTA_ASSINATURAS, nome_arquivo)
                        
                        with open(caminho_completo, "wb") as f:
                            f.write(arquivo_assinatura_novo.getbuffer())
                            
                        caminho_assinatura_salva = caminho_completo

                    novo_payload = {
                        "name": nome_instrutor.strip(),
                        "cpf": cpf_instrutor.strip(),
                        "email": email_instrutor.strip() if email_instrutor else None,
                        "phone": phone_instrutor.strip() if phone_instrutor else None,
                        "cbo": cbo_instrutor.strip() if cbo_instrutor else None,
                        "assinatura": caminho_assinatura_salva,
                        "is_active": status_instrutor
                    }
                    supabase.table("instrutores").insert(novo_payload).execute()
                    st.success(f"✅ Instrutor '{nome_instrutor}' criado com sucesso!")
                    st.balloons()
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Erro ao criar instrutor: {e}")