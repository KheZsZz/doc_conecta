import streamlit as st
from src.config.database import supabase

st.title("📚 Gestão de Cursos")
st.markdown("Cadastre e gerencie os treinamentos oferecidos pela sua empresa.")

tab_listar, tab_cadastrar = st.tabs(["📋 Cursos Cadastrados", "➕ Novo Curso"])

# ==========================================
# 1. MODAL / POPUP DE EDIÇÃO DO CURSO
# ==========================================
@st.dialog("✏️ Editar Curso", width="medium")
def modal_editar_curso(curso_id, nome_atual, sigla_atual, normativa_atual):
    with st.form(f"form_edit_curso_{curso_id}"):
        novo_nome = st.text_input("Nome do Curso*", value=nome_atual)
        
        col1, col2 = st.columns(2)
        with col1:
            nova_sigla = st.text_input("Sigla (Máx 5 caracteres)", value=sigla_atual if sigla_atual else "", max_chars=5)
        with col2:
            nova_normativa = st.text_input("Normativa (Ex: Conforme IT 17)", value=normativa_atual if normativa_atual else "")
        
        salvar = st.form_submit_button("💾 Salvar Alterações", type="primary", use_container_width=True)
        
        if salvar:
            if not novo_nome.strip():
                st.warning("⚠️ O nome do curso é obrigatório.")
            else:
                try:
                    payload = {
                        "name": novo_nome.strip(),
                        "sigla": nova_sigla.strip().upper() if nova_sigla else None,
                        "normativa": nova_normativa.strip() if nova_normativa else None
                    }
                    supabase.table("cursos").update(payload).eq("id", curso_id).execute()
                    st.success("✅ Curso atualizado com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Erro ao atualizar curso: {e}")

# ==========================================
# ABA 1: LISTAGEM DE CURSOS (EM CARDS)
# ==========================================
with tab_listar:
    st.subheader("Cursos e Treinamentos Disponíveis")
    
    try:
        response = supabase.table("cursos").select("*").order("name").execute()
        
        if response and isinstance(response.data, list) and len(response.data) > 0:
            for c in response.data:
                cid = c.get("id")
                nome = c.get("name", "Sem Nome")
                sigla = c.get("sigla", "")
                normativa = c.get("normativa", "")
                
                # Formata a sigla para exibir bonitinho ao lado do nome, se existir
                sigla_display = f" [{sigla}]" if sigla else ""
                
                # --- CARD EM LINHA COMPACTO ---
                with st.container(border=True):
                    col_info, col_acoes = st.columns([5, 1])
                    
                    with col_info:
                        st.markdown(f"**{nome}**{sigla_display}")
                        if normativa:
                            st.caption(f"📜 **Normativa:** {normativa}")
                        
                    with col_acoes:
                        st.markdown("<div style='height: 5px;'></div>", unsafe_allow_html=True)
                        # Botão centralizado no cantinho para edição
                        if st.button("✏️", key=f"edit_curso_{cid}", help="Editar informações deste curso", use_container_width=True):
                            modal_editar_curso(cid, nome, sigla, normativa)
        else:
            st.info("ℹ️ Nenhum curso cadastrado no momento.")
            
    except Exception as e:
        st.error(f"Erro ao carregar cursos: {e}")

# ==========================================
# ABA 2: CADASTRO DE NOVO CURSO
# ==========================================
with tab_cadastrar:
    st.subheader("Cadastrar Novo Curso")
    
    with st.form("form_novo_curso", clear_on_submit=True):
        nome_curso = st.text_input("Nome do Curso*")
        
        col1, col2 = st.columns(2)
        with col1:
            sigla_curso = st.text_input("Sigla (Máx 5 caracteres)", max_chars=5)
        with col2:
            normativa_curso = st.text_input("Normativa (Ex: Conforme IT 17)")
        
        submit_btn = st.form_submit_button("Criar Curso", type="primary")
        
        if submit_btn:
            if not nome_curso.strip():
                st.warning("⚠️ O nome do curso é obrigatório.")
            else:
                try:
                    novo_curso_payload = {
                        "name": nome_curso.strip(),
                        "sigla": sigla_curso.strip().upper() if sigla_curso else None,
                        "normativa": normativa_curso.strip() if normativa_curso else None
                    }
                    supabase.table("cursos").insert(novo_curso_payload).execute()
                    st.success(f"✅ Curso '{nome_curso}' criado com sucesso!")
                    st.balloons()
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Erro ao criar curso: {e}")