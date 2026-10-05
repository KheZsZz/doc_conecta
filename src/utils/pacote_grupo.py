"""Listagem e geracao de pacote de documentos por grupo empresarial + periodo."""
from __future__ import annotations

import io
import re
import zipfile
from datetime import date, datetime
from typing import Any

import pandas as pd

from src.config.database import supabase
from src.pages.private.turmas.helpers import formatar_data_extenso
from src.pages.private.turmas.modals.emitir_documentos.alunos import (
    alunos_para_atestado,
    alunos_para_certificado,
    alunos_para_lista_presenca,
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
from src.utils.certificado import gerar_certificados_pdf_zip
from src.utils.certificado_empresa import gerar_certificado_empresa_pdf


def _slug(texto: str) -> str:
    s = (texto or "item").strip().replace(" ", "_")
    return "".join(c for c in s if c.isalnum() or c in ("_", "-"))[:80] or "item"


def listar_grupos() -> list[dict]:
    try:
        res = (
            supabase.table("grupos_empresariais")
            .select("*")
            .order("nome")
            .execute()
        )
        return res.data if res and isinstance(res.data, list) else []
    except Exception:
        return []


def empresas_do_grupo(grupo_id: str) -> list[dict]:
    try:
        res = (
            supabase.table("clients")
            .select("id, name, cnpj, sigla, full_address")
            .eq("grupo_id", grupo_id)
            .order("name")
            .execute()
        )
        return res.data if res and isinstance(res.data, list) else []
    except Exception:
        return []


def turmas_do_periodo(
    client_ids: list[str],
    data_inicio: date | str,
    data_fim: date | str,
) -> list[dict]:
    if not client_ids:
        return []

    di = data_inicio.isoformat() if hasattr(data_inicio, "isoformat") else str(data_inicio)[:10]
    df = data_fim.isoformat() if hasattr(data_fim, "isoformat") else str(data_fim)[:10]

    try:
        res = (
            supabase.table("turmas")
            .select("*")
            .in_("client_id", client_ids)
            .gte("data_treinamento", di)
            .lte("data_treinamento", df)
            .order("data_treinamento")
            .execute()
        )
        return res.data if res and isinstance(res.data, list) else []
    except Exception:
        return []


def responsavel_padrao() -> dict:
    resps = fetch_responsaveis()
    ativos = [r for r in resps if r.get("is_active", True)]
    if not ativos:
        return {}
    for r in ativos:
        if r.get("is_default"):
            return {
                "nome": r.get("nome") or "",
                "cpf": r.get("cpf") or "",
                "re": r.get("re") or "",
                "assinatura_url": r.get("assinatura_url"),
            }
    r = ativos[0]
    return {
        "nome": r.get("nome") or "",
        "cpf": r.get("cpf") or "",
        "re": r.get("re") or "",
        "assinatura_url": r.get("assinatura_url"),
    }


def _fmt_data_br(val) -> str:
    if not val:
        return ""
    s = str(val)[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return s


def gerar_pacote_grupo(
    *,
    grupo_nome: str,
    turmas: list[dict],
    empresas_por_id: dict[str, dict],
    dados_resp: dict | None = None,
    incluir_atestado: bool = True,
    incluir_cert_empresa: bool = True,
    incluir_cert_alunos: bool = True,
    incluir_carteirinhas: bool = True,
    incluir_lista: bool = True,
) -> tuple[bytes, dict[str, Any]]:
    """
    Gera ZIP com pasta por turma.
    Retorna (zip_bytes, meta) onde meta tem gerados/erros/resumo.
    """
    dados_resp = dados_resp or responsavel_padrao()
    zip_buf = io.BytesIO()
    gerados: list[str] = []
    erros: list[str] = []
    resumo_turmas: list[dict] = []

    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for turma in turmas:
            tid = turma.get("id")
            titulo = turma.get("titulo") or "Turma"
            data_t = str(turma.get("data_treinamento") or "")[:10]
            pasta = f"{_slug(grupo_nome)}/{data_t}_{_slug(titulo)}"

            client_id = turma.get("client_id")
            empresa = empresas_por_id.get(client_id) or fetch_empresa(client_id)
            curso = fetch_curso(turma.get("curso_id"))
            instrutor = fetch_instrutor(turma.get("instrutor_id"))
            ct = fetch_ct(turma.get("ct_id"))
            matriculas = fetch_matriculas(tid)

            nivel = (turma.get("nivel") or "").strip() or "Formação"
            modalidade = (turma.get("modalidade") or "").strip() or "Presencial"
            carga = (turma.get("carga_horaria") or "").strip() or "8 Horas"
            normativa = turma.get("normativa") or curso.get("normativa") or ""
            curso_nome = curso.get("name") or "Treinamento"
            exige_atestado = bool(curso.get("exige_atestado", True))

            if not matriculas:
                erros.append(f"{titulo}: sem alunos matriculados")
                resumo_turmas.append(
                    {
                        "turma": titulo,
                        "data": _fmt_data_br(data_t),
                        "empresa": (empresa or {}).get("name") or "",
                        "docs": 0,
                        "status": "sem alunos",
                    }
                )
                continue

            cidade = resolver_cidade(turma.get("ct_id"), turma)
            cidade_data = formatar_data_extenso(data_t, cidade=cidade)

            alunos_cert = alunos_para_certificado(matriculas, carga, incluir_nasc=True)
            alunos_atest = alunos_para_atestado(matriculas, carga, nivel)
            alunos_lista = alunos_para_lista_presenca(matriculas)

            turma_cert = {
                "modalidade": modalidade,
                "nivel": nivel,
                "carga_horaria": carga,
                "resp_tecnico": dados_resp.get("nome", ""),
                "cpf_resp_tecnico": dados_resp.get("cpf", ""),
                "re_resp_tecnico": dados_resp.get("re", ""),
                "assinatura_resp_url": dados_resp.get("assinatura_url"),
                "curso_nome": curso_nome,
                "dizeres_certificado_empresa": curso.get(
                    "dizeres_certificado_empresa", ""
                ),
                "dizeres_certificado_aluno": curso.get(
                    "dizeres_certificado_aluno", ""
                ),
            }

            docs_ok = 0

            if incluir_atestado and exige_atestado:
                try:
                    pdf = gerar_atestado_pdf_de_arquivo(
                        alunos=alunos_atest,
                        turma=turma,
                        empresa=empresa,
                        curso=curso or None,
                        instrutor=instrutor,
                        ct=ct or None,
                        cidade_data_formatada=cidade_data,
                    )
                    zf.writestr(f"{pasta}/01_atestado.pdf", pdf)
                    gerados.append(f"{titulo}/atestado")
                    docs_ok += 1
                except Exception as e:
                    erros.append(f"{titulo} atestado: {e}")

            if incluir_cert_empresa:
                try:
                    pdf = gerar_certificado_empresa_pdf(
                        turma=turma_cert,
                        instrutor=instrutor,
                        empresa=empresa,
                        alunos=alunos_cert,
                        normativa=normativa,
                        cidade_data=cidade_data,
                    )
                    zf.writestr(f"{pasta}/02_certificado_empresa.pdf", pdf)
                    gerados.append(f"{titulo}/cert_empresa")
                    docs_ok += 1
                except Exception as e:
                    erros.append(f"{titulo} cert. empresa: {e}")

            if incluir_cert_alunos:
                try:
                    zip_alunos = gerar_certificados_pdf_zip(
                        alunos_matriculas=alunos_cert,
                        turma=turma_cert,
                        instrutor=instrutor,
                        empresa=empresa,
                        ct=None,
                        normativa=normativa,
                        cidade_data=cidade_data,
                    )
                    zf.writestr(f"{pasta}/03_certificados_individuais.zip", zip_alunos)
                    gerados.append(f"{titulo}/cert_alunos")
                    docs_ok += 1
                except Exception as e:
                    erros.append(f"{titulo} cert. alunos: {e}")

            if incluir_carteirinhas:
                try:
                    pdf = gerar_carteirinhas_pdf(
                        alunos=alunos_cert,
                        curso_nome=curso_nome,
                        carga_horaria=carga,
                        data_conclusao=data_t,
                        instrutor=instrutor,
                        ct=ct or None,
                    )
                    zf.writestr(f"{pasta}/04_carteirinhas.pdf", pdf)
                    gerados.append(f"{titulo}/carteirinhas")
                    docs_ok += 1
                except Exception as e:
                    erros.append(f"{titulo} carteirinhas: {e}")

            if incluir_lista:
                try:
                    df = pd.DataFrame(alunos_lista)
                    xlsx_buf = io.BytesIO()
                    with pd.ExcelWriter(xlsx_buf, engine="openpyxl") as writer:
                        df.to_excel(
                            writer, index=False, sheet_name="Lista de Presença"
                        )
                    zf.writestr(
                        f"{pasta}/05_lista_presenca.xlsx", xlsx_buf.getvalue()
                    )
                    gerados.append(f"{titulo}/lista")
                    docs_ok += 1
                except Exception as e:
                    erros.append(f"{titulo} lista: {e}")

            resumo_turmas.append(
                {
                    "turma": titulo,
                    "data": _fmt_data_br(data_t),
                    "empresa": (empresa or {}).get("name") or "",
                    "docs": docs_ok,
                    "status": "ok" if docs_ok else "falhou",
                }
            )

    zip_buf.seek(0)
    meta = {
        "gerados": gerados,
        "erros": erros,
        "resumo": resumo_turmas,
        "total_docs": len(gerados),
        "total_turmas": len(turmas),
    }
    return zip_buf.getvalue(), meta
