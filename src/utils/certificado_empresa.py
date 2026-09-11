import os
import base64
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS

_FUNDO_DEFAULT = "https://vesgrrejcehseygchigh.supabase.co/storage/v1/object/public/logos/certificado_conecta_fundo.png"
_ASSINATURA_RESP_TECNICO_DEFAULT = "https://vesgrrejcehseygchigh.supabase.co/storage/v1/object/public/assinaturas/assinatura_responsavel_tecnico.png"

def _imagem_para_data_uri(caminho: str) -> str:
    ext = os.path.splitext(caminho)[1].lower().lstrip(".")
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif", "webp": "webp"}.get(ext, "png")
    with open(caminho, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:image/{mime};base64,{b64}"

def _resolver_imagem(caminho):
    if not caminho:
        return ""
    if caminho.startswith(("http://", "https://", "data:")):
        return caminho
    if os.path.exists(caminho):
        try:
            return _imagem_para_data_uri(caminho)
        except Exception:
            return ""
    return ""

def formatar_cpf(cpf: str) -> str:
    cpf = (cpf or "").strip()
    if len(cpf) == 11 and cpf.isdigit():
        return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
    return cpf

def gerar_certificado_empresa_pdf(
    turma: dict,
    instrutor: dict,
    empresa: dict,
    ct: dict | None = None,
    alunos: list = None,
    normativa: str = "",
    cidade_data: str = "",
    nome_curso: str = "Treinamento Técnico",
    caminho_fundo: str = None,
    caminho_pasta_templates: str = "src/templates",
    nome_template: str = "template_certificado_empresa.html",
) -> bytes:
    env = Environment(loader=FileSystemLoader(caminho_pasta_templates))
    template = env.get_template(nome_template)

    fundo_path = caminho_fundo if caminho_fundo else (ct.get("fundo_certificado_url") if ct else _FUNDO_DEFAULT)
    imagem_fundo = _resolver_imagem(fundo_path) or _FUNDO_DEFAULT

    assinatura_instrutor = _resolver_imagem(instrutor.get("assinatura", ""))
    cpf_instrutor_fmt = formatar_cpf(instrutor.get("cpf", ""))

    resp_tecnico_nome = (turma.get("resp_tecnico") or "").strip()
    cpf_resp_fmt = formatar_cpf(turma.get("cpf_resp_tecnico", ""))
    assinatura_resp_tecnico = _ASSINATURA_RESP_TECNICO_DEFAULT if resp_tecnico_nome else ""

    total_colaboradores = len(alunos) if alunos else 0

    html_renderizado = template.render(
        IMAGEM_FUNDO=imagem_fundo,
        EMPRESA=empresa.get("name", ""),
        ENDERECO_EMPRESA=empresa.get("full_address", ""),
        CNPJ_EMPRESA=empresa.get("cnpj", ""),

        NIVEL=turma.get("nivel", "Intermediário"),
        MODALIDADE=turma.get("modalidade", "CT"),
        CARGA_HORARIA=turma.get("carga_horaria", "08 Horas"),
        CURSO_NOME=nome_curso,
        NORMATIVA=normativa,
        TOTAL_COLABORADORES=total_colaboradores,
        CIDADE_DATA=cidade_data,

        NOME_INSTRUTOR=instrutor.get("name", ""),
        CPF_INSTRUTOR=cpf_instrutor_fmt,
        ASSINATURA_INSTRUTOR=assinatura_instrutor,

        RESP_TECNICO=resp_tecnico_nome,
        CPF_RESP=cpf_resp_fmt,
        ASSINATURA_RESP_TECNICO=assinatura_resp_tecnico,
    )

    pdf_bytes = HTML(string=html_renderizado).write_pdf(
        stylesheets=[CSS(string="@page { size: A4 landscape; margin: 0; }")]
    )
    return pdf_bytes