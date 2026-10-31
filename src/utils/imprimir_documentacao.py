"""Gera PDFs consolidados do dia por CT (certificados, atestados, etc.)."""
from __future__ import annotations

import io
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from typing import Any

from pypdf import PdfReader, PdfWriter

from src.config.database import supabase
from src.pages.private.turmas.helpers import formatar_data_extenso
from src.pages.private.turmas.modals.emitir_documentos.alunos import (
    alunos_para_atestado,
    alunos_para_certificado,
)
from src.pages.private.turmas.modals.emitir_documentos.data import (
    fetch_responsaveis,
    resolver_cidade,
)
from src.utils.atestado import gerar_atestado_pdf_de_arquivo
from src.utils.carteirinha import gerar_carteirinhas_pdf
from src.utils.certificado import gerar_certificados_pdf
from src.utils.certificado_empresa import gerar_certificado_empresa_pdf

# WeasyPrint é pesado; 3 workers costuma ser o melhor custo/benefício no Streamlit Cloud
_MAX_WORKERS = 3


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
        res = (
            supabase.table("cts")
            .select("id, name, full_name, full_address, phone, cnpj, logo_url")
            .order("name")
            .execute()
        )
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


def _in_chunks(ids: list[str], size: int = 80):
    for i in range(0, len(ids), size):
        yield ids[i : i + size]


def _prefetch_maps(turmas: list[dict]) -> tuple[dict, dict, dict, dict]:
    """Carrega cursos, instrutores, empresas e matrículas em lote (1–poucas queries)."""
    curso_ids = list({str(t["curso_id"]) for t in turmas if t.get("curso_id")})
    inst_ids = list({str(t["instrutor_id"]) for t in turmas if t.get("instrutor_id")})
    emp_ids = list({str(t["client_id"]) for t in turmas if t.get("client_id")})
    turma_ids = list({str(t["id"]) for t in turmas if t.get("id")})

    cursos: dict[str, dict] = {}
    for lote in _in_chunks(curso_ids):
        try:
            res = supabase.table("cursos").select("*").in_("id", lote).execute()
            for r in res.data or []:
                if r.get("id"):
                    cursos[str(r["id"])] = r
        except Exception:
            pass

    instrutores: dict[str, dict] = {}
    for lote in _in_chunks(inst_ids):
        try:
            res = supabase.table("instrutores").select("*").in_("id", lote).execute()
            for r in res.data or []:
                if r.get("id"):
                    instrutores[str(r["id"])] = r
        except Exception:
            pass

    empresas: dict[str, dict] = {}
    for lote in _in_chunks(emp_ids):
        try:
            res = supabase.table("clients").select("*").in_("id", lote).execute()
            for r in res.data or []:
                if r.get("id"):
                    empresas[str(r["id"])] = r
        except Exception:
            pass

    # matrículas por turma_id
    mats_por_turma: dict[str, list] = {tid: [] for tid in turma_ids}
    for lote in _in_chunks(turma_ids):
        try:
            res = (
                supabase.table("matriculas")
                .select(
                    "id, turma_id, aluno_id, data_treinamento, carga_horaria, "
                    "alunos(id, name, cpf, rg, data_nasc, re), "
                    "clients(id, name, sigla)"
                )
                .in_("turma_id", lote)
                .execute()
            )
            for m in res.data or []:
                tid = str(m.get("turma_id") or "")
                if tid in mats_por_turma:
                    mats_por_turma[tid].append(m)
        except Exception:
            # fallback sem join
            try:
                res = (
                    supabase.table("matriculas")
                    .select("id, turma_id, aluno_id, data_treinamento")
                    .in_("turma_id", lote)
                    .execute()
                )
                for m in res.data or []:
                    tid = str(m.get("turma_id") or "")
                    if tid in mats_por_turma:
                        mats_por_turma[tid].append(m)
            except Exception:
                pass

    return cursos, instrutores, empresas, mats_por_turma


