import os
import base64
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS

_FUNDO_DEFAULT = "https://vesgrrejcehseygchigh.supabase.co/storage/v1/object/public/logos/certificado_conecta_fundo.png"
_FUNDO_TREINNAR = "https://vesgrrejcehseygchigh.supabase.co/storage/v1/object/public/logos/Certificados_treinnar.jpg"


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


def _fundo_do_ct(ct: dict | None) -> str:
    ct = ct or {}
    for key in (
        "fundo_certificado_url",
        "fundo_certificado",
        "certificado_fundo_url",
        "fundo_url",
        "url_fundo_certificado",
    ):
        val = (ct.get(key) or "").strip()
        if val:
            return val
    for k, v in ct.items():
        if isinstance(v, str) and v.startswith("http") and "certificado" in v.lower():
            return v.strip()
    nome = f"{ct.get('name') or ''} {ct.get('full_name') or ''}".lower()
    if "treinnar" in nome:
        return _FUNDO_TREINNAR
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
    caminho_fundo: str = None,
    caminho_pasta_templates: str = "src/templates",
    nome_template: str = "template_certificado_empresa.html",
) -> bytes:
    env = Environment(loader=FileSystemLoader(caminho_pasta_templates))
    template = env.get_template(nome_template)

    fundo_path = (caminho_fundo or "").strip() or _fundo_do_ct(ct) or _FUNDO_DEFAULT
    imagem_fundo = _resolver_imagem(fundo_path) or _FUNDO_DEFAULT

    assinatura_instrutor = _resolver_imagem(
        instrutor.get("assinatura") or instrutor.get("assinatura_url") or ""
    )
    cpf_instrutor_fmt = formatar_cpf(instrutor.get("cpf", ""))
    re_instrutor = (instrutor.get("re") or "").strip()
    formacao_instrutor = (instrutor.get("formacao") or "").strip()

    resp_tecnico_nome = (turma.get("resp_tecnico") or "").strip()
    cpf_resp_fmt = formatar_cpf(turma.get("cpf_resp_tecnico", ""))
    re_resp = (turma.get("re_resp_tecnico") or "").strip()
    formacao_resp = (turma.get("formacao_resp_tecnico") or "").strip()
    assinatura_resp_tecnico = _resolver_imagem(turma.get("assinatura_resp_url", ""))

    total_colaboradores = len(alunos) if alunos else 0

    dizeres = turma.get("dizeres_certificado_empresa")
    if not dizeres:
        dizeres = (
            "Certificamos que a empresa acima identificada promoveu o treinamento de "
            "“Brigada de Incêndio - Prevenção e Combate a Incêndio e Primeiros Socorros”, "
            "de acordo com as normas NBR 14277 da ABNT, e IT-17 do Corpo de Bombeiros."
        )

    nivel = (turma.get("nivel") or "").strip() or "Formação"
    modalidade = (turma.get("modalidade") or "").strip() or "In Company"
    carga = (turma.get("carga_horaria") or "").strip() or "08 Horas"

    html_renderizado = template.render(
        IMAGEM_FUNDO=imagem_fundo,
        EMPRESA=empresa.get("name", ""),
        ENDERECO_EMPRESA=empresa.get("full_address", ""),
        CNPJ_EMPRESA=empresa.get("cnpj", ""),
        NIVEL=nivel,
        MODALIDADE=modalidade,
        CARGA_HORARIA=carga,
        NORMATIVA=normativa,
        TOTAL_COLABORADORES=total_colaboradores,
        CIDADE_DATA=cidade_data,
        NOME_INSTRUTOR=instrutor.get("name", ""),
        CPF_INSTRUTOR=cpf_instrutor_fmt,
        RE_INSTRUTOR=re_instrutor,
        FORMACAO_INSTRUTOR=formacao_instrutor,
        ASSINATURA_INSTRUTOR=assinatura_instrutor,
        RESP_TECNICO=resp_tecnico_nome,
        CPF_RESP=cpf_resp_fmt,
        RE_RESP=re_resp,
        FORMACAO_RESP=formacao_resp,
        ASSINATURA_RESP_TECNICO=assinatura_resp_tecnico,
        DIZERES_CERTIFICADO=dizeres,
    )

    return HTML(string=html_renderizado).write_pdf(
        stylesheets=[CSS(string="@page { size: A4 landscape; margin: 0; }")]
    )
