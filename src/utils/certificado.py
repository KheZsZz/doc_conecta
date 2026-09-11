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
    aluno: dict, turma: dict, instrutor: dict, empresa: dict | None = None,
    ct: dict | None = None, normativa: str = "", cidade_data: str = "",
    nome_curso: str = "Treinamento Técnico", # 👈 ADICIONADO
    caminho_fundo: str | None = None, caminho_pasta_templates: str = "src/templates"
) -> str:
    env = Environment(loader=FileSystemLoader(caminho_pasta_templates))
    template = env.get_template("template_certificado.html")

    fundo_path = caminho_fundo if caminho_fundo else (ct.get("fundo_certificado_url") if ct and ct.get("fundo_certificado_url") else _FUNDO_DEFAULT)
    imagem_fundo = _resolver_imagem(fundo_path) or _FUNDO_DEFAULT
    assinatura_instrutor = _resolver_imagem(instrutor.get("assinatura", ""))

    cpf, rg = aluno.get("cpf", ""), aluno.get("rg", "")
    partes_doc = []
    if rg: partes_doc.append(f"RG: {rg}")
    if cpf: partes_doc.append(f"CPF: {cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}" if len(cpf) == 11 else cpf)

    cpf_inst = instrutor.get("cpf", "")
    cpf_inst_fmt = f"{cpf_inst[:3]}.{cpf_inst[3:6]}.{cpf_inst[6:9]}-{cpf_inst[9:]}" if len(cpf_inst) == 11 else cpf_inst

    data_nasc_raw = aluno.get("data_nasc") or aluno.get("data_nascimento") or ""
    data_nasc_fmt = datetime.strptime(str(data_nasc_raw).split("T")[0], "%Y-%m-%d").strftime("%d/%m/%Y") if data_nasc_raw else ""

    return template.render(
        IMAGEM_FUNDO=imagem_fundo,
        NOME_ALUNO=aluno.get("name", ""),
        RG_CPF=" / ".join(partes_doc),
        DATA_NASCIMENTO=data_nasc_fmt,
        EMPRESA=empresa.get("name", "") if empresa else "",
        ENDERECO_EMPRESA=empresa.get("full_address", "") if empresa else "",
        
        NIVEL=turma.get("nivel", "Intermediário"),
        MODALIDADE=turma.get("modalidade", "Presencial"),
        CARGA_HORARIA=turma.get("carga_horaria", "8 Horas"),
        CURSO_NOME=nome_curso, # 👈 INJETADO
        NORMATIVA=normativa,
        
        CIDADE_DATA=cidade_data,
        ASSINATURA_INSTRUTOR=assinatura_instrutor,
        NOME_INSTRUTOR=instrutor.get("name", ""),
        CPF_INSTRUTOR=cpf_inst_fmt,
        RESP_TECNICO=turma.get("resp_tecnico", ""),
        CPF_RESP=turma.get("cpf_resp_tecnico", ""),
        ASSINATURA_RESP_TECNICO="https://vesgrrejcehseygchigh.supabase.co/storage/v1/object/public/assinaturas/assinatura_responsavel_tecnico.png"
    )

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
    alunos_matriculas: list[dict], turma: dict, instrutor: dict,
    empresa: dict | None = None, ct: dict | None = None, normativa: str = "",
    cidade_data: str = "", nome_curso: str = "Treinamento Técnico", # 👈 ADICIONADO
    caminho_fundo: str | None = None, caminho_pasta_templates: str = "src/templates"
) -> bytes:
    if not alunos_matriculas: raise ValueError("Nenhum aluno para gerar certificado.")
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for aluno in alunos_matriculas:
            turma_aluno = {**turma, "carga_horaria": aluno.get("horas", turma.get("carga_horaria", "8 Horas"))}
            html_certificado = gerar_certificado_html(
                aluno=aluno, turma=turma_aluno, instrutor=instrutor, empresa=empresa, ct=ct,
                normativa=normativa, cidade_data=cidade_data, nome_curso=nome_curso, # 👈 REPASSADO
                caminho_fundo=caminho_fundo, caminho_pasta_templates=caminho_pasta_templates
            )
            pdf_bytes = HTML(string=html_certificado).write_pdf(stylesheets=[CSS(string="@page { size: A4 landscape; margin: 0; }")])
            nome_sanitizado = "".join(c if c.isalnum() or c in (' ', '-', '_') else '' for c in aluno.get("name", "aluno")).strip().replace(' ', '_')
            zip_file.writestr(f"Certificado_{nome_sanitizado}.pdf", pdf_bytes)
    
    return zip_buffer.getvalue()