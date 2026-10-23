def _v(val):
    """Normaliza vazio/None para string limpa."""
    if val is None:
        return ""
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "nat"):
        return ""
    return s


def _unidade_da_matricula(m: dict, unidade_padrao: str = "") -> str:
    """
    Unidade do aluno na matrícula:
    1) clients.sigla (via client_id da matrícula)
    2) clients.name se sigla vazia
    3) unidade padrão da turma/empresa
    """
    cli = m.get("clients") or {}
    unid = _v(cli.get("sigla"))
    if unid:
        return unid
    # fallback: nome curto da unidade/empresa vinculada à matrícula
    nome_cli = _v(cli.get("name"))
    if nome_cli:
        return nome_cli
    return _v(unidade_padrao)


def alunos_para_atestado(
    matriculas: list,
    carga_padrao: str,
    nivel: str,
    unidade_padrao: str = "",
) -> list[dict]:
    """
    Monta lista para o atestado.
    Campos opcionais (rg, data_nasc, data_matricula, unidade) podem vir vazios;
    a modularidade por TURMA decide se a coluna aparece no PDF.
    """
    alunos = []
    for m in matriculas:
        info = m.get("alunos") or {}
        alunos.append(
            {
                "nome": _v(info.get("name")),
                "rg": _v(info.get("rg")),
                "cpf": _v(info.get("cpf")),
                "data_nasc": _v(info.get("data_nasc")),
                "data_matricula": _v(m.get("data_treinamento")),
                "horas": _v(m.get("carga_horaria")) or carga_padrao,
                "Treinamento": nivel,
                "unidade": _unidade_da_matricula(m, unidade_padrao),
            }
        )
    return alunos


def alunos_para_certificado(
    matriculas: list, carga_padrao: str, incluir_nasc: bool = False
) -> list[dict]:
    """
    Monta lista para certificados individuais.
    RG / CPF / data_nasc vazios nao aparecem no template do certificado.
    """
    alunos = []
    for m in matriculas:
        info = m.get("alunos") or {}
        item = {
            "name": _v(info.get("name")),
            "cpf": _v(info.get("cpf")),
            "rg": _v(info.get("rg")),
            "re": _v(info.get("re")),
            "horas": _v(m.get("carga_horaria")) or carga_padrao,
            "unidade": _unidade_da_matricula(m),
            "aluno_id": (info.get("id") or m.get("aluno_id") or ""),
        }
        if incluir_nasc:
            item["data_nasc"] = _v(info.get("data_nasc"))
        alunos.append(item)
    return alunos


def alunos_para_lista_presenca(matriculas: list) -> list[dict]:
    return [
        {
            "Nome": _v((m.get("alunos") or {}).get("name")),
            "RG": _v((m.get("alunos") or {}).get("rg")),
            "CPF": _v((m.get("alunos") or {}).get("cpf")),
            "Unidade": _unidade_da_matricula(m),
            "Assinatura": "_________________________________",
        }
        for m in matriculas
    ]
