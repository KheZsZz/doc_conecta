import os
import streamlit as st
import pandas as pd
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
import zipfile
import io
import numpy as np
from datetime import datetime
from src.config.database import supabase # Importa a conexão com o Supabase

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Emissor de Atestados de Brigada", 
    page_icon="🔥", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- LINKS PÚBLICOS PADRÃO (FALLBACK) ---
URL_LOGO_CONECTA = "https://vesgrrejcehseygchigh.supabase.co/storage/v1/object/public/logos/logo_conecta.png"
URL_ASSINATURA_PADRAO = "https://vesgrrejcehseygchigh.supabase.co/storage/v1/object/public/assinaturas/assinatura_1787506509.png"

# --- FUNÇÕES AUXILIARES ---
@st.cache_data
def gerar_planilha_exemplo():
    """Gera um DataFrame de exemplo alinhado com as colunas suportadas"""
    df_exemplo = pd.DataFrame({
        "FUNDAÇÃO": ["EMPRESA EXEMPLO LTDA", "EMPRESA EXEMPLO LTDA"],
        "CNPJ": ["12.345.678/0001-90", "12.345.678/0001-90"],
        "ENDEREÇO": ["Rua Fictícia, 123 - Centro, São Paulo/SP", "Rua Fictícia, 123 - Centro, São Paulo/SP"],
        "NOME": ["JOÃO DA SILVA", "MARIA SOUZA"],
        "RG": ["11.222.333-4", "55.666.777-8"],
        "CPF": ["111.222.333-44", "999.888.777-66"],
        "NASC": ["15/05/1990", "22/10/1985"],
        "CARGA HORARIA": ["8h", "8h"],
        "CONCLUSÃO": ["31/07/2026", "31/07/2026"],
        "OBS": ["tabela B.2 da IT 17", "tabela B.2 da IT 17"]
    })

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_exemplo.to_excel(writer, sheet_name="LOTE", index=False)
    return output.getvalue()

def formatar_data(val):
    if pd.isna(val) or not str(val).strip(): return ""
    try:
        return pd.to_datetime(val).strftime('%d/%m/%Y')
    except:
        return str(val).split()[0]

