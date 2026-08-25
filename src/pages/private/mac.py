import os
import base64
import streamlit as st
import pandas as pd
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
import zipfile
import io
import numpy as np
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Emissor de Atestados de Brigada", 
    page_icon="🔥", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- FUNÇÕES AUXILIARES ---
@st.cache_data
def gerar_planilha_exemplo():
    """Gera um DataFrame de exemplo e retorna os bytes do arquivo Excel (.xlsx)"""
    df_exemplo = pd.DataFrame({
        "FUNDAÇÃO": ["EMPRESA EXEMPLO LTDA", "EMPRESA EXEMPLO LTDA"],
        "CNPJ": ["12.345.678/0001-90", "12.345.678/0001-90"],
        "ENDEREÇO": ["Rua Fictícia, 123 - Centro, São Paulo/SP", "Rua Fictícia, 123 - Centro, São Paulo/SP"],
        "NOME": ["JOÃO DA SILVA", "MARIA SOUZA"],
        "RG": ["11.222.333-4", "55.666.777-8"],
        "CPF": ["111.222.333-44", "999.888.777-66"],
        "NASC": ["15/05/1990", "22/10/1985"],
        "CARGA HORARIA": ["8h", "8h"],
        "CONCLUSÃO": ["Diadema, 31 de Julho de 2026", "Diadema, 31 de Julho de 2026"],
        "OBS": ["tabela B.2 da IT 17", "tabela B.2 da IT 17"]
    })

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_exemplo.to_excel(writer, sheet_name="LOTE", index=False)
    return output.getvalue()

