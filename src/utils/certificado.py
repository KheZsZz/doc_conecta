import os
import base64
import io
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS

# Caminho padrão da imagem de fundo do certificado
_FUNDO_DEFAULT = "https://vesgrrejcehseygchigh.supabase.co/storage/v1/object/public/logos/certificados.png"


def _imagem_para_data_uri(caminho: str) -> str:
    """Converte uma imagem local para data URI base64 (evita problemas de path no WeasyPrint)."""
    ext = os.path.splitext(caminho)[1].lower().lstrip(".")
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif", "webp": "webp"}.get(ext, "png")
    with open(caminho, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:image/{mime};base64,{b64}"


def gerar_certificado_html(
    aluno: dict,
    turma: dict,
    instrutor: dict,
    empresa: dict | None = None,
    normativa: str = "",
    cidade_data: str = "",
    caminho_fundo: str | None = None,
    caminho_pasta_templates: str = "src/templates",
) -> str:
    """
    Gera o HTML de um certificado individual.

    Parâmetros
    ----------
    aluno       : dict com keys: name, cpf, rg (opcional)
    turma       : dict com keys: modalidade, carga_horaria (da matrícula), nivel (opcional)
    instrutor   : dict com keys: name, cpf, cbo, assinatura (path)
    empresa     : dict com keys: name, full_address (opcional)
    normativa   : string da normativa do curso
    cidade_data : string formatada da data (ex: "Itapecerica da Serra, 18 de julho de 2025")
    caminho_fundo: path para a imagem PNG de fundo ou URL (usa _FUNDO_DEFAULT por padrão)
    """
    env = Environment(loader=FileSystemLoader(caminho_pasta_templates))
    template = env.get_template("template_certificado.html")

    # --- Imagem de fundo como data URI ou URL remota ---
    fundo_path = caminho_fundo or _FUNDO_DEFAULT
    
    if fundo_path.startswith(("http://", "https://")):
        imagem_fundo = fundo_path
    elif os.path.exists(fundo_path):
        imagem_fundo = _imagem_para_data_uri(fundo_path)
    else:
        imagem_fundo = ""

    # --- Assinatura do instrutor ---
    assinatura_instrutor = ""
    assinatura_path = instrutor.get("assinatura", "")
    if assinatura_path:
        if assinatura_path.startswith(("http://", "https://")):
            assinatura_instrutor = assinatura_path
        elif os.path.exists(assinatura_path):
            assinatura_instrutor = _imagem_para_data_uri(assinatura_path)

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

    html = template.render(
        IMAGEM_FUNDO=imagem_fundo,
        NOME_ALUNO=aluno.get("name", ""),
        RG_CPF=rg_cpf_str,
        EMPRESA=empresa.get("name", "") if empresa else "",
        ENDERECO_EMPRESA=empresa.get("full_address", "") if empresa else "",
        NIVEL=turma.get("nivel", "Formação"),
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
    normativa: str = "",
    cidade_data: str = "",
    caminho_fundo: str | None = None,
    caminho_pasta_templates: str = "src/templates",
) -> bytes:
    """
    Gera um único PDF com todos os certificados (um por página, orientação paisagem).

    alunos_matriculas: lista de dicts com keys:
        name, cpf, rg (opt), data_nasc (opt), horas (carga horária individual)
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
            normativa=normativa,
            cidade_data=cidade_data,
            caminho_fundo=caminho_fundo,
            caminho_pasta_templates=caminho_pasta_templates,
        )
        paginas_html.append(html_pagina)

    if not paginas_html:
        raise ValueError("Nenhum aluno para gerar certificado.")

    # WeasyPrint: cada HTML vira um documento, depois mesclamos via pypdf
    # Estratégia: gerar cada um e concatenar com pypdf
    from pypdf import PdfWriter

    writer = PdfWriter()

    for html_str in paginas_html:
        pdf_bytes_individual = HTML(string=html_str).write_pdf(
            stylesheets=[
                CSS(string="@page { size: A4 landscape; margin: 0; }")
            ]
        )
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes_individual))
        for page in reader.pages:
            writer.add_page(page)

    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()