from __future__ import annotations

import io
import zipfile
from datetime import date, datetime
from typing import Any

import pandas as pd

from src.config.database import supabase
from src.pages.private.turmas.helpers import (
    extrair_cidade_do_endereco,
    formatar_data_extenso,
)
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
    marcar_documento_emitido,
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


def listar_todas_empresas() -> list[dict]:
    try:
        res = (
            supabase.table("clients")
            .select("id, name, cnpj, sigla, full_address, grupo_id")
            .order("name")
            .execute()
        )
        return res.data if res and isinstance(res.data, list) else []
    except Exception:
        return []


def empresas_por_ids(ids: list[str]) -> dict[str, dict]:
    if not ids:
        return {}
    try:
        res = (
            supabase.table("clients")
            .select("id, name, cnpj, sigla, full_address, grupo_id")
            .in_("id", ids)
            .execute()
        )
        rows = res.data if res and isinstance(res.data, list) else []
        return {r["id"]: r for r in rows if r.get("id")}
    except Exception:
        return {}


def turmas_do_periodo(
    client_ids: list[str] | None,
    data_inicio: date | str,
    data_fim: date | str,
) -> list[dict]:
    """Turmas no período. Se client_ids for None ou vazio, busca de todas as empresas."""
    di = (
        data_inicio.isoformat()
        if hasattr(data_inicio, "isoformat")
        else str(data_inicio)[:10]
    )
    df = data_fim.isoformat() if hasattr(data_fim, "isoformat") else str(data_fim)[:10]

    try:
        q = (
            supabase.table("turmas")
            .select("*")
            .gte("data_treinamento", di)
            .lte("data_treinamento", df)
            .order("data_treinamento")
        )
        if client_ids:
            q = q.in_("client_id", client_ids)
        res = q.execute()
        return res.data if res and isinstance(res.data, list) else []
    except Exception:
        return []


def responsavel_padrao() -> dict:
    """Usa fetch_responsaveis (ja completa RE a partir do instrutor se precisar)."""
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


