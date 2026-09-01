import os
from datetime import datetime
from jinja2 import Environment, FileSystemLoader

def formatar_data_br(data_str):
    """Auxiliar para formatar datas no padrão DD/MM/YYYY se necessário."""
    if not data_str:
        return ""
    data_str_limpa = str(data_str).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(data_str_limpa[:10], fmt.split()[0])
            return dt.strftime("%d/%m/%Y")
        except ValueError:
            continue
    return data_str_limpa

def gerar_certificado_empresa_pdf(aluno, dados_turma, instrutor, empresa, resp_tecnico=None, caminho_pasta_templates="src/templates", nome_template="template_certificado.html"):
    env = Environment(loader=FileSystemLoader(caminho_pasta_templates))
    template = env.get_template(nome_template)

    # Tratamento dos dados do Responsável Técnico (opcional)
    resp_nome = resp_tecnico.get("name") or resp_tecnico.get("nome") if resp_tecnico else None
    resp_cpf = resp_tecnico.get("cpf") if resp_tecnico else None
    resp_assinatura = resp_tecnico.get("assinatura") if resp_tecnico else None

    html_renderizado = template.render(
        # Identificação do Aluno
        NOME_ALUNO=aluno.get("nome") or aluno.get("name", "Sem Nome"),

        # Imagem de fundo e layout
        IMAGEM_FUNDO=dados_turma.get("imagem_fundo", ""),

        # Dados da Empresa contratante
        EMPRESA=empresa.get("name") or empresa.get("nome", ""),
        ENDERECO_EMPRESA=empresa.get("full_address") or empresa.get("endereco", ""),
        CNPJ_EMPRESA=empresa.get("cnpj", ""),

        # Detalhes do Treinamento
        NIVEL=dados_turma.get("nivel", "Intermediário"),
        MODALIDADE=dados_turma.get("modalidade", "Presencial"),
        CARGA_HORARIA=aluno.get("horas") or dados_turma.get("carga_horaria", "4H"),
        CIDADE_DATA=dados_turma.get("cidade_data", ""),

        # Dados do Instrutor
        NOME_INSTRUTOR=instrutor.get("name") or instrutor.get("nome", ""),
        CPF_INSTRUTOR=instrutor.get("cpf", ""),
        ASSINATURA_INSTRUTOR=instrutor.get("assinatura", ""),

        # Dados do Responsável Técnico (se houver)
        RESP_TECNICO=resp_nome,
        CPF_RESP=resp_cpf,
        ASSINATURA_RESP_TECNICO=resp_assinatura
    )

    return html_renderizado