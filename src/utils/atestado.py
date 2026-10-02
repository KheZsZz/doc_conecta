import os
import base64
from datetime import datetime

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS


def formatar_data_br(data_str):
    if not data_str:
        return ""
    data_str_limpa = str(data_str).strip()
    if not data_str_limpa or data_str_limpa.lower() in ("nan", "none", "nat"):
        return ""
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(data_str_limpa[:10], "%Y-%m-%d")
            return dt.strftime("%d/%m/%Y")
        except ValueError:
            continue
    return data_str_limpa


def _tem_valor(val) -> bool:
    if val is None:
        return False
    s = str(val).strip()
    return bool(s) and s.lower() not in ("nan", "none", "nat", "-")


def _imagem_para_data_uri(caminho: str) -> str:
    ext = os.path.splitext(caminho)[1].lower().lstrip(".")
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif", "webp": "webp"}.get(
        ext, "png"
    )
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


def gerar_atestado_pdf_de_arquivo(
    *,
    alunos: list | None = None,
    turma: dict | None = None,
    empresa: dict | None = None,
    instrutor: dict | None = None,
    ct: dict | None = None,
    curso: dict | None = None,
    cidade_data_formatada: str = "",
    alunos_matriculas: list | None = None,
    dados_turma: dict | None = None,
    caminho_pasta_templates: str = "src/templates",
) -> bytes:
    alunos_lista = alunos if alunos is not None else (alunos_matriculas or [])
    turma = turma or dados_turma or {}
    empresa = empresa or {}
    instrutor = instrutor or {}
    curso = curso or {}

    env = Environment(loader=FileSystemLoader(caminho_pasta_templates))
    template = env.get_template("template_atestado_corrigido.html")

    mostrar_coluna_rg = any(_tem_valor(a.get("rg")) for a in alunos_lista)
    mostrar_coluna_nasc = any(_tem_valor(a.get("data_nasc")) for a in alunos_lista)

    datas_unicas = {
        formatar_data_br(a.get("data_matricula") or a.get("data_treinamento"))
        for a in alunos_lista
        if _tem_valor(a.get("data_matricula") or a.get("data_treinamento"))
    }
    datas_unicas.discard("")
    mostrar_coluna_data = len(datas_unicas) > 1

    nivel_padrao = turma.get("nivel") or turma.get("nivel_turma") or "Basico"

    alunos_processados = []
    for aluno in alunos_lista:
        data_raw = aluno.get("data_matricula") or aluno.get("data_treinamento") or ""
        data_formatada = formatar_data_br(data_raw)

        item = {
            "nome": aluno.get("nome") or aluno.get("name") or "Sem Nome",
            "rg": str(aluno.get("rg") or "").strip(),
            "cpf": str(aluno.get("cpf") or "").strip(),
            "data_nasc": formatar_data_br(aluno.get("data_nasc", "")),
            "Treinamento": aluno.get("Treinamento") or nivel_padrao,
            "horas": aluno.get("horas") or turma.get("carga_horaria") or "8 Horas",
            "data_matricula": data_formatada,
            "data_treinamento": data_formatada,
            "data": data_formatada,
        }
        alunos_processados.append(item)

    if ct and isinstance(ct, dict):
        ct_nome = ct.get("full_name") or ct.get("name") or ""
        ct_cnpj = ct.get("cnpj") or ""
        ct_endereco = ct.get("full_address") or ""
        ct_telefone = ct.get("phone") or ""
        ct_logo = ct.get("logo_url") or ""
    else:
        ct_nome = empresa.get("name") or ""
        ct_cnpj = empresa.get("cnpj") or ""
        ct_endereco = empresa.get("full_address") or ""
        ct_telefone = empresa.get("phone") or ""
        ct_logo = ""

    ct_logo_resolvida = _resolver_imagem(ct_logo)
    assinatura_src = (
        instrutor.get("assinatura")
        or instrutor.get("assinatura_url")
        or instrutor.get("signature_url")
        or ""
    )
    assinatura_resolvida = _resolver_imagem(assinatura_src)

    TAMANHO_PAGINA = 20
    if not alunos_processados:
        paginas_alunos = [[]]
    else:
        paginas_alunos = [
            alunos_processados[i : i + TAMANHO_PAGINA]
            for i in range(0, len(alunos_processados), TAMANHO_PAGINA)
        ]

    curso_nome = (
        curso.get("name")
        or turma.get("curso_nome")
        or "Treinamento Tecnico"
    )
    modalidade = turma.get("modalidade") or turma.get("modalidade_turma") or ""
    nivel = turma.get("nivel") or turma.get("nivel_turma") or ""
    normativa = turma.get("normativa") or curso.get("normativa") or ""
    cidade_data = cidade_data_formatada or turma.get("cidade_data") or ""

    re_instrutor = (instrutor.get("re") or "").strip()

    html_renderizado = template.render(
        LOGO_CT=ct_logo_resolvida,
        LOGO_CONECTA="https://vesgrrejcehseygchigh.supabase.co/storage/v1/object/public/logos/logo_conecta.png",
        EMPRESA=empresa.get("name") or "",
        ENDERECO=empresa.get("full_address") or "",
        CNPJ=empresa.get("cnpj") or "",
        CT_NOME=ct_nome,
        CT_CNPJ=ct_cnpj,
        CT_ENDERECO=ct_endereco,
        CT_TELEFONE=ct_telefone,
        NORMA=normativa,
        CIDADE_DATA=cidade_data,
        CURSO_NOME=curso_nome,
        MODALIDADE_TURMA=modalidade,
        NIVEL_TURMA=nivel,
        ASSINATURA_IMG=assinatura_resolvida,
        NOME_INSTRUTOR=instrutor.get("name") or "",
        DOC_INSTRUTOR=instrutor.get("cpf") or "",
        RE_INSTRUTOR=re_instrutor,
        mostrar_coluna_rg=mostrar_coluna_rg,
        mostrar_coluna_nasc=mostrar_coluna_nasc,
        mostrar_coluna_data=mostrar_coluna_data,
        paginas=paginas_alunos,
    )

    pdf_bytes = HTML(string=html_renderizado).write_pdf(
        stylesheets=[CSS(string="@page { size: A4 portrait; margin: 10mm 10mm 5mm 10mm; }")]
    )
    return pdf_bytes