def _gerar_uma_turma(
    *,
    tipo: str,
    turma: dict,
    ct: dict,
    dados_resp: dict,
    curso: dict,
    instrutor: dict,
    empresa: dict,
    matriculas: list,
) -> tuple[bytes | None, str | None, str | None]:
    """Retorna (pdf|None, aviso|None, erro|None)."""
    titulo = turma.get("titulo") or "Turma"
    if not matriculas:
        return None, f"{titulo}: sem alunos — ignorada.", None

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
            return pdf, None, None

        if tipo == "cert_empresa":
            pdf = gerar_certificado_empresa_pdf(
                turma=turma_cert,
                instrutor=instrutor,
                empresa=empresa,
                ct=ct or None,
                alunos=alunos_cert,
                normativa=normativa,
                cidade_data=cidade_data,
            )
            return pdf, None, None

        if tipo == "atestado":
            exige = bool(curso.get("exige_atestado", True))
            if not exige:
                return None, f"{titulo}: curso não exige atestado — ignorada.", None
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
            return pdf, None, None

        if tipo == "carteirinhas":
            pdf, _alunos_re = gerar_carteirinhas_pdf(
                alunos=alunos_cert,
                curso=curso or None,
                turma=turma,
                carga_horaria=carga,
                data_conclusao=data_t,
                instrutor=instrutor,
                ct=ct or None,
            )
            return pdf, None, None

        return None, None, f"{titulo}: tipo desconhecido ({tipo})"
    except Exception as e:
        return None, None, f"{titulo}: {e}"


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

    Otimizações:
    - prefetch de cursos/instrutores/empresas/matrículas em lote
    - geração de PDF das turmas em paralelo (ThreadPool)
    """
    dados_resp = dados_resp or responsavel_padrao()
    avisos: list[str] = []
    erros: list[str] = []

    if not turmas:
        return None, avisos, erros

    cursos, instrutores, empresas, mats_por_turma = _prefetch_maps(turmas)

    jobs = []
    for turma in turmas:
        tid = str(turma.get("id") or "")
        titulo = turma.get("titulo") or "Turma"
        curso = cursos.get(str(turma.get("curso_id") or ""), {})
        instrutor = instrutores.get(str(turma.get("instrutor_id") or ""), {})
        empresa = empresas.get(str(turma.get("client_id") or ""), {})
        matriculas = mats_por_turma.get(tid) or []

        if not matriculas:
            avisos.append(f"{titulo}: sem alunos — ignorada.")
            continue

        jobs.append(
            {
                "tipo": tipo,
                "turma": turma,
                "ct": ct,
                "dados_resp": dados_resp,
                "curso": curso,
                "instrutor": instrutor,
                "empresa": empresa,
                "matriculas": matriculas,
            }
        )

    if not jobs:
        return None, avisos, erros

    # Mantém ordem das turmas no PDF final
    resultados: list[bytes | None] = [None] * len(jobs)

    workers = min(_MAX_WORKERS, len(jobs))
    if workers <= 1:
        for i, job in enumerate(jobs):
            pdf, aviso, erro = _gerar_uma_turma(**job)
            if aviso:
                avisos.append(aviso)
            if erro:
                erros.append(erro)
            resultados[i] = pdf
    else:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(_gerar_uma_turma, **job): i for i, job in enumerate(jobs)}
            for fut in as_completed(futs):
                i = futs[fut]
                try:
                    pdf, aviso, erro = fut.result()
                except Exception as e:
                    pdf, aviso, erro = None, None, str(e)
                if aviso:
                    avisos.append(aviso)
                if erro:
                    erros.append(erro)
                resultados[i] = pdf

    pdfs = [p for p in resultados if p]
    if not pdfs:
        return None, avisos, erros

    try:
        return _merge_pdfs(pdfs), avisos, erros
    except Exception as e:
        return None, avisos, erros + [f"Falha ao unir PDFs: {e}"]
