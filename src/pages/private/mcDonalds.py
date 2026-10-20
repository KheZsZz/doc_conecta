import base64
import io
import os
import re
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
import zipfile

from src.config.database import supabase

URL_LOGO_CONECTA = (
    "https://vesgrrejcehseygchigh.supabase.co/storage/v1/object/public/logos/logo_conecta.png"
)


@st.cache_data
def gerar_planilha_exemplo():
    df_exemplo = pd.DataFrame(
        {
            "UND": ["MCD_01", "MCD_02"],
            "FUNDAÇÃO": ["EMPRESA EXEMPLO LTDA", "EMPRESA EXEMPLO LTDA"],
            "CNPJ": ["12.345.678/0001-90", "12.345.678/0001-90"],
            "ENDEREÇO": [
                "Rua Fictícia, 123 - Centro, São Paulo/SP",
                "Rua Fictícia, 123 - Centro, São Paulo/SP",
            ],
            "NOME": ["JOÃO DA SILVA", "MARIA SOUZA"],
            "RG": ["11.222.333-4", "55.666.777-8"],
            "CPF": ["111.222.333-44", "999.888.777-66"],
            "DATA_NASC": ["15/05/1990", "22/10/1985"],
            "CARGA HORARIA": ["8h", "8h"],
            "DATA TÉRMINO": ["31/07/2026", "31/07/2026"],
            "OBS": ["tabela B.2 da IT 17", "tabela B.2 da IT 17"],
        }
    )
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_exemplo.to_excel(writer, sheet_name="LOTE", index=False)
    return output.getvalue()


def formatar_data(val):
    if pd.isna(val) or not str(val).strip():
        return ""
    try:
        return pd.to_datetime(val).strftime("%d/%m/%Y")
    except Exception:
        return str(val).split()[0]


def formatar_data_por_extenso(val):
    if pd.isna(val) or not str(val).strip():
        return ""
    meses = {
        1: "Janeiro",
        2: "Fevereiro",
        3: "Março",
        4: "Abril",
        5: "Maio",
        6: "Junho",
        7: "Julho",
        8: "Agosto",
        9: "Setembro",
        10: "Outubro",
        11: "Novembro",
        12: "Dezembro",
    }
    try:
        dt = pd.to_datetime(val)
        dia = f"{dt.day:02d}".lstrip("0") if dt.day < 10 else str(dt.day)
        return f"{dia} de {meses.get(dt.month, '')} de {dt.year}"
    except Exception:
        return str(val)


def valor_esta_vazio(val):
    if pd.isna(val):
        return True
    val_str = str(val).strip().upper()
    return val_str == "" or val_str in ["NAN", "NONE", "#N/D", "N/D", "NULL"]


def formatar_documento(val):
    if pd.isna(val) or not str(val).strip():
        return ""
    val_str = str(val).strip()
    if val_str.endswith(".0"):
        return val_str[:-2]
    return val_str


def formatar_cpf(val) -> str:
    digitos = re.sub(r"\D", "", str(val or ""))
    if not digitos:
        return ""
    if len(digitos) < 11:
        digitos = digitos.zfill(11)
    if len(digitos) != 11:
        return ""
    return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"


def validar_template_html():
    caminho_template = os.path.join("src", "templates", "template_atestado_corrigido.html")
    if not os.path.exists(caminho_template):
        st.error(f"❌ Arquivo de template HTML não encontrado em: `{caminho_template}`")
        return False
    return True


def _carregar_cts() -> dict:
    cts_dict = {}
    try:
        res_cts = supabase.table("cts").select("*").order("name").execute()
        if res_cts and res_cts.data:
            for ct in res_cts.data:
                nome_ct = ct.get("name") or ct.get("full_name") or "Centro de Treinamento"
                cts_dict[nome_ct] = ct
    except Exception as e:
        st.error(f"Erro ao carregar os CTs: {e}")
    return cts_dict


def _carregar_instrutores() -> list[dict]:
    try:
        res = (
            supabase.table("instrutores")
            .select("id, name, cpf, re, assinatura, is_active")
            .order("name")
            .execute()
        )
        lista = res.data if res and res.data else []
        # só ativos, se o campo existir
        ativos = [i for i in lista if i.get("is_active") is not False]
        return ativos or lista
    except Exception as e:
        st.error(f"Erro ao carregar instrutores: {e}")
        return []


