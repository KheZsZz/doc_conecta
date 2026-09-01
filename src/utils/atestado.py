import os
import base64
from datetime import datetime
from jinja2 import Environment, FileSystemLoader

def formatar_data_br(data_str):
    """Converte string de data (ex: YYYY-MM-DD) para o padrão brasileiro DD/MM/YYYY."""
    if not data_str:
        return ""
    data_str_limpa = str(data_str).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(data_str_limpa[:10], fmt.split()[0])
            return dt.strftime("%d/%m/%Y")
        except ValueError:
            continue
    return data_str_limpa  # Retorna o original se não conseguir converter


def _imagem_para_data_uri(caminho: str) -> str:
    """Converte uma imagem local para data URI base64 (evita problemas de path no WeasyPrint)."""
    ext = os.path.splitext(caminho)[1].lower().lstrip(".")
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif", "webp": "webp"}.get(ext, "png")
    with open(caminho, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:image/{mime};base64,{b64}"


def _resolver_imagem(caminho_ou_url: str) -> str:
    """
    Resolve uma referência de imagem (assinatura, logo, etc.) vinda do banco para algo
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
    # Caminho local salvo no banco não existe mais no filesystem atual (ex: app reiniciado
    # em ambiente com storage efêmero) — não há como recuperar a imagem aqui.
    return ""


def gerar_atestado_pdf_de_arquivo(dados_turma, alunos_matriculas, instrutor, empresa, ct=None, caminho_pasta_templates="src/templates"):
    env = Environment(loader=FileSystemLoader(caminho_pasta_templates))
    template = env.get_template("template_atestado_corrigido.html")

    # Regras das colunas avaliadas para todos os alunos (para manter as tabelas iguais em todas as páginas)
    mostrar_coluna_rg = any(a.get("rg") and str(a.get("rg")).strip() for a in alunos_matriculas)
    mostrar_coluna_nasc = any(a.get("data_nasc") and str(a.get("data_nasc")).strip() for a in alunos_matriculas)
    datas_unicas = set(a.get("data_matricula") for a in alunos_matriculas if a.get("data_matricula"))
    mostrar_coluna_data = len(datas_unicas) > 1

    alunos_processados = []
    for aluno in alunos_matriculas:
        item = {
            "nome": aluno.get("nome", "Sem Nome"),
            "rg": aluno.get("rg", ""),
            "cpf": aluno.get("cpf", ""),
            "data_nasc": formatar_data_br(aluno.get("data_nasc", "")),
            "Treinamento": aluno.get("Treinamento", "Intermediário"),
            "horas": aluno.get("horas", "4H")
        }
        if mostrar_coluna_data:
            item["data_matricula"] = formatar_data_br(aluno.get("data_matricula", ""))
        alunos_processados.append(item)

    # Resolução do CT
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

    # Imagens: logo do CT e assinatura do instrutor precisam virar URL absoluta ou data URI,
    # pois o HTML é renderizado a partir de string (sem base_url) via HTML(string=...).write_pdf()
    ct_logo_resolvida = _resolver_imagem(ct_logo)
    assinatura_resolvida = _resolver_imagem(instrutor.get("assinatura"))

    # Fatiamento em páginas de no máximo 20 alunos
    TAMANHO_PAGINA = 20
    if not alunos_processados:
        paginas_alunos = [[]]
    else:
        paginas_alunos = [
            alunos_processados[i : i + TAMANHO_PAGINA]
            for i in range(0, len(alunos_processados), TAMANHO_PAGINA)
        ]

    html_renderizado = template.render(
        LOGO_CT=ct_logo_resolvida,
        LOGO_CONECTA="https://vesgrrejcehseygchigh.supabase.co/storage/v1/object/public/logos/logo_conecta.png",
        EMPRESA=empresa.get("name"),
        ENDERECO=empresa.get("full_address"),
        CNPJ=empresa.get("cnpj"),
        CT_NOME=ct_nome,
        CT_CNPJ=ct_cnpj,
        CT_ENDERECO=ct_endereco,
        CT_TELEFONE=ct_telefone,
        NORMA=dados_turma.get("normativa"),
        CIDADE_DATA=dados_turma.get("cidade_data"),
        ASSINATURA_IMG=assinatura_resolvida,
        NOME_INSTRUTOR=instrutor.get("name"),
        DOC_INSTRUTOR=instrutor.get("cpf"),
        mostrar_coluna_rg=mostrar_coluna_rg,
        mostrar_coluna_nasc=mostrar_coluna_nasc,
        mostrar_coluna_data=mostrar_coluna_data,

        # Aqui enviamos a lista dividida por páginas
        paginas=paginas_alunos
    )

    return html_renderizado