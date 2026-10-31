import unicodedata


def _v(val):
    """Normaliza vazio/None para string limpa."""
    if val is None:
        return ""
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "nat"):
        return ""
    return s


def _chave_ordenacao_nome(nome: str) -> str:
    """Chave estável para ordem alfabética (sem acento, casefold)."""
    s = (nome or "").strip().casefold()
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def _unidade_da_matricula(m: dict, unidade_padrao: str = "") -> str:
    cli = m.get("clients") or {}
    unid = _v(cli.get("sigla"))
    if unid:
        return unid
    nome_cli = _v(cli.get("name"))
    if nome_cli:
        return nome_cli
    return _v(unidade_padrao)


def _info_aluno(m: dict) -> dict:
    """Extrai dados do aluno da matrícula (join ou campos planos)."""
    info = m.get("alunos") or {}
    if not isinstance(info, dict):
        info = {}
    # fallback se o join não veio e os campos estão na própria matrícula
    if not info.get("name") and not info.get("nome"):
        info = {
            "id": m.get("aluno_id") or info.get("id"),
            "name": m.get("aluno_nome") or m.get("name") or m.get("nome") or "",
            "cpf": m.get("cpf") or info.get("cpf") or "",
            "rg": m.get("rg") or info.get("rg") or "",
            "data_nasc": m.get("data_nasc") or info.get("data_nasc") or "",
            "re": m.get("re") or info.get("re") or "",
        }
    return info


def alunos_para_atestado(
    matriculas: list,
    carga_padrao: str,
    nivel: str,
    unidade_padrao: str = "",
) -> list[dict]:
    """Monta lista para o template do atestado.

    Carga horária SEMPRE da turma (carga_padrao).
    Chaves alinhadas ao template: nome, Treinamento, horas (+ aliases).
    Lista SEMPRE em ordem alfabética pelo nome (lista inteira, antes de paginar).
    Usado por: documentação completa, atestado individual, pacote período,
    imprimir documentação.
    """
    alunos = []
    nivel_limpo = _v(nivel) or "Formação"
    carga = _v(carga_padrao) or "8 Horas"

    for m in matriculas or []:
        info = _info_aluno(m)
        nome = _v(info.get("name")) or _v(info.get("nome"))
        alunos.append(
            {
                # template: aluno.nome
                "nome": nome,
                # aliases / compat
                "name": nome,
                "rg": _v(info.get("rg")),
                "cpf": _v(info.get("cpf")),
                "data_nasc": _v(info.get("data_nasc")),
                "data_matricula": _v(m.get("data_treinamento")),
                # template: aluno.horas
                "horas": carga,
                "carga_horaria": carga,
                # template: aluno.Treinamento
                "Treinamento": nivel_limpo,
                "treinamento": nivel_limpo,
                "nivel": nivel_limpo,
                "unidade": "",
                "re": _v(info.get("re")),
            }
        )

    # Ordem alfabética da lista COMPLETA (não por página)
    alunos.sort(key=lambda a: _chave_ordenacao_nome(a.get("nome") or a.get("name") or ""))
    return alunos


def alunos_para_certificado(
    matriculas: list, carga_padrao: str, incluir_nasc: bool = False
) -> list[dict]:
    """Carga horária SEMPRE da turma (carga_padrao), nunca da matrícula/aluno."""
    alunos = []
    carga = _v(carga_padrao) or "8 Horas"
    for m in matriculas or []:
        info = _info_aluno(m)
        nome = _v(info.get("name")) or _v(info.get("nome"))
        item = {
            "name": nome,
            "nome": nome,
            "cpf": _v(info.get("cpf")),
            "rg": _v(info.get("rg")),
            "re": _v(info.get("re")),
            "horas": carga,
            "unidade": _unidade_da_matricula(m),
            "aluno_id": (info.get("id") or m.get("aluno_id") or ""),
        }
        if incluir_nasc:
            item["data_nasc"] = _v(info.get("data_nasc"))
        alunos.append(item)
    return alunos


def alunos_para_lista_presenca(matriculas: list) -> list[dict]:
    rows = [
        {
            "Nome": _v(_info_aluno(m).get("name")) or _v(_info_aluno(m).get("nome")),
            "RG": _v(_info_aluno(m).get("rg")),
            "CPF": _v(_info_aluno(m).get("cpf")),
            "Unidade": _unidade_da_matricula(m),
            "Assinatura": "_________________________________",
        }
        for m in (matriculas or [])
    ]
    rows.sort(key=lambda r: _chave_ordenacao_nome(r.get("Nome") or ""))
    return rows
