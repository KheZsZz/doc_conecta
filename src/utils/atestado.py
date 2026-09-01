import os
from jinja2 import Environment, FileSystemLoader

def gerar_atestado_pdf_de_arquivo(dados_turma, alunos_matriculas, instrutor, empresa, ct=None, caminho_pasta_templates="src/templates"):
    env = Environment(loader=FileSystemLoader(caminho_pasta_templates))
    template = env.get_template("template_atestado_corrigido.html")

    # --- Resolução do CT ---
    if ct and isinstance(ct, dict):
        ct_nome        = ct.get("full_name") or ct.get("name") or ""
        ct_cnpj        = ct.get("cnpj") or ""
        ct_endereco    = ct.get("full_address") or ""
        ct_telefone    = ct.get("phone") or ""
        ct_logo        = ct.get("logo_url") or ""
    else:
        ct_nome        = empresa.get("name") or ""
        ct_cnpj        = empresa.get("cnpj") or ""
        ct_endereco    = empresa.get("full_address") or ""
        ct_telefone    = empresa.get("phone") or ""
        ct_logo        = ""

    # Dividir a lista de alunos em grupos de no máximo 30
    TAMANHO_PAGINA = 30
    paginas_alunos = []

    for i in range(0, len(alunos_matriculas), TAMANHO_PAGINA):
        grupo = alunos_matriculas[i : i + TAMANHO_PAGINA]
        
        # Avalia a necessidade de colunas individualmente para cada página/grupo
        mostrar_coluna_rg = any(a.get("rg") and str(a.get("rg")).strip() for a in grupo)
        mostrar_coluna_nasc = any(a.get("data_nasc") and str(a.get("data_nasc")).strip() for a in grupo)
        datas_unicas = set(a.get("data_matricula") for a in grupo if a.get("data_matricula"))
        mostrar_coluna_data = len(datas_unicas) > 1

        alunos_processados = []
        for aluno in grupo:
            item = {
                "nome": aluno.get("nome", "Sem Nome"),
                "rg": aluno.get("rg", ""),
                "cpf": aluno.get("cpf", ""),
                "data_nasc": aluno.get("data_nasc", ""),
                "horas": aluno.get("horas", "4H")
            }
            if mostrar_coluna_data:
                item["data_matricula"] = aluno.get("data_matricula", "")
            alunos_processados.append(item)

        paginas_alunos.append({
            "alunos": alunos_processados,
            "mostrar_coluna_rg": mostrar_coluna_rg,
            "mostrar_coluna_nasc": mostrar_coluna_nasc,
            "mostrar_coluna_data": mostrar_coluna_data
        })

    # Passa a lista 'paginas' para o template Jinja
    html_renderizado = template.render(
        LOGO_CT=ct_logo,
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
        ASSINATURA_IMG=instrutor.get("assinatura"),
        NOME_INSTRUTOR=instrutor.get("name"),
        DOC_INSTRUTOR=instrutor.get("cbo") or instrutor.get("cpf"),
        
        paginas=paginas_alunos
    )

    return html_renderizado