"""Gera lista de presença no layout padrão Conecta (.xlsx)."""
from __future__ import annotations

import io
import re
from datetime import datetime
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


def _fmt_cnpj(val) -> str:
    d = re.sub(r"\D", "", str(val or ""))
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    return str(val or "").strip()


def _fmt_cpf(val) -> str:
    d = re.sub(r"\D", "", str(val or ""))
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    return str(val or "").strip()


def _fmt_data_br(val) -> str:
    if not val:
        return ""
    if hasattr(val, "strftime"):
        try:
            return val.strftime("%d/%m/%Y")
        except Exception:
            pass
    s = str(val).split("T")[0][:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return str(val).strip()


def _thin() -> Border:
    s = Side(style="thin", color="FF718096")
    return Border(left=s, right=s, top=s, bottom=s)


def gerar_lista_presenca_xlsx(
    *,
    alunos: list[dict[str, Any]],
    empresa: dict | None = None,
    data_treinamento: str = "",
    responsavel_turma: dict | None = None,
    min_linhas_alunos: int = 30,
) -> bytes:
    """Monta o Excel no layout LISTA DE PRESENÇA (modelo Conecta).

    alunos: lista com chaves Nome/nome, CPF/cpf, Unidade/unidade (opcional).
    empresa: clients (name, cnpj, full_address, responsavel, phone, email).
    responsavel_turma: opcional; se omitido, usa dados da empresa.
    """
    empresa = empresa or {}
    resp = responsavel_turma or {}

    razao = (empresa.get("name") or empresa.get("full_name") or "").strip()
    cnpj = _fmt_cnpj(empresa.get("cnpj"))
    endereco = (empresa.get("full_address") or empresa.get("endereco") or "").strip()
    data_br = _fmt_data_br(data_treinamento)

    resp_nome = (resp.get("nome") or resp.get("name") or empresa.get("responsavel") or "").strip()
    resp_cpf = _fmt_cpf(resp.get("cpf") or "")
    resp_tel = (resp.get("telefone") or resp.get("phone") or empresa.get("phone") or "").strip()
    resp_email = (resp.get("email") or empresa.get("email") or "").strip()

    # normaliza alunos
    rows: list[dict] = []
    for a in alunos or []:
        nome = (a.get("Nome") or a.get("nome") or a.get("name") or "").strip()
        if not nome:
            continue
        cpf = _fmt_cpf(a.get("CPF") or a.get("cpf") or "")
        unid = (a.get("Unidade") or a.get("unidade") or "").strip()
        # coluna UNIDADE / CNPJ: prioriza unidade; se vazio, CNPJ da empresa
        unid_cnpj = unid or cnpj
        rows.append({"nome": nome, "cpf": cpf, "unid": unid_cnpj})

    wb = Workbook()
    ws = wb.active
    ws.title = "LISTA"

    # larguras
    widths = {"A": 8, "B": 44, "C": 24, "D": 22, "E": 38}
    for col, w in widths.items():
        ws.column_dimensions[col].width = w

    fill_title = PatternFill("solid", fgColor="FF1B365D")
    fill_label = PatternFill("solid", fgColor="FFEDF2F7")
    fill_white = PatternFill("solid", fgColor="FFFFFFFF")
    fill_section = PatternFill("solid", fgColor="FF2C5282")
    fill_header_alunos = PatternFill("solid", fgColor="FF1B365D")

    font_title = Font(name="Calibri", bold=True, size=14, color="FFFFFFFF")
    font_label = Font(name="Calibri", bold=True, size=10, color="FF1A202C")
    font_val = Font(name="Calibri", size=10, color="FF1A202C")
    font_section = Font(name="Calibri", bold=True, size=11, color="FFFFFFFF")
    font_header = Font(name="Calibri", bold=True, size=10, color="FFFFFFFF")
    font_header_gray = Font(name="Calibri", bold=True, size=10, color="FF1A202C")
    font_note = Font(name="Calibri", size=9, color="FF2D3748", italic=True)
    font_total = Font(name="Calibri", bold=True, size=10)

    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left = Alignment(horizontal="left", vertical="center", wrap_text=True)
    border = _thin()

    # Título
    ws.merge_cells("A1:E1")
    c = ws["A1"]
    c.value = "LISTA DE PRESENÇA"
    c.font = font_title
    c.fill = fill_title
    c.alignment = center
    ws.row_dimensions[1].height = 45
    for col in range(1, 6):
        ws.cell(1, col).fill = fill_title
        ws.cell(1, col).border = border

    # Empresa / CNPJ
    ws["A2"] = "Empresa:"
    ws["A2"].font = font_label
    ws["A2"].fill = fill_label
    ws["A2"].alignment = center
    ws["A2"].border = border
    ws.merge_cells("B2:C2")
    ws["B2"] = razao
    ws["B2"].font = font_val
    ws["B2"].fill = fill_white
    ws["B2"].alignment = left
    ws["B2"].border = border
    ws["C2"].border = border
    ws["C2"].fill = fill_white
    ws["D2"] = "CNPJ:"
    ws["D2"].font = font_label
    ws["D2"].fill = fill_label
    ws["D2"].alignment = center
    ws["D2"].border = border
    ws["E2"] = cnpj
    ws["E2"].font = font_val
    ws["E2"].fill = fill_white
    ws["E2"].alignment = left
    ws["E2"].border = border
    ws.row_dimensions[2].height = 20

    # Endereço / Data
    ws["A3"] = "Endereço Completo:"
    ws["A3"].font = font_label
    ws["A3"].fill = fill_label
    ws["A3"].alignment = center
    ws["A3"].border = border
    ws.merge_cells("B3:C3")
    ws["B3"] = endereco
    ws["B3"].font = font_val
    ws["B3"].fill = fill_white
    ws["B3"].alignment = left
    ws["B3"].border = border
    ws["C3"].border = border
    ws["C3"].fill = fill_white
    ws["D3"] = "Data do Treinamento:"
    ws["D3"].font = font_label
    ws["D3"].fill = fill_label
    ws["D3"].alignment = center
    ws["D3"].border = border
    ws["E3"] = data_br
    ws["E3"].font = font_val
    ws["E3"].fill = fill_white
    ws["E3"].alignment = left
    ws["E3"].border = border
    ws.row_dimensions[3].height = 20

    # Texto legal
    ws.merge_cells("A4:E4")
    ws["A4"] = (
        "A assinatura nesta lista implica ciência e concordância do participante "
        "em cumprir todas as orientações de segurança da Conecta Treinamentos, "
        "bem como utilizar corretamente os EPIs fornecidos durante o treinamento."
    )
    ws["A4"].font = font_note
    ws["A4"].alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
    for col in range(1, 6):
        ws.cell(4, col).border = border
    ws.row_dimensions[4].height = 28

    # Seção responsável
    ws.merge_cells("A6:E6")
    ws["A6"] = "DADOS DO RESPONSÁVEL DA TURMA"
    ws["A6"].font = font_section
    ws["A6"].fill = fill_section
    ws["A6"].alignment = left
    for col in range(1, 6):
        ws.cell(6, col).fill = fill_section
    ws.row_dimensions[6].height = 22

    headers_resp = ["Nº", "NOME COMPLETO", "CPF", "TELEFONE", "E-MAIL"]
    for i, h in enumerate(headers_resp, start=1):
        cell = ws.cell(7, i, h)
        cell.font = font_header_gray
        cell.fill = fill_label
        cell.alignment = center if i in (1, 3) else left
        cell.border = border
    ws.row_dimensions[7].height = 20

    vals_resp = ["-", resp_nome, resp_cpf, resp_tel, resp_email]
    aligns_resp = [center, left, center, left, left]
    for i, (v, al) in enumerate(zip(vals_resp, aligns_resp), start=1):
        cell = ws.cell(8, i, v)
        cell.font = font_val
        cell.fill = fill_white
        cell.alignment = al
        cell.border = border
    ws.row_dimensions[8].height = 20

    # Seção alunos
    ws.merge_cells("A10:E10")
    ws["A10"] = "DADOS DOS ALUNOS"
    ws["A10"].font = font_section
    ws["A10"].fill = fill_section
    ws["A10"].alignment = left
    for col in range(1, 6):
        ws.cell(10, col).fill = fill_section
    ws.row_dimensions[10].height = 22

    headers_al = [
        "Nº",
        "NOME COMPLETO",
        "CPF",
        "UNIDADE / CNPJ",
        "ASSINATURA (SOMENTE NO DIA DO TREINAMENTO)",
    ]
    for i, h in enumerate(headers_al, start=1):
        cell = ws.cell(11, i, h)
        cell.font = font_header
        cell.fill = fill_header_alunos
        cell.alignment = center
        cell.border = border
    ws.row_dimensions[11].height = 24

    n_linhas = max(min_linhas_alunos, len(rows))
    first_aluno = 12
    for i in range(n_linhas):
        r = first_aluno + i
        nome = rows[i]["nome"] if i < len(rows) else ""
        cpf = rows[i]["cpf"] if i < len(rows) else ""
        unid = rows[i]["unid"] if i < len(rows) else ""
        vals = [i + 1, nome, cpf, unid, ""]
        aligns = [center, left, center, center, center]
        for col, (v, al) in enumerate(zip(vals, aligns), start=1):
            cell = ws.cell(r, col, v)
            cell.font = font_val
            cell.fill = fill_white
            cell.alignment = al
            cell.border = border
        ws.row_dimensions[r].height = 22

    total_row = first_aluno + n_linhas
    ws.cell(total_row, 1, "TOTAL").font = font_total
    ws.cell(total_row, 1).alignment = center
    ws.cell(total_row, 1).border = border
    # fórmula conta nomes preenchidos
    last_aluno = total_row - 1
    ws.cell(total_row, 2, f"=COUNTA(B{first_aluno}:B{last_aluno})")
    ws.cell(total_row, 2).font = font_total
    ws.cell(total_row, 2).alignment = center
    ws.cell(total_row, 2).border = border
    for col in range(3, 6):
        ws.cell(total_row, col).border = border
    ws.merge_cells(start_row=total_row, start_column=3, end_row=total_row, end_column=5)
    ws.row_dimensions[total_row].height = 20

    ws.print_title_rows = "1:11"
    ws.page_setup.orientation = "portrait"
    ws.page_setup.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.page_margins.left = 0.4
    ws.page_margins.right = 0.4
    ws.page_margins.top = 0.5
    ws.page_margins.bottom = 0.5

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
