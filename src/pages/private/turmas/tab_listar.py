import re
from datetime import datetime

import streamlit as st

from src.config.database import supabase
from src.auth.permissions import ct_id_atual, is_consulta
from src.pages.private.turmas.helpers import so_digitos
from src.pages.private.turmas.modals import (
    modal_adicionar_aluno,
    modal_editar_matriculas,
    modal_editar_turma,
    modal_emitir_documentacao,
)


def _fmt_data_br(data_str) -> str:
    if not data_str:
        return "—"
    s = str(data_str)[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return s


TURMAS_POR_PAGINA = 100  # teto: 100 turmas por página
MAX_EMPRESAS_BUSCA = 200  # limite de empresas no filtro por nome/CNPJ (tamanho da URL)
PAG_KEY = "turmas_pagina_atual"
SIG_KEY = "turmas_filtros_sig"

_SELECT_TURMAS = (
    "id, titulo, modalidade, nivel, carga_horaria, data_treinamento, "
    "documento_emitido, created_at, instrutor_id, client_id, ct_id, "
    "cursos(name), instrutores(id, name), clients(id, name, cnpj, sigla), cts(id, name)"
)
_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def _expr_busca(termo: str) -> tuple[str | None, bool]:
    """Monta o filtro `or` do PostgREST (título, empresa/sigla/CNPJ ou id exato).

    Retorna (expressão | None, truncado). `truncado` indica que mais empresas
    casaram do que o limite MAX_EMPRESAS_BUSCA.
    """
    termo = (termo or "").strip()
    if not termo:
        return None, False

    # vírgula, parênteses e curingas quebrariam a sintaxe do filtro
    t = re.sub(r"[,()%*\\]", " ", termo)
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        return None, False

    partes = [f"titulo.ilike.%{t}%"]
    if _UUID_RE.fullmatch(termo):
        partes.append(f"id.eq.{termo}")

    filtros_cli = [f"name.ilike.%{t}%", f"sigla.ilike.%{t}%", f"cnpj.ilike.%{t}%"]
    if re.fullmatch(r"[\d.\-/\s]+", t):
        dig = so_digitos(t)
        if dig:
            filtros_cli.append(f"cnpj.ilike.%{dig}%")

    truncado = False
    try:
        res = (
            supabase.table("clients")
            .select("id")
            .or_(",".join(filtros_cli))
            .limit(MAX_EMPRESAS_BUSCA + 1)
            .execute()
        )
        ids = [str(r["id"]) for r in (res.data or []) if r.get("id")]
        if len(ids) > MAX_EMPRESAS_BUSCA:
            ids = ids[:MAX_EMPRESAS_BUSCA]
            truncado = True
        if ids:
            partes.append(f"client_id.in.({','.join(ids)})")
    except Exception:
        pass

    return ",".join(partes), truncado


def _aplicar_filtros(q, f: dict):
    if f.get("ct_id"):
        q = q.eq("ct_id", f["ct_id"])
    if f.get("status") == "Pendentes":
        q = q.eq("documento_emitido", False)
    elif f.get("status") == "Emitidos":
        q = q.eq("documento_emitido", True)
    if f.get("instrutor_id"):
        q = q.eq("instrutor_id", f["instrutor_id"])
    if f.get("data_de"):
        q = q.gte("data_treinamento", f["data_de"].isoformat())
    if f.get("data_ate"):
        q = q.lte("data_treinamento", f["data_ate"].isoformat())
    if f.get("expr_busca"):
        q = q.or_(f["expr_busca"])
    return q


def _contar_turmas(f: dict) -> int:
    q = supabase.table("turmas").select("id", count="exact")
    res = _aplicar_filtros(q, f).limit(1).execute()
    return int(res.count or 0)


def _buscar_pagina(f: dict, pagina: int) -> list[dict]:
    ini = (pagina - 1) * TURMAS_POR_PAGINA
    fim = ini + TURMAS_POR_PAGINA - 1
    ultimo_erro: Exception | None = None
    # pendentes primeiro; depois mais recentes; `id` como desempate (páginas estáveis)
    for col_ord in ("created_at", "data_treinamento"):
        try:
            q = supabase.table("turmas").select(_SELECT_TURMAS)
            q = _aplicar_filtros(q, f)
            res = (
                q.order("documento_emitido")
                .order(col_ord, desc=True)
                .order("id")
                .range(ini, fim)
                .execute()
            )
            return list(res.data or [])
        except Exception as e:
            ultimo_erro = e
    raise ultimo_erro  # type: ignore[misc]


def _ir_pagina(p: int) -> None:
    st.session_state[PAG_KEY] = p


def _render_paginacao(pagina: int, total_paginas: int, sufixo: str) -> None:
    if total_paginas <= 1:
        return
    c1, c2, c3, c4, c5 = st.columns([1, 1, 3, 1, 1])
    c1.button(
        "⏮",
        key=f"pag_primeira_{sufixo}",
        disabled=pagina <= 1,
        on_click=_ir_pagina,
        args=(1,),
        use_container_width=True,
        help="Primeira página",
    )
    c2.button(
        "◀",
        key=f"pag_ant_{sufixo}",
        disabled=pagina <= 1,
        on_click=_ir_pagina,
        args=(pagina - 1,),
        use_container_width=True,
        help="Página anterior",
    )
    c3.markdown(
        f"<div style='text-align:center;padding-top:0.4rem'>"
        f"Página <b>{pagina}</b> de <b>{total_paginas}</b></div>",
        unsafe_allow_html=True,
    )
    c4.button(
        "▶",
        key=f"pag_prox_{sufixo}",
        disabled=pagina >= total_paginas,
        on_click=_ir_pagina,
        args=(pagina + 1,),
        use_container_width=True,
        help="Próxima página",
    )
    c5.button(
        "⏭",
        key=f"pag_ultima_{sufixo}",
        disabled=pagina >= total_paginas,
        on_click=_ir_pagina,
        args=(total_paginas,),
        use_container_width=True,
        help="Última página",
    )


def _excluir_turma(tid: str) -> tuple[bool, str]:
    """Remove matrículas da turma e depois a turma."""
    try:
        supabase.table("matriculas").delete().eq("turma_id", tid).execute()
        supabase.table("turmas").delete().eq("id", tid).execute()
        return True, "Turma excluída com sucesso."
    except Exception as e:
        return False, str(e)


@st.dialog("Excluir turma", width="small")
def modal_excluir_turma(tid: str, titulo: str, qtd_alunos: int):
    st.warning(
        f"Tem certeza que deseja excluir a turma **{titulo}**?\n\n"
        f"Isso remove também as **{qtd_alunos}** matrícula(s) vinculadas. "
        "Esta ação não pode ser desfeita."
    )
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Cancelar", use_container_width=True, key=f"cancel_del_{tid}"):
            st.rerun()
    with c2:
        if st.button(
            "Excluir definitivamente",
            type="primary",
            use_container_width=True,
            key=f"confirm_del_{tid}",
        ):
            ok, msg = _excluir_turma(tid)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(f"Erro ao excluir: {msg}")


def render_tab_listar():
    st.subheader("Painel de Turmas e Emissão de Documentos")

    _ct_user = ct_id_atual() if is_consulta() else None
    if _ct_user:
        st.caption("Exibindo apenas turmas do **seu CT**.")

    # CTs para filtro (usuário sem CT vinculado vê todos)
    opcoes_ct = ["Todos"]
    mapa_ct: dict[str, str] = {}
    try:
        res_cts = supabase.table("cts").select("id, name").order("name").execute()
        if res_cts and res_cts.data:
            for c in res_cts.data:
                nome = (c.get("name") or "Sem nome").strip()
                if not nome:
                    continue
                opcoes_ct.append(nome)
                mapa_ct[nome] = c.get("id")
    except Exception:
        pass

    col1, col2, col_ct = st.columns(3)
    with col1:
        busca_turma = st.text_input(
            "Buscar (título, empresa ou CNPJ)",
            placeholder="Título, nome da empresa ou CNPJ...",
        )
    with col2:
        filtro_status = st.selectbox(
            "Status dos Documentos", ["Todos", "Pendentes", "Emitidos"]
        )
    with col_ct:
        if _ct_user:
            # Usuário de CT: filtro travado no próprio CT
            nome_ct_user = next(
                (n for n, i in mapa_ct.items() if i == _ct_user), "Seu CT"
            )
            st.selectbox(
                "CT",
                [nome_ct_user],
                index=0,
                key="filtro_ct_turmas",
                disabled=True,
            )
            filtro_ct = nome_ct_user
        else:
            filtro_ct = st.selectbox("CT", opcoes_ct, key="filtro_ct_turmas")

    col_d1, col_d2, col_inst = st.columns(3)
    with col_d1:
        data_de = st.date_input(
            "Data treinamento (de)",
            value=None,
            format="DD/MM/YYYY",
            key="filtro_data_de",
        )
    with col_d2:
        data_ate = st.date_input(
            "Data treinamento (até)",
            value=None,
            format="DD/MM/YYYY",
            key="filtro_data_ate",
        )
    with col_inst:
        opcoes_instrutor = ["Todos"]
        mapa_instrutor: dict[str, str] = {}
        try:
            res_inst = (
                supabase.table("instrutores")
                .select("id, name")
                .order("name")
                .execute()
            )
            if res_inst and res_inst.data:
                for i in res_inst.data:
                    nome = i.get("name") or "Sem nome"
                    opcoes_instrutor.append(nome)
                    mapa_instrutor[nome] = i.get("id")
        except Exception:
            pass
        filtro_instrutor = st.selectbox("Instrutor", opcoes_instrutor)

    try:
        filtros = {
            "ct_id": _ct_user
            or (mapa_ct.get(filtro_ct) if filtro_ct != "Todos" else None),
            "status": filtro_status,
            "instrutor_id": (
                mapa_instrutor.get(filtro_instrutor)
                if filtro_instrutor != "Todos"
                else None
            ),
            "data_de": data_de,
            "data_ate": data_ate,
            "busca": busca_turma.strip(),
        }

        # Mudou qualquer filtro -> volta para a página 1
        assinatura = tuple(str(v) for v in filtros.values())
        if st.session_state.get(SIG_KEY) != assinatura:
            st.session_state[SIG_KEY] = assinatura
            st.session_state[PAG_KEY] = 1

        expr_busca, busca_truncada = _expr_busca(filtros["busca"])
        filtros["expr_busca"] = expr_busca

        total = _contar_turmas(filtros)
        if total == 0:
            st.info(
                "Nenhuma turma encontrada com os filtros aplicados."
                if any(
                    filtros[k]
                    for k in ("busca", "data_de", "data_ate", "instrutor_id")
                )
                or filtro_status != "Todos"
                or filtro_ct != "Todos"
                else "Nenhuma turma encontrada."
            )
            return

        total_paginas = max(1, -(-total // TURMAS_POR_PAGINA))
        pagina = min(max(int(st.session_state.get(PAG_KEY, 1)), 1), total_paginas)
        st.session_state[PAG_KEY] = pagina

        turmas_exibir = _buscar_pagina(filtros, pagina)
        if not turmas_exibir:
            st.info("Nenhuma turma encontrada com os filtros aplicados.")
            return

        ini = (pagina - 1) * TURMAS_POR_PAGINA
        st.caption(
            f"{total} turma(s) · mostrando {ini + 1}–{ini + len(turmas_exibir)} · "
            "pendentes de documento no topo; mais recentes primeiro."
        )
        if busca_truncada:
            st.warning(
                f"A busca casa com muitas empresas; só as primeiras {MAX_EMPRESAS_BUSCA} "
                "entram no filtro por empresa. Refine o termo para ver todas."
            )

        _render_paginacao(pagina, total_paginas, "topo")

        for t in turmas_exibir:
            tid = t.get("id")
            data_trein = str(t.get("data_treinamento", ""))[:10]
            data_br = _fmt_data_br(data_trein)
            status_doc = t.get("documento_emitido", False)
            curso_nome = (t.get("cursos") or {}).get("name", "N/A")
            empresa_nome = (t.get("clients") or {}).get("name", "Sem Empresa Vinculada")
            empresa_id = (t.get("clients") or {}).get("id") or t.get("client_id")
            _cnpj = ((t.get("clients") or {}).get("cnpj") or "").strip()
            empresa_cnpj_txt = f" (CNPJ {_cnpj})" if _cnpj else ""
            ct_id = (t.get("cts") or {}).get("id") or t.get("ct_id")
            ct_nome = (t.get("cts") or {}).get("name") or "—"
            instrutor_nome = (t.get("instrutores") or {}).get("name", "N/A")
            titulo = t.get("titulo") or "Sem título"
            icon_status = "✅" if status_doc else "⚠️"

            label_expander = f"{icon_status} **{data_br}** · {empresa_nome} · {ct_nome}"

            with st.expander(label_expander, expanded=False):
                st.markdown(
                    f"""
* **ID:** `{tid}`
* **Título:** {titulo}
* **Curso:** {curso_nome}
* **Instrutor:** {instrutor_nome}
* **Empresa:** {empresa_nome}{empresa_cnpj_txt}
* **CT:** {ct_nome}
* **Data treinamento:** {data_br}
* **Modalidade:** {t.get('modalidade') or '—'}
* **Nível:** {t.get('nivel') or '—'}
* **Carga:** {t.get('carga_horaria') or '—'}
* **Documentos:** {'Emitidos' if status_doc else 'Pendentes'}
                    """
                )

                c1, c2, c3, c4, c5 = st.columns(5)
                with c1:
                    if st.button(
                        "Documentos",
                        key=f"docs_{tid}",
                        use_container_width=True,
                    ):
                        modal_emitir_documentacao(
                            tid,
                            titulo,
                            empresa_id,
                            ct_id,
                        )
                with c2:
                    if st.button(
                        "Editar",
                        key=f"edit_{tid}",
                        use_container_width=True,
                    ):
                        modal_editar_turma(tid)
                with c3:
                    if st.button(
                        "Aluno",
                        key=f"add_{tid}",
                        use_container_width=True,
                    ):
                        modal_adicionar_aluno(
                            tid,
                            titulo,
                            empresa_id,
                            data_trein,
                            t.get("carga_horaria"),
                        )
                with c4:
                    if st.button(
                        "Matrículas",
                        key=f"mat_{tid}",
                        use_container_width=True,
                    ):
                        modal_editar_matriculas(tid, titulo)
                with c5:
                    if st.button(
                        "   Excluir",
                        key=f"del_{tid}",
                        use_container_width=True,
                    ):
                        try:
                            r = (
                                supabase.table("matriculas")
                                .select("id", count="exact")
                                .eq("turma_id", tid)
                                .execute()
                            )
                            qtd = r.count if r and r.count is not None else 0
                        except Exception:
                            qtd = 0
                        modal_excluir_turma(tid, titulo, qtd)

        _render_paginacao(pagina, total_paginas, "base")

    except Exception as e:
        st.error(f"Erro ao listar turmas: {e}")
