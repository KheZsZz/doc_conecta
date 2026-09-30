import re
import pandas as pd

MESES_PT = {
    1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril",
    5: "maio", 6: "junho", 7: "julho", 8: "agosto",
    9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro"
}

def extrair_cidade_do_endereco(endereco: str | None) -> str:
    if not endereco:
        return "Itapecerica da Serra"

    endereco_str = str(endereco)

    if "Itapecerica da Serra" in endereco_str:
        return "Itapecerica da Serra"
    if "Guarulhos" in endereco_str:
        return "Guarulhos"

    match = re.search(r'([^,-]+)(?:/|-)\s*[A-Z]{2}(?:\s|-|$)', endereco_str)
    if match:
        cidade_bruta = match.group(1).strip()
        return cidade_bruta.split(',')[-1].strip()

    return "Itapecerica da Serra"


def formatar_data_extenso(data_str, cidade: str = "Itapecerica da Serra") -> str:
    if not data_str:
        return f"{cidade}, data não informada."

    try:
        if "T" in str(data_str):
            data_str = str(data_str).split("T")[0]

        dt = pd.to_datetime(data_str)
        return f"{cidade}, {dt.day} de {MESES_PT[dt.month]} de {dt.year}."
    except Exception:
        return f"{cidade}, {data_str}."