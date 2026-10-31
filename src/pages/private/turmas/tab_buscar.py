"""Busca turmas por nome, CPF ou RG do aluno."""
from __future__ import annotations

import re
from datetime import datetime

import streamlit as st

from src.auth.permissions import ct_id_atual, is_consulta
from src.config.database import supabase
from src.pages.private.turmas.modals import (
    modal_editar_matriculas,
    modal_editar_turma,
    modal_emitir_documentacao,
)


def _so_digitos(val) -> str:
    return re.sub(r"\D", "", str(val or ""))


def _fmt_data_br(data_str) -> str:
    if not data_str:
        return "—"
    s = str(data_str)[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return s


def _buscar_alunos(termo: str) -> list[dict]:
    """Localiza alunos por nome (parcial), CPF ou RG."""
    digitos = _so_digitos(termo)
    texto = (termo or "").strip()
    if not digitos and not texto:
        return []

    encontrados: dict[str, dict] = {}
    tem_letra = any(ch.isalpha() for ch in texto)

    # 1) Nome (parcial, case-insensitive) — prioridade quando há letras
    if tem_letra and len(texto) >= 2:
        try:
            res = (
                supabase.table("alunos")
                .select("*")
                .ilike("name", f"%{texto}%")
                .limit(80)
                .execute()
            )
            for a in res.data or []:
                if a.get("id"):
                    encontrados[str(a["id"])] = a
        except Exception as e:
            st.warning(f"Falha na busca por nome: {e}")

    # 2) CPF / RG (quando há dígitos suficientes)
    if len(digitos) >= 5:
        # CPF completo direto no banco
        if len(digitos) == 11:
            try:
                res = (
                    supabase.table("alunos")
                    .select("*")
                    .eq("cpf", digitos)
                    .execute()
                )
                for a in res.data or []:
                    if a.get("id"):
                        encontrados[str(a["id"])] = a
            except Exception:
                pass
            # também tenta CPF formatado comum
            if not encontrados:
                cpf_fmt = (
                    f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"
                )
                try:
                    res = (
                        supabase.table("alunos")
                        .select("*")
                        .eq("cpf", cpf_fmt)
                        .execute()
                    )
                    for a in res.data or []:
                        if a.get("id"):
                            encontrados[str(a["id"])] = a
                except Exception:
                    pass

        # Varredura limitada só se ainda não achou (evita scan sempre)
        if not encontrados:
            try:
                res = supabase.table("alunos").select("*").limit(2000).execute()
                rows = res.data if res and isinstance(res.data, list) else []
                for a in rows:
                    cpf_d = _so_digitos(a.get("cpf"))
                    rg_raw = str(a.get("rg") or "")
                    rg_d = _so_digitos(rg_raw)
                    match = False
                    if digitos and cpf_d and (
                        cpf_d == digitos
                        or digitos in cpf_d
                        or cpf_d.endswith(digitos)
                    ):
                        match = True
                    if digitos and rg_d and (
                        rg_d == digitos
                        or digitos in rg_d
                        or rg_d.endswith(digitos)
                    ):
                        match = True
                    if texto and rg_raw and texto.lower() in rg_raw.lower():
                        match = True
                    if match and a.get("id"):
                        encontrados[str(a["id"])] = a
            except Exception as e:
                st.warning(f"Falha ao buscar por documento: {e}")

    return list(encontrados.values())


def _matriculas_dos_alunos(aluno_ids: list[str]) -> list[dict]:
    if not aluno_ids:
        return []
    out: list[dict] = []
    for i in range(0, len(aluno_ids), 50):
        lote = aluno_ids[i : i + 50]
        try:
            res = (
                supabase.table("matriculas")
                .select(
                    "id, turma_id, aluno_id, client_id, data_treinamento, carga_horaria, "
                    "alunos(id, name, cpf, rg), "
                    "clients(id, name)"
                )
                .in_("aluno_id", lote)
                .execute()
            )
            if res and res.data:
                out.extend(res.data)
        except Exception:
            try:
                res = (
                    supabase.table("matriculas")
                    .select("id, turma_id, aluno_id, client_id, data_treinamento")
                    .in_("aluno_id", lote)
                    .execute()
                )
                if res and res.data:
                    out.extend(res.data)
            except Exception as e:
                st.warning(f"Falha ao buscar matrículas: {e}")
    return out


def _carregar_turmas(turma_ids: list[str]) -> dict[str, dict]:
    mapa: dict[str, dict] = {}
    if not turma_ids:
        return mapa
    for i in range(0, len(turma_ids), 50):
        lote = turma_ids[i : i + 50]
        try:
            res = (
                supabase.table("turmas")
                .select(
                    "id, titulo, modalidade, nivel, carga_horaria, data_treinamento, "
                    "documento_emitido, client_id, ct_id, instrutor_id, "
                    "cursos(name, sigla), instrutores(name), clients(id, name), cts(id, name)"
                )
                .in_("id", lote)
                .execute()
            )
            for t in res.data or []:
                if t.get("id"):
                    mapa[str(t["id"])] = t
        except Exception as e:
            st.warning(f"Falha ao carregar turmas: {e}")
    return mapa


def render_tab_buscar():
    st.subheader("🔍 Buscar turmas por aluno")
    st.caption(
        "Informe o **nome**, **CPF** ou **RG** do aluno para localizar em quais turmas ele está matriculado."
    )

    if is_consulta() and ct_id_atual():
        st.caption("Resultados filtrados pelo **seu CT**.")

    col_in, col_btn = st.columns([3, 1])
    with col_in:
        termo = st.text_input(
            "Nome, CPF ou RG*",
            placeholder="Ex.: Maria Silva  ·  123.456.789-00  ·  12.345.678-9",
            key="busca_aluno_termo",
        )
    with col_btn:
        st.write("")
        buscar = st.button("🔍 Buscar", type="primary", use_container_width=True)

    if not buscar:
        if not st.session_state.get("busca_doc_resultados"):
            return

    if buscar:
        if not (termo or "").strip():
            st.warning("Informe um nome, CPF ou RG.")
            return

        with st.spinner("Buscando aluno e turmas..."):
            alunos = _buscar_alunos(termo)
            if not alunos:
                st.session_state["busca_doc_resultados"] = {
                    "termo": termo,
                    "alunos": [],
                    "itens": [],
                }
                st.info("Nenhum aluno encontrado com esse termo.")
                return

            aluno_ids = [str(a["id"]) for a in alunos if a.get("id")]
            mats = _matriculas_dos_alunos(aluno_ids)
            turma_ids = list({str(m["turma_id"]) for m in mats if m.get("turma_id")})
            turmas = _carregar_turmas(turma_ids)

            _ct_user = ct_id_atual() if is_consulta() else None
            itens = []
            for m in mats:
                tid = str(m.get("turma_id") or "")
                turma = turmas.get(tid)
                if not turma:
                    continue
                if _ct_user and str(turma.get("ct_id") or "") != str(_ct_user):
                    continue
                aluno = m.get("alunos") or {}
                if not aluno.get("name"):
                    for a in alunos:
                        if str(a.get("id")) == str(m.get("aluno_id")):
                            aluno = a
                            break
                itens.append({"matricula": m, "turma": turma, "aluno": aluno})

            st.session_state["busca_doc_resultados"] = {
                "termo": termo,
                "alunos": alunos,
                "itens": itens,
            }

    dados = st.session_state.get("busca_doc_resultados") or {}
    alunos = dados.get("alunos") or []
    itens = dados.get("itens") or []

    if not dados:
        return

    if alunos and not itens:
        st.info(
            "Aluno(s) encontrado(s), mas **sem matrícula** em turmas"
            + (" deste CT." if is_consulta() and ct_id_atual() else ".")
        )
        for a in alunos:
            st.write(
                f"- **{a.get('name') or '—'}** · CPF `{a.get('cpf') or '—'}` · RG `{a.get('rg') or '—'}`"
            )
        return

    if not itens:
        return

    termo_exib = dados.get("termo") or ""
    st.success(
        f"**{len(itens)}** matrícula(s) encontrada(s)"
        + (f" para **{termo_exib}**" if termo_exib else "")
        + "."
    )

    por_turma: dict[str, dict] = {}
    for it in itens:
        t = it["turma"]
        tid = str(t.get("id"))
        if tid not in por_turma:
            por_turma[tid] = {"turma": t, "alunos": []}
        por_turma[tid]["alunos"].append(it["aluno"])

    for tid, bloco in por_turma.items():
        t = bloco["turma"]
        titulo = t.get("titulo") or "Sem título"
        data_br = _fmt_data_br(t.get("data_treinamento"))
        curso = (t.get("cursos") or {}).get("name") or "—"
        emp = (t.get("clients") or {}).get("name") or "—"
        inst = (t.get("instrutores") or {}).get("name") or "—"
        emitido = bool(t.get("documento_emitido"))
        badge = "✅ Emitido" if emitido else "⚠️ Pendente"
        empresa_id = (t.get("clients") or {}).get("id") or t.get("client_id")
        ct_id = (t.get("cts") or {}).get("id") or t.get("ct_id")

        with st.container(border=True):
            st.markdown(f"**{titulo}** · {badge}")
            st.caption(
                f"📅 {data_br} · 🏢 {emp} · 📚 {curso} · 👨‍🏫 {inst} · "
                f"Modalidade: {t.get('modalidade') or '—'} · Nível: {t.get('nivel') or '—'}"
            )
            nomes = []
            for a in bloco["alunos"]:
                nm = (a.get("name") or a.get("nome") or "Aluno").strip()
                cpf = a.get("cpf") or ""
                nomes.append(f"{nm}" + (f" (CPF {cpf})" if cpf else ""))
            st.write("**Aluno(s):** " + "; ".join(nomes))

            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button(
                    "📄 Documentos",
                    key=f"busca_docs_{tid}",
                    use_container_width=True,
                ):
                    modal_emitir_documentacao(tid, titulo, empresa_id, ct_id)
            with c2:
                if st.button(
                    "✏️ Editar turma",
                    key=f"busca_edit_{tid}",
                    use_container_width=True,
                ):
                    modal_editar_turma(tid)
            with c3:
                if st.button(
                    "👥 Matrículas",
                    key=f"busca_mat_{tid}",
                    use_container_width=True,
                ):
                    modal_editar_matriculas(tid, titulo)
