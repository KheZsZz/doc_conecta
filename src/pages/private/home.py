import streamlit as str_lit
import pandas as pd
import plotly.express as px
from datetime import date
from src.config.database import supabase

# Configuração da página (opcional se já estiver no app.py principal, mas bom garantir)
str_lit.title("📊 Painel Geral (Dashboard)")
str_lit.markdown("Acompanhe os principais indicadores do seu Centro de Treinamento em tempo real.")

# ==========================================
# 1. BUSCA DE DADOS (EXTRAÇÃO)
# ==========================================
@str_lit.cache_data(ttl=60) # Cache de 60 segundos para deixar a Home super rápida
def carregar_dados_dashboard():
    # Busca todas as turmas (trazendo o nome do curso junto)
    res_turmas = supabase.table("turmas").select("id, titulo, data_treinamento, documento_emitido, modalidade, cursos(name)").execute()
    
    # Busca alunos e clientes apenas para contagem total
    res_alunos = supabase.table("alunos").select("id").execute()
    res_clientes = supabase.table("clients").select("id").execute()
    
    # Busca matrículas para contagem de certificados
    res_matriculas = supabase.table("matriculas").select("id, doc_emitida").execute()
    
    return {
        "turmas": res_turmas.data if res_turmas else [],
        "alunos": res_alunos.data if res_alunos else [],
        "clientes": res_clientes.data if res_clientes else [],
        "matriculas": res_matriculas.data if res_matriculas else []
    }

with str_lit.spinner("Carregando indicadores..."):
    dados = carregar_dados_dashboard()

df_turmas = pd.DataFrame(dados["turmas"])
df_matriculas = pd.DataFrame(dados["matriculas"])

# ==========================================
# 2. CÁLCULO DE KPIs (MÉTRICAS NO TOPO)
# ==========================================
total_alunos = len(dados["alunos"])
total_empresas = len(dados["clientes"])

total_certificados = 0
if not df_matriculas.empty:
    total_certificados = len(df_matriculas[df_matriculas["doc_emitida"] == True])

turmas_pendentes = 0
if not df_turmas.empty:
    turmas_pendentes = len(df_turmas[df_turmas["documento_emitido"] == False])

# Renderização dos KPIs
col1, col2, col3, col4 = str_lit.columns(4)
with col1:
    str_lit.metric("👥 Total de Alunos", f"{total_alunos}")
with col2:
    str_lit.metric("🏢 Empresas Atendidas", f"{total_empresas}")
with col3:
    str_lit.metric("🎓 Certificados Emitidos", f"{total_certificados}")
with col4:
    # Destaca em vermelho se houver pendências
    delta_cor = "inverse" if turmas_pendentes > 0 else "normal"
    str_lit.metric("⚠️ Turmas Pendentes", f"{turmas_pendentes}", delta=f"{turmas_pendentes} sem docs", delta_color=delta_cor)

str_lit.markdown("---")

# ==========================================
# 3. GRÁFICOS INTERATIVOS
# ==========================================
if df_turmas.empty:
    str_lit.info("Nenhuma turma cadastrada ainda para gerar os gráficos.")
else:
    # Tratamento da tabela de turmas para os gráficos
    df_turmas["data_treinamento"] = pd.to_datetime(df_turmas["data_treinamento"], errors="coerce")
    df_turmas["mes_ano"] = df_turmas["data_treinamento"].dt.strftime("%m/%Y")
    df_turmas["nome_curso"] = df_turmas["cursos"].apply(lambda x: x["name"] if isinstance(x, dict) else "N/D")
    df_turmas["Status"] = df_turmas["documento_emitido"].map({True: "Emitido", False: "Pendente"})
    
    col_grafico1, col_grafico2 = str_lit.columns(2)
    
    with col_grafico1:
        # Gráfico 1: Evolução de Turmas por Mês
        turmas_por_mes = df_turmas.groupby("mes_ano").size().reset_index(name="Quantidade")
        
        # Ordena a data cronologicamente para o gráfico não ficar bagunçado
        turmas_por_mes["data_sort"] = pd.to_datetime(turmas_por_mes["mes_ano"], format="%m/%Y")
        turmas_por_mes = turmas_por_mes.sort_values("data_sort")
        
        fig_linha = px.bar(
            turmas_por_mes, 
            x="mes_ano", 
            y="Quantidade", 
            title="📅 Turmas Realizadas por Mês",
            text_auto=True,
            color_discrete_sequence=["#1f77b4"]
        )
        fig_linha.update_layout(xaxis_title="Mês/Ano", yaxis_title="Nº de Turmas")
        str_lit.plotly_chart(fig_linha, use_container_width=True)
        
    with col_grafico2:
        # Gráfico 2: Status das Documentações (Rosquinha / Donut)
        status_counts = df_turmas["Status"].value_counts().reset_index()
        status_counts.columns = ["Status", "Quantidade"]
        
        fig_donut = px.pie(
            status_counts, 
            values="Quantidade", 
            names="Status", 
            hole=0.45, 
            title="📄 Status de Emissão (Turmas)",
            color="Status",
            color_discrete_map={"Emitido": "#2ca02c", "Pendente": "#d62728"} # Verde e Vermelho
        )
        str_lit.plotly_chart(fig_donut, use_container_width=True)

    str_lit.markdown("---")
    
    # ==========================================
    # 4. GRÁFICO INFERIOR & TABELA DE ALERTAS
    # ==========================================
    col_grafico3, col_tabela = str_lit.columns([1, 1])
    
    with col_grafico3:
        # Gráfico 3: Turmas por Modalidade
        modalidade_counts = df_turmas["modalidade"].value_counts().reset_index()
        modalidade_counts.columns = ["Modalidade", "Quantidade"]
        
        fig_modalidade = px.bar(
            modalidade_counts, 
            y="Modalidade", 
            x="Quantidade", 
            orientation="h",
            title="📍 Distribuição por Modalidade",
            text_auto=True,
            color="Modalidade",
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        str_lit.plotly_chart(fig_modalidade, use_container_width=True)
        
    with col_tabela:
        str_lit.subheader("🚨 Turmas com Pendência de Documentos")
        
        df_pendentes = df_turmas[df_turmas["documento_emitido"] == False].copy()
        
        if not df_pendentes.empty:
            # Formata a data bonitinha para a tabela
            df_pendentes["Data"] = df_pendentes["data_treinamento"].dt.strftime("%d/%m/%Y")
            
            # Prepara o dataframe final só com as colunas úteis
            df_exibicao = df_pendentes[["Data", "titulo", "nome_curso"]].rename(columns={
                "titulo": "Título da Turma",
                "nome_curso": "Curso"
            }).sort_values("Data", ascending=False)
            
            str_lit.dataframe(df_exibicao, hide_index=True, use_container_width=True)
        else:
            str_lit.success("🎉 Nenhuma pendência! Todas as turmas já tiveram seus documentos emitidos.")