def formatar_data_por_extenso(val):
    if pd.isna(val) or not str(val).strip(): return ""
    meses = {1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho", 
             7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"}
    try:
        dt = pd.to_datetime(val)
        dia = f"{dt.day:02d}".lstrip('0') if dt.day < 10 else str(dt.day)
        return f"{dia} de {meses.get(dt.month, '')} de {dt.year}"
    except:
        return str(val)

def valor_esta_vazio(val):
    if pd.isna(val): return True
    val_str = str(val).strip().upper()
    return val_str == "" or val_str in ["NAN", "NONE", "#N/D", "N/D", "NULL"]

def validar_template_html():
    caminho_template = os.path.join("src", "templates", "template_atestado_corrigido.html")
    if not os.path.exists(caminho_template):
        st.error(f"❌ Arquivo de template HTML não encontrado em: `{caminho_template}`")
        return False
    return True

# --- BUSCAR CENTROS DE TREINAMENTO (CTs) DO SUPABASE ---
cts_dict = {}
try:
    res_cts = supabase.table("cts").select("*").execute()
    if res_cts and res_cts.data:
        for ct in res_cts.data:
            # Identifica pelo nome ou full_name cadastrado na tabela cts
            nome_ct = ct.get("name") or ct.get("full_name") or "Centro de Treinamento"
            cts_dict[nome_ct] = ct
except Exception as e:
    st.error(f"Erro ao carregar os Centros de Treinamento (CTs) do Supabase: {e}")

# --- BARRA LATERAL (SIDEBAR) ---
with st.sidebar:
    st.header("⚙️ Configurações")
    
    # Seleção do CT direto da tabela 'cts' do Supabase
    ct_selecionado_dados = {}
    if cts_dict:
        ct_nome_escolhido = st.selectbox("🏢 Centro de Treinamento (CT)", options=list(cts_dict.keys()))
        ct_selecionado_dados = cts_dict[ct_nome_escolhido]
    else:
        st.warning("⚠️ Nenhum CT encontrado na tabela 'cts' do Supabase.")

    # Exibe a logo do CT selecionado na barra lateral se houver URL cadastrada
    url_logo_ct = ct_selecionado_dados.get("logo_url")
    if url_logo_ct:
        st.image(url_logo_ct, use_container_width=True)

    st.markdown("---")
    st.markdown("Preencha os dados que sairão no rodapé e corpo do atestado.")
    
    with st.expander("👨‍🏫 Dados do Instrutor", expanded=True):
        nome_instrutor = st.text_input("Nome Completo", value="POLYANE OLIVEIRA CIVIRINO")
        doc_instrutor = st.text_input("Documento / CBO", value="351605")
        
        usar_assinatura_personalizada = st.checkbox("Enviar assinatura personalizada?", value=False)
        assinatura_url_final = URL_ASSINATURA_PADRAO
        
        if usar_assinatura_personalizada:
            assinatura_file = st.file_uploader("Arquivo de Assinatura", type=["png", "jpg", "jpeg"])
            if assinatura_file:
                import base64
                encoded = base64.b64encode(assinatura_file.getvalue()).decode('utf-8')
                mime = assinatura_file.type
                assinatura_url_final = f"data:{mime};base64,{encoded}"

    with st.expander("👁️ Exibição de Colunas na Tabela", expanded=True):
        mostrar_rg = st.checkbox("Mostrar coluna RG", value=True)
        mostrar_nasc = st.checkbox("Mostrar coluna Data Nasc.", value=True)
        mostrar_data_conclusao = st.checkbox("Mostrar coluna Data Conclusão", value=True)

    with st.expander("📅 Local e Data de Emissão", expanded=True):
        cidade_input = st.text_input("Cidade", value="Diadema")
        data_input = st.date_input("Data", value=datetime.today())

    st.markdown("---")
    st.caption("Desenvolvido para agilizar a emissão de atestados de brigada.")

# --- ÁREA PRINCIPAL ---
st.title("🔥 Emissor de Atestados de Brigada")
st.markdown("Gere atestados em PDF de forma automatizada via planilha utilizando os dados do **CT** selecionado.")

col_step1, col_step2, col_step3 = st.columns(3)
with col_step1:
    st.info("👈 **Passo 1:** Selecione o CT, configure as colunas e o instrutor.")
with col_step2:
    st.info("📄 **Passo 2:** Baixe o exemplo e faça o upload da planilha com a aba 'LOTE'.")
with col_step3:
    st.info("🚀 **Passo 3:** Clique em gerar e baixe o arquivo ZIP com todos os PDFs.")

st.markdown("---")
st.subheader("📂 Upload de Dados")

st.download_button(
    label="📄 Baixar Planilha de Exemplo",
    data=gerar_planilha_exemplo(),
    file_name="modelo_dados_brigada.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    help="Baixe este modelo para ver como as colunas devem estar formatadas."
)

uploaded_file = st.file_uploader(
    "Arraste ou selecione a planilha Excel (`.xlsx`)", 
    type=["xlsx", "xls"], 
    label_visibility="collapsed"
)

# --- PROCESSAMENTO DOS DADOS ---
if uploaded_file is not None:
    st.success(f"✅ Planilha **{uploaded_file.name}** carregada com sucesso!")

    col_btn, _ = st.columns([1, 2])
    with col_btn:
        gerar_btn = st.button("🚀 Processar e Gerar Atestados", type="primary", use_container_width=True)

    if gerar_btn:
        if not ct_selecionado_dados:
            st.error("⚠️ Selecione um Centro de Treinamento válido na barra lateral.")
            st.stop()

        with st.spinner("🔄 Lendo dados, validando e gerando os PDFs..."):
            if not validar_template_html():
                st.stop()

            # Formatação da data final
            data_formatada_extenso = formatar_data_por_extenso(data_input)
            cidade_data_final = f"{cidade_input.strip()}, {data_formatada_extenso}."

            # Leitura do DataFrame
            df = pd.read_excel(uploaded_file, sheet_name="LOTE")
            df.columns = df.columns.str.strip()
            df.replace(["#N/D", "#n/d", "N/D", "n/d"], np.nan, inplace=True)

            grupos = list(df.groupby(['FUNDAÇÃO', 'CNPJ'], dropna=False))

            env = Environment(loader=FileSystemLoader(os.path.join("src", "templates")))
            template = env.get_template('template_atestado_corrigido.html')

            zip_buffer = io.BytesIO()
            atestados_gerados = 0
            dados_ignorados = []

            # Geração dos arquivos
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for (empresa_nome, cnpj), grupo in grupos:
                    primeira_linha = grupo.iloc[0]
                    endereco = primeira_linha.get('ENDEREÇO', '')
                    motivos_falha = []

                    # Validações essenciais
                    if valor_esta_vazio(cnpj): motivos_falha.append("CNPJ ausente ou #N/D")
                    if valor_esta_vazio(endereco): motivos_falha.append("Endereço ausente ou #N/D")
                    if valor_esta_vazio(empresa_nome): motivos_falha.append("Nome ausente")

                    if motivos_falha:
                        dados_ignorados.append({
                            "Empresa": str(empresa_nome),
                            "CNPJ": str(cnpj) if not pd.isna(cnpj) else "Vazio",
                            "Inconsistência": " | ".join(motivos_falha),
                            "Alunos Afetados": len(grupo)
                        })
                        continue

                    lista_alunos = []
                    for _, row in grupo.iterrows():
                        lista_alunos.append({
                            "nome": str(row.get('NOME', '')).strip().upper(),
                            "rg": str(row.get('RG', '')).strip(),
                            "cpf": str(row.get('CPF', '')).strip(),
                            "data_nasc": formatar_data(row.get('NASC', '')),
                            "data_matricula": formatar_data(row.get('CONCLUSÃO', '')),
                            "horas": str(row.get('CARGA HORARIA', '')).strip()
                        })

                    # Dicionário do Jinja mapeando os dados do CT vindos diretamente da tabela 'cts'
                    contexto = {
                        "LOGO_CT": ct_selecionado_dados.get("logo_url", ""),
                        "LOGO_CONECTA": URL_LOGO_CONECTA,
                        "ASSINATURA_IMG": assinatura_url_final,
                        "EMPRESA": str(empresa_nome).strip(),
                        "ENDERECO": str(endereco).strip(),
                        "CNPJ": str(cnpj).strip(),
                        "NORMA": primeira_linha.get('OBS', 'tabela B.2 da IT 17'),
                        "CIDADE_DATA": cidade_data_final,
                        "NOME_INSTRUTOR": nome_instrutor.strip(),
                        "DOC_INSTRUTOR": doc_instrutor.strip(),
                        # Dados dinâmicos do CT vindos da tabela 'cts' do Supabase
                        "CT_NOME": ct_selecionado_dados.get("full_name") or ct_selecionado_dados.get("name", ""),
                        "CT_CNPJ": ct_selecionado_dados.get("cnpj", ""),
                        "CT_ENDERECO": ct_selecionado_dados.get("full_address", ""),
                        "CT_TELEFONE": ct_selecionado_dados.get("phone", ""),
                        # Flags condicionais das colunas da tabela
                        "mostrar_coluna_rg": mostrar_rg,
                        "mostrar_coluna_nasc": mostrar_nasc,
                        "mostrar_coluna_data": mostrar_data_conclusao,
                        "alunos": lista_alunos
                    }

                    # Criação do PDF
                    html_renderizado = template.render(contexto)
                    nome_sanitizado = "".join(c for c in str(empresa_nome) if c.isalnum() or c in (' ', '_', '-')).strip()
                    pdf_bytes = HTML(string=html_renderizado).write_pdf()
                    zip_file.writestr(f"Atestado_{nome_sanitizado[:50]}.pdf", pdf_bytes)
                    atestados_gerados += 1

            zip_buffer.seek(0)

            # --- EXIBIÇÃO DE RESULTADOS EM ABAS ---
            st.markdown("---")
            st.subheader("📊 Resultados do Processamento")
            
            metrica1, metrica2 = st.columns(2)
            metrica1.metric(label="Atestados Gerados (Válidos)", value=atestados_gerados)
            metrica2.metric(label="Registros Inconsistentes (Ignorados)", value=len(dados_ignorados))

            aba_download, aba_erros = st.tabs(["📥 Área de Download", "⚠️ Relatório de Inconsistências"])
            
            with aba_download:
                if atestados_gerados > 0:
                    st.success("Tudo pronto! Seus atestados foram gerados com sucesso utilizando os dados do CT selecionado.")
                    st.download_button(
                        label="📦 Baixar Atestados (.zip)",
                        data=zip_buffer,
                        file_name=f"atestados_brigada_{datetime.today().strftime('%d%m%Y')}.zip",
                        mime="application/zip",
                        use_container_width=True
                    )
                else:
                    st.warning("Nenhum atestado pôde ser gerado. Verifique os erros na aba de inconsistências.")

            with aba_erros:
                if dados_ignorados:
                    st.warning("Algumas linhas da planilha foram puladas por conterem dados essenciais ausentes ou inválidos.")
                    st.dataframe(pd.DataFrame(dados_ignorados), use_container_width=True)
                else:
                    st.info("✨ Todos os registros estavam corretos e foram processados sem problemas!")