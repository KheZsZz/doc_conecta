import os
import base64
import io
import zipfile
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS
from datetime import datetime

# Caminhos padrão das imagens de fundo do certificado (fallback)
_FUNDO_DEFAULT = "https://vesgrrejcehseygchigh.supabase.co/storage/v1/object/public/logos/certificado_conecta_fundo.png"


def _imagem_para_data_uri(caminho: str) -> str:
    """Converte uma imagem local para data URI base64 (evita problemas de path no WeasyPrint)."""
    ext = os.path.splitext(caminho)[1].lower().lstrip(".")
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif", "webp": "webp"}.get(ext, "png")
    with open(caminho, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:image/{mime};base64,{b64}"


def _resolver_imagem(caminho_ou_url: str) -> str:
    """
    Resolve uma referência de imagem (assinatura, logo, fundo, etc.) vinda do banco para algo
    que o WeasyPrint consegue renderizar quando o HTML é montado como string em memória:
      - URL http(s) (ex: Supabase Storage) -> usada diretamente
      - caminho local existente -> convertido para data URI base64
      - qualquer outro caso (arquivo local ausente, vazio, etc.) -> string vazia
    """
    if not caminho_ou_url:
        return ""
    caminho_ou_url = str(caminho_ou_url).strip()
    if caminho_ou_url.startswith(("http://", "https://", "data:")):
        return caminho_ou_url
    if os.path.exists(caminho_ou_url):
        try:
            return _imagem_para_data_uri(caminho_ou_url)
        except Exception:
            return ""
    return ""


def gerar_certificado_html(
    aluno: dict,
    turma: dict,
    instrutor: dict,
    empresa: dict | None = None,
    ct: dict | None = None,
    normativa: str = "",
    cidade_data: str = "",
    caminho_fundo: str | None = None,
    caminho_pasta_templates: str = "src/templates",
) -> str:
    """
    Gera o HTML de um certificado individual.

    Parâmetros
    ----------
    aluno       : dict com keys: name, cpf, rg (opcional), data_nasc (opcional)
    turma       : dict com keys: modalidade, carga_horaria (da matrícula), nivel (opcional)
    instrutor   : dict com keys: name, cpf, cbo, assinatura (path)
    empresa     : dict com keys: name, full_address (opcional)
    ct          : dict com keys: fundo_certificado_url (opcional)
    normativa   : string da normativa do curso
    cidade_data : string formatada da data (ex: "Itapecerica da Serra, 18 de julho de 2025")
    caminho_fundo: path para a imagem PNG de fundo ou URL (sobrescreve o fundo do CT)
    """
    env = Environment(loader=FileSystemLoader(caminho_pasta_templates))
    template = env.get_template("template_certificado.html")

    # --- Definição do Fundo: prioridade é CT > caminho_fundo > fallback padrão ---
    fundo_path = ""
    
    if caminho_fundo:
        # Se foi passado um caminho/URL específico, usa esse
        fundo_path = caminho_fundo
    elif ct and ct.get("fundo_certificado_url"):
        # Caso contrário, usa o fundo do CT se disponível
        fundo_path = ct.get("fundo_certificado_url")
    else:
        # Fallback para fundo padrão
        fundo_path = _FUNDO_DEFAULT

    # --- Imagem de fundo como data URI ou URL remota ---
    if fundo_path.startswith(("http://", "https://")):
        imagem_fundo = fundo_path
    elif os.path.exists(fundo_path):
        imagem_fundo = _imagem_para_data_uri(fundo_path)
    else:
        imagem_fundo = _FUNDO_DEFAULT  # Fallback se nada funcionar

    # --- Assinatura do instrutor ---
    assinatura_instrutor = ""
    assinatura_path = instrutor.get("assinatura", "")
    if assinatura_path:
        assinatura_instrutor = _resolver_imagem(assinatura_path)

    # --- RG/CPF do aluno formatado ---
    cpf = aluno.get("cpf", "")
    rg = aluno.get("rg", "")
    partes_doc = []
    if rg:
        partes_doc.append(f"RG: {rg}")
    if cpf:
        cpf_fmt = f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}" if len(cpf) == 11 else cpf
        partes_doc.append(f"CPF: {cpf_fmt}")
    rg_cpf_str = " / ".join(partes_doc)

    # --- CPF do instrutor formatado ---
    cpf_inst = instrutor.get("cpf", "")
    cpf_inst_fmt = (
        f"{cpf_inst[:3]}.{cpf_inst[3:6]}.{cpf_inst[6:9]}-{cpf_inst[9:]}"
        if len(cpf_inst) == 11 else cpf_inst
    )

    # --- Formatação da Data de Nascimento (DD/MM/YYYY) ---
    data_nasc_raw = aluno.get("data_nasc") or aluno.get("data_nascimento") or aluno.get("birth_date") or ""
    data_nasc_fmt = ""
    if data_nasc_raw:
        try:
            dt = datetime.strptime(str(data_nasc_raw).split("T")[0], "%Y-%m-%d")
            data_nasc_fmt = dt.strftime("%d/%m/%Y")
        except Exception:
            data_nasc_fmt = str(data_nasc_raw)

    html = template.render(
        IMAGEM_FUNDO=imagem_fundo,
        NOME_ALUNO=aluno.get("name", ""),
        RG_CPF=rg_cpf_str,
        DATA_NASCIMENTO=data_nasc_fmt,
        EMPRESA=empresa.get("name", "") if empresa else "",
        ENDERECO_EMPRESA=empresa.get("full_address", "") if empresa else "",
        NIVEL=turma.get("nivel", "Intermediário"),
        MODALIDADE=turma.get("modalidade", "Presencial"),
        CARGA_HORARIA=turma.get("carga_horaria", "8 Horas"),
        NORMATIVA=normativa,
        CIDADE_DATA=cidade_data,
        ASSINATURA_INSTRUTOR=assinatura_instrutor,
        NOME_INSTRUTOR=instrutor.get("name", ""),
        CPF_INSTRUTOR=cpf_inst_fmt,
        RESP_TECNICO=turma.get("resp_tecnico", ""),
        CPF_RESP=turma.get("cpf_resp_tecnico", ""),
        ASSINATURA_RESP_TECNICO="https://vesgrrejcehseygchigh.supabase.co/storage/v1/object/public/assinaturas/assinatura_responsavel_tecnico.png"
    )
    return html


