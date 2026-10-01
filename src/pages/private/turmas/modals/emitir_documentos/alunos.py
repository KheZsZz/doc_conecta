def _v(val):
    """Normaliza vazio/None para string limpa."""
    if val is None:
        return ""
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "nat"):
        return ""
    return s


def alunos_para_atestado(matriculas: list, carga_padrao: str, nivel: str) -> list[dict]:
    """
    Monta lista para o atestado.
    Campos opcionais (rg, data_nasc, data_matricula) podem vir vazios;
    a modularidade por TURMA decide se a coluna aparece no PDF.
    """
    alunos = []
    for m in matriculas:
        info = m.get("alunos") or {}
        alunos.append({
            "nome": _v(info.get("name")),
            "rg": _v(info.get("rg")),
            "cpf": _v(info.get("cpf")),
            "data_nasc": _v(info.get("data_nasc")),
            "data_matricula": _v(m.get("data_treinamento")),
            "horas": _v(m.get("carga_horaria")) or carga_padrao,
            "Treinamento": nivel,
        })
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
            "horas": _v(m.get("carga_horaria")) or carga_padrao,
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
            "Assinatura": "_________________________________",
        }
        for m in matriculas
    ]
