import streamlit as str_lit
import pandas as pd
import plotly.express as px
from datetime import date
from src.config.database import supabase
from src.utils.import_helper import processar_planilha_alunos

# Configuração da página
str_lit.title("📊 Painel Geral (Dashboard)")
str_lit.markdown("Acompanhe os principais indicadores do seu Centro de Treinamento e gerencie importações em tempo real.")

# ==========================================
# 1. BUSCA DE DADOS (EXTRAÇÃO)
# ==========================================
@str_lit.cache_data(ttl=60) # Cache de 60 segundos para deixar a Home super rápida
def carregar_dados_dashboard():
    res_turmas = supabase.table("turmas").select("id, titulo, data_treinamento, documento_emitido, modalidade, cursos(name)").execute()
    res_alunos = supabase.table("alunos").select("id").execute()
    res_clientes = supabase.table("clients").select("id").execute()
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
    delta_cor = "inverse" if turmas_pendentes > 0 else "normal"
    str_lit.metric("⚠️ Turmas Pendentes", f"{turmas_pendentes}", delta=f"{turmas_pendentes} sem docs", delta_color=delta_cor)

str_lit.markdown("---")

# ==========================================
# 3. SEÇÃO DE IMPORTAÇÃO RÁPIDA (UPLOAD DE ARQUIVOS NO DASHBOARD)
# ==========================================
with str_lit.expander("📥 Central de Importação Rápida de Alunos (Upload de Planilha)", expanded=False):
    str_lit.markdown("Envie a planilha de alunos (.xlsx ou .csv) e vincule diretamente a uma turma existente no banco de dados.")
    
    try:
        turmas_res = supabase.table("turmas").select("id, titulo, data_treinamento, carga_horaria").order("data_treinamento", desc=True).execute()
        turmas_dict_import = {}
        if turmas_res and turmas_res.data:
            for tm in turmas_res.data:
                turmas_dict_import[f"{tm.get('titulo')} (Data: {tm.get('data_treinamento')})"] = {
                    "id": tm.get("id"),
                    "data": tm.get("data_treinamento"),
                    "carga": tm.get("carga_horaria", "8 Horas")
                }

        clients_res = supabase.table("clients").select("id, name, cnpj").order("name").execute()
        empresas_opcoes_imp = {}
        if clients_res and clients_res.data:
            for cli in clients_res.data:
                empresas_opcoes_imp[f"{cli.get('name')} (CNPJ: {cli.get('cnpj')})"] = cli.get('id')

        if not turmas_dict_import:
            str_lit.info("ℹ️ Nenhuma turma cadastrada para receber importações. Crie uma turma na aba de Turmas primeiro.")
        else:
            col_imp1, col_imp2 = str_lit.columns(2)
            with col_imp1:
                turma_escolhida_label = str_lit.selectbox("Selecione a Turma de Destino*", options=list(turmas_dict_import.keys()), key="home_sel_turma")
            with col_imp2:
                empresa_escolhida_imp = str_lit.selectbox("Selecione a Empresa dos Alunos*", options=list(empresas_opcoes_imp.keys()) if empresas_opcoes_imp else ["Nenhuma empresa cadastrada"], key="home_sel_empresa")
            
            info_turma_sel = turmas_dict_import[turma_escolhida_label]
            tid_destino = info_turma_sel["id"]
            data_turma_sel = info_turma_sel["data"]
            carga_turma_sel = info_turma_sel["carga"]

            carga_horaria_padrao_imp = str_lit.text_input("Carga Horária Padrão para os Alunos", value=carga_turma_sel, key="home_input_carga")
            
            arquivo_excel_dash = str_lit.file_uploader(
                "Envie o arquivo de alunos (.xlsx ou .csv)",
                type=["xlsx", "csv"],
                key="file_uploader_home_dashboard"
            )
            
            if arquivo_excel_dash is not None:
                if str_lit.button("🚀 Processar e Importar Alunos para a Turma", type="primary", use_container_width=True, key="home_btn_importar"):
                    try:
                        with str_lit.spinner("Processando planilha e salvando matrículas..."):
                            alunos_tratados = processar_planilha_alunos(arquivo_excel_dash, data_turma_sel)
                            client_id_destino = empresas_opcoes_imp.get(empresa_escolhida_imp) if empresas_opcoes_imp else None
                            importados_count = 0
                            
                            for aluno in alunos_tratados:
                                nome_aluno = aluno["name"]
                                cpf_aluno = aluno["cpf"]
                                data_aluno_final = aluno["data_treinamento"]
                                data_nasc_aluno = aluno["data_nasc"]
                                
                                if not data_nasc_aluno or str(data_nasc_aluno).strip().lower() in ['nan', 'none', '']:
                                    data_nasc_aluno = None
                                
                                aluno_existente = supabase.table("alunos").select("id").eq("cpf", cpf_aluno).execute()
                                
                                if aluno_existente and aluno_existente.data:
                                    aluno_id = aluno_existente.data[0].get("id")
                                    supabase.table("alunos").update({"name": nome_aluno, "data_nasc": data_nasc_aluno}).eq("id", aluno_id).execute()
                                else:
                                    novo_aluno_payload = {"name": nome_aluno, "cpf": cpf_aluno, "data_nasc": data_nasc_aluno}
                                    res_novo_aluno = supabase.table("alunos").insert(novo_aluno_payload).execute()
                                    if res_novo_aluno and res_novo_aluno.data:
                                        aluno_id = res_novo_aluno.data[0].get("id")
                                    else:
                                        continue
                                
                                matricula_payload = {
                                    "turma_id": tid_destino,
                                    "aluno_id": aluno_id,
                                    "client_id": client_id_destino,
                                    "carga_horaria": carga_horaria_padrao_imp,
                                    "data_treinamento": data_aluno_final
                                }
                                supabase.table("matriculas").insert(matricula_payload).execute()
                                importados_count += 1
                                
                            str_lit.success(f"✅ {importados_count} alunos importados com sucesso! Os indicadores acima serão atualizados.")
                            str_lit.balloons()
                    except Exception as err:
                        str_lit.error(f"❌ Erro ao processar planilha: {err}")
    except Exception as e:
        str_lit.error(f"Erro ao carregar central de importação na home: {e}")