def imagem_para_base64(caminho_imagem: str) -> str:
    """Lê imagem do disco e converte para base64"""
    if not os.path.exists(caminho_imagem):
        st.sidebar.error(f"⚠️ Imagem de sistema não encontrada: {caminho_imagem}")
        return ""
    try:
        ext = caminho_imagem.split('.')[-1].lower()
        mime_type = "image/png" if ext == "png" else "image/jpeg"
        with open(caminho_imagem, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        return f"data:{mime_type};base64,{encoded_string}"
    except Exception as e:
        st.sidebar.error(f"❌ Erro ao carregar {caminho_imagem}: {e}")
        return ""

def bytes_para_base64(file_bytes, mime_type: str) -> str:
    """Converte arquivo upado no Streamlit para base64"""
    try:
        encoded_string = base64.b64encode(file_bytes).decode('utf-8')
        return f"data:{mime_type};base64,{encoded_string}"
    except Exception as e:
        st.error(f"❌ Erro ao converter assinatura: {e}")
        return ""

def formatar_data(val):
    if pd.isna(val): return ""
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

def validar_arquivos_necessarios():
    arquivos = [os.path.join("assets", "logo_treinnar.png"), os.path.join("assets", "logo_conecta.png"), "template_atestado_corrigido.html"]
    faltando = [f for f in arquivos if not os.path.exists(f)]
    if faltando:
        st.error(f"❌ Arquivos de sistema faltando: {', '.join(faltando)}")
        return False
    return True

# --- BARRA LATERAL (SIDEBAR) ---
with st.sidebar:
    # Mostra a logo principal de forma correta sem gerar avisos de Deprecation
    logo_path = os.path.join("assets", "logo_treinnar.png")
    if os.path.exists(logo_path):
        st.image(logo_path, use_container_width=True)
        
    st.header("⚙️ Configurações")
    st.markdown("Preencha os dados que sairão no rodapé do atestado.")
    
    with st.expander("👨‍🏫 Dados do Instrutor", expanded=True):
        nome_instrutor = st.text_input("Nome Completo", value="POLYANE OLIVEIRA CIVIRINO")
        doc_instrutor = st.text_input("Documento / CBO", value="320.827.408-46 | CBO n° 351605")
        assinatura_file = st.file_uploader("Foto da Assinatura", type=["png", "jpg", "jpeg"], help="Envie a imagem da assinatura sem fundo (PNG) de preferência.")

    with st.expander("📅 Local e Data de Emissão", expanded=True):
        cidade_input = st.text_input("Cidade", value="Diadema")
        data_input = st.date_input("Data", value=datetime.today())

    st.markdown("---")
    st.caption("Desenvolvido para agilizar a emissão de atestados de brigada.")

# --- ÁREA PRINCIPAL ---
st.title("🔥 Emissor de Atestados de Brigada")
st.markdown("Gere atestados em PDF de forma automatizada. **Siga os passos abaixo:**")

# Orientação visual em colunas
col_step1, col_step2, col_step3 = st.columns(3)
with col_step1:
    st.info("👈 **Passo 1:** Configure os dados do instrutor e data na barra lateral.")
with col_step2:
    st.info("📄 **Passo 2:** Baixe o exemplo e faça o upload da planilha com a aba 'LOTE'.")
with col_step3:
    st.info("🚀 **Passo 3:** Clique em gerar e baixe o arquivo ZIP com todos os PDFs.")

st.markdown("---")
st.subheader("📂 Upload de Dados")

# Botão para baixar a planilha de exemplo
st.download_button(
    label="📄 Baixar Planilha de Exemplo",
    data=gerar_planilha_exemplo(),
    file_name="modelo_dados_brigada.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    help="Baixe este modelo para ver como as colunas devem estar formatadas."
)

# Componente de upload
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
        if not assinatura_file:
            st.error("⚠️ **Ação necessária:** Faça o upload da imagem da assinatura do instrutor na barra lateral antes de continuar.")
            st.stop()

        with st.spinner("🔄 Lendo dados, validando campos e montando os PDFs. Aguarde..."):
            if not validar_arquivos_necessarios():
                st.stop()

            # Conversão de imagens
            img_treinnar = imagem_para_base64(os.path.join("assets", "logo_treinnar.png"))
            img_conecta = imagem_para_base64(os.path.join("assets", "logo_conecta.png"))
            img_assinatura = bytes_para_base64(assinatura_file.getvalue(), assinatura_file.type)

            # Formatação da data final
            data_formatada_extenso = formatar_data_por_extenso(data_input)
            cidade_data_final = f"{cidade_input.strip()}, {data_formatada_extenso}."

            # Leitura do DataFrame
            df = pd.read_excel(uploaded_file, sheet_name="LOTE")
            df.columns = df.columns.str.strip()
            df.replace(["#N/D", "#n/d", "N/D", "n/d"], np.nan, inplace=True)

            grupos = list(df.groupby(['FUNDAÇÃO', 'CNPJ'], dropna=False))

            env = Environment(loader=FileSystemLoader('.'))
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
                            "horas": str(row.get('CARGA HORARIA', '')).strip()
                        })

                    # Dicionário do Jinja
                    contexto = {
                        "LOGO_TREINNAR": img_treinnar,
                        "ASSINATURA_IMG": img_assinatura,
                        "LOGO_CONECTA": img_conecta,
                        "EMPRESA": str(empresa_nome).strip(),
                        "ENDERECO": str(endereco).strip(),
                        "CNPJ": str(cnpj).strip(),
                        "NORMA": primeira_linha.get('OBS', 'tabela B.2 da IT 17'),
                        "CIDADE_DATA": cidade_data_final,
                        "NOME_INSTRUTOR": nome_instrutor.strip(),
                        "DOC_INSTRUTOR": doc_instrutor.strip(),
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
            
            # Métricas
            metrica1, metrica2 = st.columns(2)
            metrica1.metric(label="Atestados Gerados (Válidos)", value=atestados_gerados)
            metrica2.metric(label="Registros Inconsistentes (Ignorados)", value=len(dados_ignorados))

            aba_download, aba_erros = st.tabs(["📥 Área de Download", "⚠️ Relatório de Inconsistências"])
            
            with aba_download:
                if atestados_gerados > 0:
                    st.success("Tudo pronto! Seus atestados foram gerados com sucesso.")
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