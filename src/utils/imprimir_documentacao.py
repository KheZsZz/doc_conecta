"""Gera PDFs consolidados do dia por CT (certificados, atestados, etc.)."""
from __future__ import annotations

import io
from datetime import date, datetime
from typing import Any

from pypdf import PdfReader, PdfWriter

from src.config.database import supabase
from src.pages.private.turmas.helpers import formatar_data_extenso
from src.pages.private.turmas.modals.emitir_documentos.alunos import (
    alunos_para_atestado,
    alunos_para_certificado,
)
from src.pages.private.turmas.modals.emitir_documentos.data import (
    fetch_ct,
    fetch_curso,
    fetch_empresa,
    fetch_instrutor,
    fetch_matriculas,
    fetch_responsaveis,
    resolver_cidade,
)
from src.utils.atestado import gerar_atestado_pdf_de_arquivo
from src.utils.carteirinha import gerar_carteirinhas_pdf
from src.utils.certificado import gerar_certificados_pdf
from src.utils.certificado_empresa import gerar_certificado_empresa_pdf


def _merge_pdfs(lista: list[bytes]) -> bytes:
    writer = PdfWriter()
    for pdf in lista:
        if not pdf:
            continue
        reader = PdfReader(io.BytesIO(pdf))
        for page in reader.pages:
            writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def listar_cts() -> list[dict]:
    try:
        res = supabase.table("cts").select("id, name, full_name, full_address").order("name").execute()
        return res.data if res and isinstance(res.data, list) else []
    except Exception:
        return []


def turmas_do_ct_na_data(ct_id: str, data_ref: date | str) -> list[dict]:
    di = data_ref.isoformat() if hasattr(data_ref, "isoformat") else str(data_ref)[:10]
    try:
        res = (
            supabase.table("turmas")
            .select("*")
            .eq("ct_id", ct_id)
            .eq("data_treinamento", di)
            .order("titulo")
            .execute()
        )
        return res.data if res and isinstance(res.data, list) else []
    except Exception:
        return []


def responsavel_padrao() -> dict:
    resps = fetch_responsaveis()
    ativos = [r for r in resps if r.get("is_active", True)]
    if not ativos:
        return {
            "nome": "Cristiano Reis",
            "cpf": "214.135.358-01",
            "re": "0075191",
            "formacao": "",
            "assinatura_url": None,
        }
    escolhido = next((r for r in ativos if r.get("is_default")), ativos[0])
    return {
        "nome": escolhido.get("nome") or "",
        "cpf": escolhido.get("cpf") or "",
        "re": (escolhido.get("re") or "").strip(),
        "formacao": (escolhido.get("formacao") or "").strip(),
        "assinatura_url": escolhido.get("assinatura_url"),
    }


def _montar_turma_cert(turma: dict, curso: dict, dados_resp: dict) -> dict:
    return {
        "modalidade": (turma.get("modalidade") or "").strip() or "Presencial",
        "nivel": (turma.get("nivel") or "").strip() or "Formação",
        "carga_horaria": (turma.get("carga_horaria") or "").strip() or "8 Horas",
        "resp_tecnico": dados_resp.get("nome", ""),
        "cpf_resp_tecnico": dados_resp.get("cpf", ""),
        "re_resp_tecnico": dados_resp.get("re", ""),
        "formacao_resp_tecnico": dados_resp.get("formacao", ""),
        "assinatura_resp_url": dados_resp.get("assinatura_url"),
        "curso_nome": curso.get("name") or "Treinamento",
        "curso_sigla": (curso.get("sigla") or "").strip().upper(),
        "dizeres_certificado_empresa": curso.get("dizeres_certificado_empresa", ""),
        "dizeres_certificado_aluno": curso.get("dizeres_certificado_aluno", ""),
    }


def gerar_pdf_tipo(
    *,
    tipo: str,
    turmas: list[dict],
    ct: dict,
    dados_resp: dict | None = None,
) -> tuple[bytes | None, list[str], list[str]]:
    """
    tipo: cert_alunos | cert_empresa | atestado | carteirinhas
    Retorna (pdf_bytes|None, avisos, erros)
    """
    dados_resp = dados_resp or responsavel_padrao()
    pdfs: list[bytes] = []
    avisos: list[str] = []
    erros: list[str] = []

    for turma in turmas:
        titulo = turma.get("titulo") or "Turma"
        tid = turma.get("id")
        curso = fetch_curso(turma.get("curso_id"))
        instrutor = fetch_instrutor(turma.get("instrutor_id"))
        empresa = fetch_empresa(turma.get("client_id"))
        matriculas = fetch_matriculas(tid)

        if not matriculas:
            avisos.append(f"{titulo}: sem alunos — ignorada.")
            continue

        data_t = str(turma.get("data_treinamento") or "")[:10]
        cidade = resolver_cidade(turma.get("ct_id"), turma)
        cidade_data = formatar_data_extenso(data_t, cidade=cidade)
        carga = (turma.get("carga_horaria") or "").strip() or "8 Horas"
        nivel = (turma.get("nivel") or "").strip() or "Formação"
        normativa = turma.get("normativa") or curso.get("normativa") or ""
        turma_cert = _montar_turma_cert(turma, curso, dados_resp)
        alunos_cert = alunos_para_certificado(matriculas, carga, incluir_nasc=True)

        try:
            if tipo == "cert_alunos":
                pdf = gerar_certificados_pdf(
                    alunos_matriculas=alunos_cert,
                    turma=turma_cert,
                    instrutor=instrutor,
                    empresa=empresa,
                    ct=ct or None,
                    normativa=normativa,
                    cidade_data=cidade_data,
                )
                pdfs.append(pdf)

            elif tipo == "cert_empresa":
                pdf = gerar_certificado_empresa_pdf(
                    turma=turma_cert,
                    instrutor=instrutor,
                    empresa=empresa,
                    ct=ct or None,
                    alunos=alunos_cert,
                    normativa=normativa,
                    cidade_data=cidade_data,
                )
                pdfs.append(pdf)

            elif tipo == "atestado":
                exige = bool(curso.get("exige_atestado", True))
                if not exige:
                    avisos.append(
                        f"{titulo}: curso não exige atestado — ignorada."
                    )
                    continue
                alunos_atest = alunos_para_atestado(matriculas, carga, nivel)
                pdf = gerar_atestado_pdf_de_arquivo(
                    alunos=alunos_atest,
                    turma=turma,
                    empresa=empresa,
                    curso=curso or None,
                    instrutor=instrutor,
                    ct=ct or None,
                    cidade_data_formatada=cidade_data,
                )
                pdfs.append(pdf)

            elif tipo == "carteirinhas":
                pdf = gerar_carteirinhas_pdf(
                    alunos=alunos_cert,
                    curso_nome=curso.get("name") or "Treinamento",
                    carga_horaria=carga,
                    data_conclusao=data_t,
                    instrutor=instrutor,
                    ct=ct or None,
                )
                pdfs.append(pdf)
            else:
                erros.append(f"Tipo desconhecido: {tipo}")
        except Exception as e:
            erros.append(f"{titulo}: {e}")

    if not pdfs:
        return None, avisos, erros

    try:
        return _merge_pdfs(pdfs), avisos, erros
    except Exception as e:
        return None, avisos, erros + [f"Falha ao unir PDFs: {e}"]
