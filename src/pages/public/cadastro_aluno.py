import streamlit as st
from src.config.database import supabase

st.title("📱 Cadastro de Presença - Centro de Treinamento")
st.write("Selecione a turma em que você está participando hoje e preencha seus dados.")

turmas_dict = {}
empresas_dict = {}

try:
    # 1. Busca turmas disponíveis
    turmas_res = supabase.table("turmas").select("id, titulo, data_treinamento").order("data_treinamento", desc=True).limit(20).execute()
    
    # Valida explicitamente se os dados retornados são uma lista
    if turmas_res and isinstance(turmas_res.data, list):
        for t in turmas_res.data:
            # Acessando de forma segura convertendo explicitamente se necessário
            titulo = str(t.get("titulo", "Sem Título")) if isinstance(t, dict) else "Sem Título"
            data = str(t.get("data_treinamento", "")) if isinstance(t, dict) else ""
            tid = t.get("id") if isinstance(t, dict) else None
            if tid:
                turmas_dict[f"{titulo} ({data})"] = tid

    # 2. Busca empresas (clients) cadastradas
    clients_res = supabase.table("clients").select("id, name, cnpj").execute()
    
    if clients_res and isinstance(clients_res.data, list):
        for c in clients_res.data:
            cname = str(c.get("name", "Empresa Sem Nome")) if isinstance(c, dict) else "Empresa Sem Nome"
            ccnjp = str(c.get("cnpj", "")) if isinstance(c, dict) else ""
            cid = c.get("id") if isinstance(c, dict) else None
            if cid:
                empresas_dict[f"{cname} (CNPJ: {ccnjp})"] = cid

except Exception as e:
    st.error(f"Erro de conexão ao carregar dados do banco: {e}")

# Validações caso as tabelas estejam vazias
if not turmas_dict:
    st.warning("⚠️ Nenhuma turma cadastrada no sistema. Por favor, cadastre uma turma no painel administrativo.")
    st.stop()

if not empresas_dict:
    st.warning("⚠️ Nenhuma empresa cadastrada no sistema. Por favor, cadastre os clientes/empresas.")
    st.stop()

# (O restante do formulário com st.form continua exatamente igual ao anterior...)