def gerar_certificados_pdf(
    alunos_matriculas: list[dict],
    turma: dict,
    instrutor: dict,
    empresa: dict | None = None,
    ct: dict | None = None,
    normativa: str = "",
    cidade_data: str = "",
    caminho_fundo: str | None = None,
    caminho_pasta_templates: str = "src/templates",
) -> bytes:
    """
    Gera um único PDF com todos os certificados (um por página, orientação paisagem).

    alunos_matriculas: lista de dicts com keys:
        name, cpf, rg (opt), data_nasc (opt), horas (carga horária individual)
    ct: dict com dados do CT (fundo_certificado_url, etc)
    """
    paginas_html = []

    for aluno in alunos_matriculas:
        # Carga horária pode ser individual por matrícula
        turma_aluno = {**turma, "carga_horaria": aluno.get("horas", turma.get("carga_horaria", "8 Horas"))}
        
        html_pagina = gerar_certificado_html(
            aluno=aluno,
            turma=turma_aluno,
            instrutor=instrutor,
            empresa=empresa,
            ct=ct,
            normativa=normativa,
            cidade_data=cidade_data,
            caminho_fundo=caminho_fundo,
            caminho_pasta_templates=caminho_pasta_templates,
        )
        paginas_html.append(html_pagina)

    if not paginas_html:
        raise ValueError("Nenhum aluno para gerar certificado.")

    # WeasyPrint: cada HTML vira um documento, depois mesclamos via pypdf
    from pypdf import PdfWriter, PdfReader

    writer = PdfWriter()

    for html_str in paginas_html:
        pdf_bytes_individual = HTML(string=html_str).write_pdf(
            stylesheets=[
                CSS(string="@page { size: A4 landscape; margin: 0; }")
            ]
        )
        reader = PdfReader(io.BytesIO(pdf_bytes_individual))
        for page in reader.pages:
            writer.add_page(page)

    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def gerar_certificados_pdf_zip(
    alunos_matriculas: list[dict],
    turma: dict,
    instrutor: dict,
    empresa: dict | None = None,
    ct: dict | None = None,
    normativa: str = "",
    cidade_data: str = "",
    caminho_fundo: str | None = None,
    caminho_pasta_templates: str = "src/templates",
) -> bytes:
    """
    Gera um ZIP contendo um PDF individual para cada aluno, nomeado com o nome do aluno.

    alunos_matriculas: lista de dicts com keys:
        name, cpf, rg (opt), data_nasc (opt), horas (carga horária individual)
    ct: dict com dados do CT (fundo_certificado_url, etc)
    
    Retorna: bytes do arquivo ZIP
    """
    if not alunos_matriculas:
        raise ValueError("Nenhum aluno para gerar certificado.")

    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for aluno in alunos_matriculas:
            # Carga horária individual por matrícula
            turma_aluno = {**turma, "carga_horaria": aluno.get("horas", turma.get("carga_horaria", "8 Horas"))}
            
            # Gera HTML do certificado
            html_certificado = gerar_certificado_html(
                aluno=aluno,
                turma=turma_aluno,
                instrutor=instrutor,
                empresa=empresa,
                ct=ct,
                normativa=normativa,
                cidade_data=cidade_data,
                caminho_fundo=caminho_fundo,
                caminho_pasta_templates=caminho_pasta_templates,
            )
            
            # Converte HTML para PDF
            pdf_bytes = HTML(string=html_certificado).write_pdf(
                stylesheets=[
                    CSS(string="@page { size: A4 landscape; margin: 0; }")
                ]
            )
            
            # Sanitiza o nome do aluno para usar como nome de arquivo
            nome_aluno = aluno.get("name", "aluno").strip()
            # Remove caracteres especiais, mantém apenas letras, números, espaços e hífens
            nome_sanitizado = "".join(c if c.isalnum() or c in (' ', '-', '_') else '' for c in nome_aluno)
            nome_sanitizado = nome_sanitizado.strip().replace(' ', '_')
            
            # Define o nome do arquivo PDF
            nome_arquivo_pdf = f"Certificado_{nome_sanitizado}.pdf"
            
            # Adiciona o PDF ao ZIP
            zip_file.writestr(nome_arquivo_pdf, pdf_bytes)
    
    zip_buffer.seek(0)
    return zip_buffer.getvalue()