# --- Dados cadastrados ---
cts_dict = _carregar_cts()
instrutores = _carregar_instrutores()

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Configurações")

    ct_selecionado_dados = {}
    if cts_dict:
        ct_nome_escolhido = st.selectbox(
            "🏢 Centro de Treinamento (CT)", options=list(cts_dict.keys())
        )
        ct_selecionado_dados = cts_dict[ct_nome_escolhido]
        # Logo e dados vêm do cadastro do CT — sem upload manual
        url_logo_ct = ct_selecionado_dados.get("logo_url")
        if url_logo_ct:
            st.image(url_logo_ct, use_container_width=True)
            st.caption("Logo do CT (cadastro)")
        else:
            st.warning("Este CT não tem logo cadastrada.")
    else:
        st.warning("⚠️ Nenhum CT encontrado. Cadastre em **CTS**.")

    st.markdown("---")

    with st.expander("👨‍🏫 Instrutor", expanded=True):
        if not instrutores:
            st.warning("Nenhum instrutor cadastrado. Cadastre em **Instrutores**.")
            nome_instrutor = ""
            doc_instrutor = ""
            re_instrutor = ""
            assinatura_url_final = ""
        else:
            opcoes = {
                f"{i.get('name', 'Sem nome')} · CPF {formatar_cpf(i.get('cpf')) or '—'}": i
                for i in instrutores
            }
            escolha = st.selectbox("Selecionar instrutor", options=list(opcoes.keys()))
            inst = opcoes[escolha]
            nome_instrutor = (inst.get("name") or "").strip()
            doc_instrutor = formatar_cpf(inst.get("cpf"))
            re_instrutor = (inst.get("re") or "").strip()
            assinatura_url_final = (inst.get("assinatura") or "").strip()

            st.caption(f"CPF: **{doc_instrutor or 'não cadastrado'}**")
            if re_instrutor:
                st.caption(f"RE: **{re_instrutor}**")
            if assinatura_url_final:
                st.image(assinatura_url_final, width=160, caption="Assinatura cadastrada")
            else:
                st.warning("Instrutor sem assinatura no cadastro.")

            # Override opcional só se precisar de assinatura avulsa nesta emissão
            usar_assinatura_personalizada = st.checkbox(
                "Usar assinatura avulsa só nesta emissão?", value=False
            )
            if usar_assinatura_personalizada:
                assinatura_file = st.file_uploader(
                    "Arquivo de Assinatura", type=["png", "jpg", "jpeg"]
                )
                if assinatura_file:
                    encoded = base64.b64encode(assinatura_file.getvalue()).decode("utf-8")
                    mime = assinatura_file.type
                    assinatura_url_final = f"data:{mime};base64,{encoded}"

    with st.expander("👁️ Exibição de Colunas na Tabela", expanded=True):
        mostrar_rg = st.checkbox("Mostrar coluna RG", value=True)
        mostrar_nasc = st.checkbox("Mostrar coluna Data Nasc.", value=True)
        mostrar_data_conclusao = st.checkbox(
            "Mostrar coluna Data Conclusão", value=False
        )
        mostrar_unidade = st.checkbox("Mostrar coluna Unidade (UND)", value=True)

    with st.expander("📅 Local e Data de Emissão", expanded=True):
        cidade_input = st.text_input("Cidade", value="Diadema")
        data_input = st.date_input("Data", value=datetime.today())

    st.markdown("---")
    st.caption("Instrutor e logo vêm do cadastro — sem digitar CBO/documento manual.")

# --- ÁREA PRINCIPAL ---
st.title("🔥 Emissor de Atestados de Brigada")
st.markdown(
    "Gere atestados em PDF via planilha. **CT, logo, instrutor e CPF** "
    "saem do cadastro do sistema."
)

