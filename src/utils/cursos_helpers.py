"""Helpers leves sobre cursos (sem dependências de PDF)."""
from __future__ import annotations

import re


def eh_curso_bombeiro(curso_nome: str = "", curso_sigla: str = "") -> bool:
    """True quando o curso é de Bombeiro Civil / Bombeiro Profissional Civil."""
    t = f"{curso_nome or ''} {curso_sigla or ''}".lower()
    t = re.sub(r"\s+", " ", t)
    return any(
        k in t
        for k in (
            "bombeiro",
            "bombeiros",
            "bc civil",
            "bombeiro civil",
            "bombeiro profissional",
        )
    ) or (curso_sigla or "").strip().upper() in ("BC", "BPC", "BPCIVIL")


def somente_digitos(valor: str | None) -> str:
    return "".join(ch for ch in (valor or "") if ch.isdigit())


def cpf_valido(cpf: str | None) -> bool:
    """Valida CPF pelos dígitos verificadores."""
    c = somente_digitos(cpf)
    if len(c) != 11 or c == c[0] * 11:
        return False
    for n in (9, 10):
        soma = sum(int(c[i]) * ((n + 1) - i) for i in range(n))
        dv = (soma * 10) % 11
        if dv == 10:
            dv = 0
        if dv != int(c[n]):
            return False
    return True


def formatar_cpf(cpf: str | None) -> str:
    c = somente_digitos(cpf)
    if len(c) != 11:
        return cpf or ""
    return f"{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}"
