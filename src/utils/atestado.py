import os
from jinja2 import Environment, FileSystemLoader

def gerar_atestado_pdf_de_arquivo(dados_turma, alunos_matriculas, instrutor, empresa, caminho_pasta_templates="src/templates"):
    env = Environment(loader=FileSystemLoader(caminho_pasta_templates))
    template = env.get_template("template_atestado_corrigido.html")
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
            "data_nasc": aluno.get("data_nasc", ""),
            "horas": aluno.get("horas", "4H")
        }
        if mostrar_coluna_data:
            item["data_matricula"] = aluno.get("data_matricula", "")
        
        alunos_processados.append(item)

    html_renderizado = template.render(
        LOGO_TREINNAR=dados_turma.get("logo_treinnar"),
        LOGO_CONECTA=dados_turma.get("logo_conecta"),
        EMPRESA=empresa.get("name"),
        ENDERECO=empresa.get("full_address"),
        CNPJ=empresa.get("cnpj"),
        NORMA=dados_turma.get("normativa"),
        CIDADE_DATA=dados_turma.get("cidade_data"),
        ASSINATURA_IMG=instrutor.get("assinatura"),
        NOME_INSTRUTOR=instrutor.get("name"),
        DOC_INSTRUTOR=instrutor.get("cbo") or instrutor.get("cpf"),
        mostrar_coluna_rg=mostrar_coluna_rg,
        mostrar_coluna_nasc=mostrar_coluna_nasc,
        mostrar_coluna_data=mostrar_coluna_data,
        alunos=alunos_processados
    )

    return html_renderizado