def alunos_para_atestado(matriculas: list, carga_padrao: str, nivel: str) -> list[dict]:
    alunos = []
    for m in matriculas:
        info = m.get("alunos") or {}
        alunos.append({
            "nome": info.get("name", ""),
            "rg": info.get("rg", ""),
            "cpf": info.get("cpf", ""),
            "data_nasc": info.get("data_nasc", ""),
            "data_matricula": m.get("data_treinamento", ""),
            "horas": m.get("carga_horaria") or carga_padrao,
            "Treinamento": nivel,
        })
    return alunos


def alunos_para_certificado(
    matriculas: list, carga_padrao: str, incluir_nasc: bool = False
) -> list[dict]:
    alunos = []
    for m in matriculas:
        info = m.get("alunos") or {}
        item = {
            "name": info.get("name", ""),
            "cpf": info.get("cpf", ""),
            "rg": info.get("rg", ""),
            "horas": m.get("carga_horaria") or carga_padrao,
        }
        if incluir_nasc:
            item["data_nasc"] = info.get("data_nasc", "")
        alunos.append(item)
    return alunos


def alunos_para_lista_presenca(matriculas: list) -> list[dict]:
    return [
        {
            "Nome": (m.get("alunos") or {}).get("name", ""),
            "RG": (m.get("alunos") or {}).get("rg", ""),
            "CPF": (m.get("alunos") or {}).get("cpf", ""),
            "Assinatura": "_________________________________",
        }
        for m in matriculas
    ]