st.download_button(
    "📥 Baixar planilha modelo",
    data=gerar_planilha_exemplo(),
    file_name="modelo_atestados_brigada.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

st.markdown("---")
st.subheader("📂 Upload de Dados")

uploaded_file = st.file_uploader(
    "Arraste ou selecione a planilha Excel (`.xlsx`)",
    type=["xlsx", "xls"],
    label_visibility="collapsed",
)

if uploaded_file is not None:
    st.success(f"✅ Planilha **{uploaded_file.name}** carregada com sucesso!")

    col_btn, _ = st.columns([1, 2])
    with col_btn:
        gerar_btn = st.button(
            "🚀 Processar e Gerar Atestados", type="primary", use_container_width=True
        )

    if gerar_btn:
        if not ct_selecionado_dados:
            st.error("⚠️ Selecione um Centro de Treinamento válido na barra lateral.")
            st.stop()
        if not nome_instrutor:
            st.error("⚠️ Selecione um instrutor cadastrado na barra lateral.")
            st.stop()
        if not doc_instrutor:
            st.error(
                "⚠️ O instrutor selecionado não tem CPF cadastrado. "
                "Atualize em **Instrutores**."
            )
            st.stop()

        with st.spinner("🔄 Lendo dados e gerando os PDFs..."):
            if not validar_template_html():
                st.stop()

            data_formatada_extenso = formatar_data_por_extenso(data_input)
            cidade_data_final = f"{cidade_input.strip()}, {data_formatada_extenso}."

            df = pd.read_excel(uploaded_file, sheet_name="LOTE")
            df.columns = df.columns.str.strip()
            df.replace(["#N/D", "#n/d", "N/D", "n/d"], np.nan, inplace=True)

            grupos = list(df.groupby(["FUNDAÇÃO", "CNPJ"], dropna=False))

            env = Environment(
                loader=FileSystemLoader(os.path.join("src", "templates"))
            )
            template = env.get_template("template_atestado_corrigido.html")

            zip_buffer = io.BytesIO()
            atestados_gerados = 0
            dados_ignorados = []

            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for (empresa_nome, cnpj), grupo in grupos:
                    primeira_linha = grupo.iloc[0]
                    endereco = primeira_linha.get("ENDEREÇO", "")
                    sigla_und = str(primeira_linha.get("UND", "Sem Sigla")).strip()
                    motivos_falha = []

                    if valor_esta_vazio(cnpj):
                        motivos_falha.append("CNPJ ausente")
                    if valor_esta_vazio(endereco):
                        motivos_falha.append("Endereço ausente")
                    if valor_esta_vazio(empresa_nome):
                        motivos_falha.append("Nome ausente")

                    if motivos_falha:
                        dados_ignorados.append(
                            {
                                "Unidade (UND)": sigla_und,
                                "Empresa": str(empresa_nome),
                                "CNPJ": str(cnpj) if not pd.isna(cnpj) else "Vazio",
                                "Motivo / Inconsistência": " | ".join(motivos_falha),
                                "Alunos Afetados": len(grupo),
                            }
                        )
                        continue

                    lista_alunos = []
                    for _, row in grupo.iterrows():
                        und_aluno = str(row.get("UND", "") or "").strip() or sigla_und
                        lista_alunos.append(
                            {
                                "nome": str(row.get("NOME", "")).strip().upper(),
                                "rg": formatar_documento(row.get("RG", "")),
                                "cpf": formatar_documento(row.get("CPF", "")),
                                "data_nasc": formatar_data(
                                    row.get("DATA_NASC", row.get("NASC", ""))
                                ),
                                "data_matricula": formatar_data(
                                    row.get(
                                        "DATA TÉRMINO", row.get("CONCLUSÃO", "")
                                    )
                                ),
                                "horas": str(row.get("CARGA HORARIA", "")).strip(),
                                "Treinamento": "Intermediário",
                                "unidade": und_aluno,
                            }
                        )

                    TAMANHO_PAGINA = 20
                    if not lista_alunos:
                        paginas_alunos = [[]]
                    else:
                        paginas_alunos = [
                            lista_alunos[i : i + TAMANHO_PAGINA]
                            for i in range(0, len(lista_alunos), TAMANHO_PAGINA)
                        ]

                    contexto = {
                        "LOGO_CT": ct_selecionado_dados.get("logo_url", ""),
                        "LOGO_CONECTA": URL_LOGO_CONECTA,
                        "ASSINATURA_IMG": assinatura_url_final,
                        "EMPRESA": str(empresa_nome).strip(),
                        "ENDERECO": str(endereco).strip(),
                        "CNPJ": str(cnpj).strip(),
                        "NORMA": primeira_linha.get("OBS", "tabela B.2 da IT 17"),
                        "CIDADE_DATA": cidade_data_final,
                        "NOME_INSTRUTOR": nome_instrutor,
                        "DOC_INSTRUTOR": doc_instrutor,  # CPF formatado do cadastro
                        "RE_INSTRUTOR": re_instrutor,
                        "CT_NOME": ct_selecionado_dados.get("full_name")
                        or ct_selecionado_dados.get("name", ""),
                        "CT_CNPJ": ct_selecionado_dados.get("cnpj", ""),
                        "CT_ENDERECO": ct_selecionado_dados.get("full_address", ""),
                        "CT_TELEFONE": ct_selecionado_dados.get("phone", ""),
                        "CURSO_NOME": "Treinamento Técnico",
                        "MODALIDADE_TURMA": "Incompany",
                        "NIVEL_TURMA": "Intermediário",
                        "mostrar_coluna_rg": mostrar_rg,
                        "mostrar_coluna_nasc": mostrar_nasc,
                        "mostrar_coluna_data": mostrar_data_conclusao,
                        "mostrar_coluna_unidade": mostrar_unidade,
                        "paginas": paginas_alunos,
                    }

                    html_renderizado = template.render(contexto)
                    sigla_sanitizada = "".join(
                        c for c in sigla_und if c.isalnum() or c in (" ", "_", "-")
                    ).strip()
                    pdf_bytes = HTML(string=html_renderizado).write_pdf()
                    zip_file.writestr(f"{sigla_sanitizada}.pdf", pdf_bytes)
                    atestados_gerados += 1

            zip_buffer.seek(0)

            st.markdown("---")
            st.subheader("📊 Resultados do Processamento")

            aba_download, aba_erros = st.tabs(
                ["📥 Área de Download", "⚠️ Inconsistências"]
            )
            with aba_download:
                if atestados_gerados > 0:
                    st.success(f"✅ {atestados_gerados} atestados gerados com sucesso!")
                    st.download_button(
                        "📦 Baixar Atestados (.zip)",
                        data=zip_buffer,
                        file_name="atestados.zip",
                        mime="application/zip",
                    )
            with aba_erros:
                if dados_ignorados:
                    st.dataframe(
                        pd.DataFrame(dados_ignorados), use_container_width=True
                    )
                else:
                    st.info("Nenhuma inconsistência.")
