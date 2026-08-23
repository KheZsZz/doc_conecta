import streamlit as st
from src.config.database import supabase
from datetime import datetime

st.title("📝 Criar Nova Conta")
st.write("Preencha os dados abaixo para se cadastrar no sistema.")

with st.form("form_cadastro_usuario"):
    # Novos campos solicitados
    nome = st.text_input("Nome Completo*")
    phone = st.text_input("Telefone")
    email = st.text_input("E-mail*")
    
    st.markdown("---")
    senha = st.text_input("Senha*", type="password", help="A senha deve ter no mínimo 6 caracteres.")
    confirmar_senha = st.text_input("Confirmar Senha*", type="password")
    
    submit = st.form_submit_button("Cadastrar", type="primary", use_container_width=True)
    
    if submit:
        # 1. Validações Locais
        if not email or not senha or not nome:
            st.warning("⚠️ Por favor, preencha todos os campos obrigatórios (*).")
        elif senha != confirmar_senha:
            st.warning("⚠️ As senhas não coincidem.")
        elif len(senha) < 6:
            st.warning("⚠️ A senha deve ter no mínimo 6 caracteres.")
        else:
            try:
                # 2. Cria o usuário no sistema de Autenticação do Supabase
                response = supabase.auth.sign_up({
                    "email": email, 
                    "password": senha
                })
                
                # Verifica se o usuário foi criado com sucesso
                if response.user:
                    # 3. Salva os dados complementares na tabela "usuarios"
                    dados_usuario = {
                        "id": response.user.id, # Usa o mesmo ID gerado pela autenticação
                        "nome": nome,
                        "email": email,
                        "phone": phone,
                        "is_active": True,
                        "updated_at": datetime.now().isoformat()
                    }
                    
                    # Insere no banco
                    supabase.table("usuarios").insert(dados_usuario).execute()
                    
                    st.success("✅ Conta criada com sucesso! Você já pode ir para a tela de Login.")
                else:
                    st.error("Erro desconhecido ao criar usuário. Tente novamente.")
                    
            except Exception as e:
                st.error(f"❌ Erro ao criar conta: {e}")