str_lit.markdown("---")

# ==========================================
# 4. GRÁFICOS INTERATIVOS
# ==========================================
if df_turmas.empty:
    str_lit.info("Nenhuma turma cadastrada ainda para gerar os gráficos.")
else:
    df_turmas["data_treinamento"] = pd.to_datetime(df_turmas["data_treinamento"], errors="coerce")
    df_turmas["mes_ano"] = df_turmas["data_treinamento"].dt.strftime("%m/%Y")
    df_turmas["nome_curso"] = df_turmas["cursos"].apply(lambda x: x["name"] if isinstance(x, dict) else "N/D")
    df_turmas["Status"] = df_turmas["documento_emitido"].map({True: "Emitido", False: "Pendente"})
    
    col_grafico1, col_grafico2 = str_lit.columns(2)
    
    with col_grafico1:
        turmas_por_mes = df_turmas.groupby("mes_ano").size().reset_index(name="Quantidade")
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
        status_counts = df_turmas["Status"].value_counts().reset_index()
        status_counts.columns = ["Status", "Quantidade"]
        
        fig_donut = px.pie(
            status_counts, 
            values="Quantidade", 
            names="Status", 
            hole=0.45, 
            title="📄 Status de Emissão (Turmas)",
            color="Status",
            color_discrete_map={"Emitido": "#2ca02c", "Pendente": "#d62728"}
        )
        str_lit.plotly_chart(fig_donut, use_container_width=True)

    str_lit.markdown("---")
    
    # ==========================================
    # 5. GRÁFICO INFERIOR & TABELA DE ALERTAS
    # ==========================================
    col_grafico3, col_tabela = str_lit.columns([1, 1])
    
    with col_grafico3:
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
            df_pendentes["Data"] = df_pendentes["data_treinamento"].dt.strftime("%d/%m/%Y")
            df_exibicao = df_pendentes[["Data", "titulo", "nome_curso"]].rename(columns={
                "titulo": "Título da Turma",
                "nome_curso": "Curso"
            }).sort_values("Data", ascending=False)
            
            str_lit.dataframe(df_exibicao, hide_index=True, use_container_width=True)
        else:
            str_lit.success("🎉 Nenhuma pendência! Todas as turmas já tiveram seus documentos emitidos.")