def _fmt_data_br(val) -> str:
    if not val:
        return ""
    s = str(val)[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return s


def listar_cts_completo() -> dict[str, dict]:
    """Todos os CTs (select *), indexados por id. 1 consulta por pacote."""
    try:
        res = supabase.table("cts").select("*").execute()
        rows = res.data if res and isinstance(res.data, list) else []
        return {str(r["id"]): r for r in rows if r.get("id")}
    except Exception:
        return {}


def marcar_turmas_emitidas(tids: list[str]) -> tuple[list[str], list[str]]:
    """Marca varias turmas como emitidas. Retorna (ok_ids, falhas_msg)."""
    ok: list[str] = []
    falhas: list[str] = []
    for tid in tids:
        sucesso, msg = marcar_documento_emitido(tid)
        if sucesso:
            ok.append(tid)
        else:
            falhas.append(f"{tid}: {msg}")
    return ok, falhas


def gerar_docs_turma(
    *,
    grupo_nome: str,
    turma: dict,
    empresas_por_id: dict[str, dict],
    dados_resp: dict,
    incluir_atestado: bool = True,
    incluir_cert_empresa: bool = True,
    incluir_cert_alunos: bool = True,
    incluir_carteirinhas: bool = True,
    incluir_lista: bool = True,
    pre: dict | None = None,
    marcar: bool = True,
) -> tuple[list[tuple[str, bytes]], dict[str, Any]]:
    """Gera os documentos de UMA turma. Seguro para rodar em thread (sem Streamlit).

    Retorna (arquivos[(caminho_no_zip, bytes)], info).
    info = {tid, titulo, gerados, erros, resumo(dict), docs_ok, marcado, erro_marca}

    pre: dados ja carregados em lote {empresa, curso, instrutor, ct, matriculas};
         o que faltar e buscado individualmente.
    marcar: se False, NAO marca a turma como emitida (a tela marca no download).
    """
    pre = pre or {}
    tid = turma.get("id")
    titulo = turma.get("titulo") or "Turma"
    data_t = str(turma.get("data_treinamento") or "")[:10]
    pasta = f"{_slug(grupo_nome)}/{data_t}_{_slug(titulo)}"

    arquivos: list[tuple[str, bytes]] = []
    gerados: list[str] = []
    erros: list[str] = []

    client_id = turma.get("client_id")
    empresa = (
        empresas_por_id.get(client_id)
        or pre.get("empresa")
        or fetch_empresa(client_id)
    )
    curso = pre["curso"] if pre.get("curso") else fetch_curso(turma.get("curso_id"))
    instrutor = (
        pre["instrutor"]
        if pre.get("instrutor")
        else fetch_instrutor(turma.get("instrutor_id"))
    )
    ct = pre["ct"] if "ct" in pre else fetch_ct(turma.get("ct_id"))
    matriculas = pre.get("matriculas") or fetch_matriculas(tid)

    def _info(docs_ok: int, status: str, marcado: bool, erro_marca: str | None):
        return {
            "tid": tid,
            "docs_ok": docs_ok,
            "titulo": titulo,
            "gerados": gerados,
            "erros": erros,
            "marcado": marcado,
            "erro_marca": erro_marca,
            "resumo": {
                "turma": titulo,
                "data": _fmt_data_br(data_t),
                "empresa": (empresa or {}).get("name") or "",
                "docs": docs_ok,
                "status": status,
                "marcado": marcado,
            },
        }

    if not matriculas:
        erros.append(f"{titulo}: sem alunos matriculados")
        return arquivos, _info(0, "sem alunos", False, None)

    nivel = (turma.get("nivel") or "").strip() or "Formação"
    modalidade = (turma.get("modalidade") or "").strip() or "Presencial"
    carga = (turma.get("carga_horaria") or "").strip() or "8 Horas"
    normativa = turma.get("normativa") or curso.get("normativa") or ""
    curso_nome = curso.get("name") or "Treinamento"
    exige_atestado = bool(curso.get("exige_atestado", True))

    if "ct" in pre:  # ct ja carregado: evita consulta por turma
        cidade = (
            extrair_cidade_do_endereco(ct.get("full_address"))
            if ct
            else "Itapecerica da Serra"
        )
    else:
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
        "formacao_resp_tecnico": dados_resp.get("formacao", ""),
        "assinatura_resp_url": dados_resp.get("assinatura_url"),
        "curso_nome": curso_nome,
        "curso_sigla": (curso.get("sigla") or "").strip().upper(),
        "dizeres_certificado_empresa": curso.get("dizeres_certificado_empresa", ""),
        "dizeres_certificado_aluno": curso.get("dizeres_certificado_aluno", ""),
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
            arquivos.append((f"{pasta}/01_atestado.pdf", pdf))
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
                ct=ct or None,
                alunos=alunos_cert,
                normativa=normativa,
                cidade_data=cidade_data,
            )
            arquivos.append((f"{pasta}/02_certificado_empresa.pdf", pdf))
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
                ct=ct or None,
                normativa=normativa,
                cidade_data=cidade_data,
            )
            arquivos.append((f"{pasta}/03_certificados_individuais.zip", zip_alunos))
            gerados.append(f"{titulo}/cert_alunos")
            docs_ok += 1
        except Exception as e:
            erros.append(f"{titulo} cert. alunos: {e}")

    if incluir_carteirinhas:
        try:
            pdf, _alunos_re = gerar_carteirinhas_pdf(
                alunos=alunos_cert,
                curso=curso or None,
                turma=turma,
                carga_horaria=carga,
                data_conclusao=data_t,
                instrutor=instrutor,
                ct=ct or None,
            )
            arquivos.append((f"{pasta}/04_carteirinhas.pdf", pdf))
            gerados.append(f"{titulo}/carteirinhas")
            docs_ok += 1
        except Exception as e:
            erros.append(f"{titulo} carteirinhas: {e}")

    if incluir_lista:
        try:
            df = pd.DataFrame(alunos_lista)
            xlsx_buf = io.BytesIO()
            with pd.ExcelWriter(xlsx_buf, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="Lista de Presença")
            arquivos.append((f"{pasta}/05_lista_presenca.xlsx", xlsx_buf.getvalue()))
            gerados.append(f"{titulo}/lista")
            docs_ok += 1
        except Exception as e:
            erros.append(f"{titulo} lista: {e}")

    marcado = False
    erro_marca = None
    if marcar and docs_ok > 0 and tid:
        ok_marca, msg_marca = marcar_documento_emitido(tid)
        if ok_marca:
            marcado = True
        else:
            erro_marca = f"{titulo}: {msg_marca}"
            erros.append(f"{titulo} status: {msg_marca}")

    return arquivos, _info(docs_ok, "ok" if docs_ok else "falhou", marcado, erro_marca)


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
    """Versao sincrona (compat). A tela usa o modo em lotes via gerar_docs_turma."""
    dados_resp = dados_resp or responsavel_padrao()
    zip_buf = io.BytesIO()
    meta: dict[str, Any] = {
        "gerados": [],
        "erros": [],
        "resumo": [],
        "total_docs": 0,
        "total_turmas": len(turmas),
        "turmas_marcadas": [],
        "turmas_falha_marca": [],
    }
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for turma in turmas:
            arquivos, info = gerar_docs_turma(
                grupo_nome=grupo_nome,
                turma=turma,
                empresas_por_id=empresas_por_id,
                dados_resp=dados_resp,
                incluir_atestado=incluir_atestado,
                incluir_cert_empresa=incluir_cert_empresa,
                incluir_cert_alunos=incluir_cert_alunos,
                incluir_carteirinhas=incluir_carteirinhas,
                incluir_lista=incluir_lista,
            )
            for caminho, dados in arquivos:
                zf.writestr(caminho, dados)
            meta["gerados"].extend(info["gerados"])
            meta["erros"].extend(info["erros"])
            meta["resumo"].append(info["resumo"])
            if info["marcado"]:
                meta["turmas_marcadas"].append(info["titulo"])
            if info["erro_marca"]:
                meta["turmas_falha_marca"].append(info["erro_marca"])
    meta["total_docs"] = len(meta["gerados"])
    return zip_buf.getvalue(), meta
