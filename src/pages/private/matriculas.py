import streamlit as st
import pandas as pd
from src.config.database import supabase

st.title("📋 Alunos Matriculados por Turma")
st.markdown("Consulte os alunos que realizaram o check-in através do sistema e gerencie a turma.")

# 1. Busca todas as turmas cadastradas para o selectbox de forma segura
turmas_dict = {}
try:
    turmas_res = supabase.table("turmas").select("id, titulo, data_treinamento").order("data_treinamento", desc=True).execute()
    if turmas_res and isinstance(turmas_res.data, list):
        for t in turmas_res.data:
            if isinstance(t, dict):
                titulo = str(t.get("titulo", "Sem Título"))
                data = str(t.get("data_treinamento", ""))
                tid = t.get("id")
                if tid:
                    turmas_dict[f"{titulo} ({data})"] = tid
except Exception as e:
    st.error(f"Erro ao carregar turmas: {e}")

if not turmas_dict:
    st.warning("⚠️ Nenhuma turma cadastrada no sistema.")
    st.stop()

# Seleção da Turma
turma_selecionada = st.selectbox("Selecione a Turma para ver os Alunos:", options=list(turmas_dict.keys()))
turma_id_atual = turmas_dict[turma_selecionada]

st.divider()

# 2. Busca as matrículas vinculadas a esta turma de forma segura
try:
    response = supabase.table("matriculas").select(
        "id, doc_emitida, created_at, alunos(name, cpf, rg, email, phone), clients(name, cnpj)"
    ).eq("turma_id", turma_id_atual).execute()
    
    if response and isinstance(response.data, list) and len(response.data) > 0:
        dados_tabela = []
        for m in response.data:
            if isinstance(m, dict):
                aluno = m.get("alunos")
                aluno_dict = aluno if isinstance(aluno, dict) else {}
                
                client = m.get("clients")
                client_dict = client if isinstance(client, dict) else {}
                
                created_at_str = str(m.get("created_at", ""))
                data_formatada = created_at_str[:10] if len(created_at_str) >= 10 else ""
                
                dados_tabela.append({
                    "ID Matrícula": m.get("id"),
                    "Nome do Aluno": aluno_dict.get("name", "Não informado"),
                    "CPF": aluno_dict.get("cpf", "Não informado"),
                    "RG": aluno_dict.get("rg", "-"),
                    "Empresa": client_dict.get("name", "Não informada"),
                    "CNPJ": client_dict.get("cnpj", "-"),
                    "Documento Emitido?": "✅ Sim" if m.get("doc_emitida") else "❌ Não",
                    "Data Check-in": data_formatada
                })
            
        df_alunos = pd.DataFrame(dados_tabela)
        
        st.subheader(f"Total de Alunos na Turma: {len(df_alunos)}")
        
        st.dataframe(
            df_alunos,
            use_container_width=True,
            hide_index=True
        )
        
        st.markdown("---")
        if st.button("📥 Exportar Lista da Turma (Excel/CSV)", use_container_width=True):
            csv = df_alunos.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Baixar Arquivo CSV",
                data=csv,
                file_name=f"turma_alunos_{turma_id_atual}.csv",
                mime="text/csv",
            )
        
    else:
        st.info("ℹ️ Nenhum aluno realizou o check-in nesta turma até o momento.")

except Exception as e:
    st.error(f"Erro ao buscar matrículas da turma: {e}")