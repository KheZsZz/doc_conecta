import os
import base64
import re
from datetime import datetime

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS

from src.utils.pdf_assets import get_template, html_para_pdf, resolver_imagem

# Logo Conecta (rodapé do atestado) — sem fundo
_LOGO_CONECTA = (
    "https://vesgrrejcehseygchigh.supabase.co/storage/v1/object/public/logos/"
    "logo_conecta_sem_fundo%20(2).png"
)


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


def _cpf_somente_digitos(val) -> str:
    return re.sub(r"\D", "", str(val or ""))


def formatar_cpf_instrutor(instrutor: dict | None) -> str:
    if not instrutor:
        return ""
    digitos = _cpf_somente_digitos(instrutor.get("cpf"))
    if not digitos:
        return ""
    if len(digitos) < 11:
        digitos = digitos.zfill(11)
    if len(digitos) != 11:
        return ""
    return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"


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

    template = get_template(caminho_pasta_templates, "template_atestado_corrigido.html")

    mostrar_coluna_rg = any(_tem_valor(a.get("rg")) for a in alunos_lista)
    mostrar_coluna_nasc = any(_tem_valor(a.get("data_nasc")) for a in alunos_lista)

    datas_unicas = {
        formatar_data_br(a.get("data_matricula") or a.get("data_treinamento"))
        for a in alunos_lista
    }
    datas_unicas.discard("")
    mostrar_coluna_data = len(datas_unicas) > 1

    # Unidade desativada por enquanto
    mostrar_coluna_unidade = False

    carga_turma = (turma.get("carga_horaria") or "").strip() or "8 Horas"
    nivel_turma = (
        (turma.get("nivel") or turma.get("nivel_turma") or "").strip() or "Formação"
    )

    # Template espera: aluno.nome, aluno.cpf, aluno.Treinamento, aluno.horas
    alunos_processados = []
    for a in alunos_lista:
        nome = (a.get("nome") or a.get("name") or "").strip()
        horas = a.get("horas") or a.get("carga_horaria") or carga_turma or "8 Horas"
        treinamento = (
            a.get("Treinamento")
            or a.get("treinamento")
            or a.get("nivel")
            or nivel_turma
        )
        alunos_processados.append(
            {
                "nome": nome,
                "name": nome,
                "cpf": a.get("cpf") or "",
                "rg": a.get("rg") or "",
                "data_nasc": formatar_data_br(
                    a.get("data_nasc") or a.get("data_nascimento")
                ),
                "data_matricula": formatar_data_br(
                    a.get("data_matricula") or a.get("data_treinamento")
                ),
                "horas": horas,
                "carga_horaria": horas,
                "Treinamento": treinamento,
                "unidade": a.get("unidade") or "",
            }
        )

    if ct:
        ct_nome = ct.get("name") or ct.get("full_name") or ""
        ct_cnpj = ct.get("cnpj") or ""
        ct_endereco = ct.get("full_address") or ct.get("endereco") or ""
        ct_telefone = ct.get("phone") or ""
        ct_logo = ct.get("logo_url") or ""
    else:
        ct_nome = empresa.get("name") or ""
        ct_cnpj = empresa.get("cnpj") or ""
        ct_endereco = empresa.get("full_address") or ""
        ct_telefone = empresa.get("phone") or ""
        ct_logo = ""

    ct_logo_resolvida = resolver_imagem(ct_logo)
    assinatura_src = (
        instrutor.get("assinatura")
        or instrutor.get("assinatura_url")
        or instrutor.get("signature_url")
        or ""
    )
    assinatura_resolvida = resolver_imagem(assinatura_src)

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

    cpf_instrutor = formatar_cpf_instrutor(instrutor)
    re_instrutor = (instrutor.get("re") or "").strip()
    formacao_instrutor = (instrutor.get("formacao") or "").strip()

    html_renderizado = template.render(
        LOGO_CT=ct_logo_resolvida,
        LOGO_CONECTA=resolver_imagem(_LOGO_CONECTA) or _LOGO_CONECTA,
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
        CARGA_HORARIA=carga_turma,
        ASSINATURA_IMG=assinatura_resolvida,
        NOME_INSTRUTOR=instrutor.get("name") or "",
        FORMACAO_INSTRUTOR=formacao_instrutor,
        DOC_INSTRUTOR=cpf_instrutor,
        RE_INSTRUTOR=re_instrutor,
        mostrar_coluna_rg=mostrar_coluna_rg,
        mostrar_coluna_nasc=mostrar_coluna_nasc,
        mostrar_coluna_data=mostrar_coluna_data,
        mostrar_coluna_unidade=mostrar_coluna_unidade,
        paginas=paginas_alunos,
    )

    pdf_bytes = html_para_pdf(html_renderizado, landscape=False)
    return pdf_bytes
