from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from src.config.database import supabase
from src.auth.permissions import ct_id_atual

_ACCENT = "#1a5f9e"
_OK = "#1e7e34"
_WARN = "#c0392b"
_BAR = "#1a5f9e"
_BAR2 = "#3d7ab5"
_PLOT_FONT = "#334455"
_PLOT_TITLE = "#0b1f3a"

st.markdown(
    """
<div class="df-hero">
  <h1>Painel operacional</h1>
  <p>Visão filtrável de turmas, matrículas e pendências de documentação.</p>
</div>
""",
    unsafe_allow_html=True,
)


def _fmt_num(n: int | float) -> str:
    return f"{int(n):,}".replace(",", ".")


def _fetch_all(
    table: str,
    select: str,
    page_size: int = 1000,
    filters: list | None = None,
) -> list:
    out: list = []
    start = 0
    while True:
        try:
            q = supabase.table(table).select(select)
            if filters:
                for col, op, val in filters:
                    if op == "eq":
                        q = q.eq(col, val)
                    elif op == "neq":
                        q = q.neq(col, val)
                    elif op == "in":
                        q = q.in_(col, val)
                    elif op == "gte":
                        q = q.gte(col, val)
                    elif op == "lte":
                        q = q.lte(col, val)
            res = q.range(start, start + page_size - 1).execute()
            batch = res.data if res and isinstance(res.data, list) else []
        except Exception:
            break
        out.extend(batch)
        if len(batch) < page_size:
            break
        start += page_size
        if start > 200_000:
            break
    return out


def _count_exact(table: str, filters: list | None = None) -> int:
    try:
        q = supabase.table(table).select("id", count="exact").limit(1)
        if filters:
            for col, op, val in filters:
                if op == "eq":
                    q = q.eq(col, val)
                elif op == "in":
                    q = q.in_(col, val)
        res = q.execute()
        if res and res.count is not None:
            return int(res.count)
    except Exception:
        pass
    return 0


def _kpi_html(label: str, value: str, hint: str = "", variant: str = "") -> str:
    cls = f"kpi-card {variant}".strip()
    hint_html = f'<div class="kpi-hint">{hint}</div>' if hint else ""
    return (
        f'<div class="{cls}">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f"{hint_html}"
        f"</div>"
    )


def _apply_layout(fig, title: str):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Segoe UI, sans-serif", color=_PLOT_FONT, size=12),
        margin=dict(l=40, r=20, t=48, b=40),
        title=dict(text=title, font=dict(size=14, color=_PLOT_TITLE)),
        legend=dict(font=dict(color=_PLOT_FONT)),
    )
    fig.update_xaxes(
        gridcolor="rgba(128,128,128,0.2)", zerolinecolor="rgba(128,128,128,0.2)"
    )
    fig.update_yaxes(
        gridcolor="rgba(128,128,128,0.2)", zerolinecolor="rgba(128,128,128,0.2)"
    )
    return fig


def _nome_join(row_val, key="name"):
    if isinstance(row_val, dict):
        return (row_val.get(key) or row_val.get("full_name") or "").strip() or "N/D"
    return "N/D"


@st.cache_data(ttl=60)
def carregar_base_dashboard(ct_fixado: str | None = None):
    """Carrega turmas + dimensões auxiliares (cache 60s)."""
    filtros = []
    if ct_fixado:
        filtros.append(("ct_id", "eq", ct_fixado))

    turmas = _fetch_all(
        "turmas",
        "id, titulo, data_treinamento, documento_emitido, modalidade, nivel, "
        "carga_horaria, ct_id, client_id, curso_id, instrutor_id, "
        "cursos(id, name, sigla), "
        "clients(id, name, cnpj, sigla, grupo_id), "
        "instrutores(id, name), "
        "cts(id, name, full_name)",
        filters=filtros or None,
    )

    if not turmas:
        turmas = _fetch_all(
            "turmas",
            "id, titulo, data_treinamento, documento_emitido, modalidade, nivel, "
            "carga_horaria, ct_id, client_id, curso_id, instrutor_id",
            filters=filtros or None,
        )

    grupos: list[dict] = []
    try:
        res = (
            supabase.table("grupos_empresariais")
            .select("id, nome")
            .order("nome")
            .execute()
        )
        grupos = res.data if res and isinstance(res.data, list) else []
    except Exception:
        grupos = []

    return {"turmas": turmas, "grupos": grupos}


def _contagem_matriculas(turma_ids: list[str]) -> int:
    if not turma_ids:
        return 0
    total = 0
    for i in range(0, len(turma_ids), 80):
        lote = turma_ids[i : i + 80]
        total += _count_exact("matriculas", [("turma_id", "in", lote)])
    return total


def _mapa_matriculas_por_turma(turma_ids: list[str]) -> dict[str, int]:
    """Conta matrículas por turma_id (lote)."""
    contagem: dict[str, int] = {tid: 0 for tid in turma_ids}
    if not turma_ids:
        return contagem
    for i in range(0, len(turma_ids), 80):
        lote = turma_ids[i : i + 80]
        try:
            res = (
                supabase.table("matriculas")
                .select("turma_id")
                .in_("turma_id", lote)
                .execute()
            )
            for row in res.data or []:
                tid = str(row.get("turma_id") or "")
                if tid in contagem:
                    contagem[tid] += 1
        except Exception:
            pass
    return contagem


def _set_periodo(di: date, dfim: date):
    """Atualiza session_state dos date_inputs (keys dos widgets)."""
    st.session_state["dash_input_di"] = di
    st.session_state["dash_input_df"] = dfim


# ---------------------------------------------------------------------------
# Carga
# ---------------------------------------------------------------------------
_ct_user = ct_id_atual()
with st.spinner("Carregando base do painel..."):
    base = carregar_base_dashboard(_ct_user)

df = pd.DataFrame(base["turmas"] or [])
grupos = base.get("grupos") or []
mapa_grupo = {g["id"]: (g.get("nome") or "Sem nome") for g in grupos if g.get("id")}

if df.empty:
    st.info("Nenhuma turma cadastrada ainda para gerar o painel.")
    st.stop()

df["data_treinamento"] = pd.to_datetime(df["data_treinamento"], errors="coerce")
df["data_date"] = df["data_treinamento"].dt.date
df["mes_ano"] = df["data_treinamento"].dt.strftime("%m/%Y")
df["nome_curso"] = (
    df["cursos"].apply(lambda x: _nome_join(x, "name")) if "cursos" in df.columns else "N/D"
)
df["nome_empresa"] = (
    df["clients"].apply(lambda x: _nome_join(x, "name")) if "clients" in df.columns else "N/D"
)
df["grupo_id"] = (
    df["clients"].apply(lambda x: x.get("grupo_id") if isinstance(x, dict) else None)
    if "clients" in df.columns
    else None
)
df["nome_grupo"] = df["grupo_id"].map(
    lambda g: mapa_grupo.get(g) if g else "— Sem grupo —"
)
df["nome_instrutor"] = (
    df["instrutores"].apply(lambda x: _nome_join(x, "name"))
    if "instrutores" in df.columns
    else "N/D"
)
df["nome_ct"] = (
    df["cts"].apply(lambda x: _nome_join(x, "name")) if "cts" in df.columns else "N/D"
)
df["Status"] = df["documento_emitido"].map({True: "Emitido", False: "Pendente"})

# ---------------------------------------------------------------------------
# Filtros (recolhíveis)
# ---------------------------------------------------------------------------
hoje = date.today()

# defaults dos widgets de data (só na 1ª carga)
if "dash_input_di" not in st.session_state:
    st.session_state["dash_input_di"] = hoje.replace(day=1)
if "dash_input_df" not in st.session_state:
    st.session_state["dash_input_df"] = hoje

with st.expander("Filtros", expanded=True):
    c_bt1, c_bt2, c_bt3, c_bt4, c_bt5 = st.columns(5)
    with c_bt1:
        if st.button("Hoje", use_container_width=True, key="btn_dash_hoje"):
            _set_periodo(hoje, hoje)
            st.rerun()
    with c_bt2:
        if st.button("7 dias", use_container_width=True, key="btn_dash_7d"):
            _set_periodo(hoje - timedelta(days=6), hoje)
            st.rerun()
    with c_bt3:
        if st.button("Mês", use_container_width=True, key="btn_dash_mes"):
            _set_periodo(hoje.replace(day=1), hoje)
            st.rerun()
    with c_bt4:
        if st.button("Ano", use_container_width=True, key="btn_dash_ano"):
            _set_periodo(date(hoje.year, 1, 1), hoje)
            st.rerun()
    with c_bt5:
        if st.button("Tudo", use_container_width=True, key="btn_dash_tudo"):
            dmin = df["data_date"].dropna()
            _set_periodo(
                dmin.min() if len(dmin) else hoje,
                dmin.max() if len(dmin) else hoje,
            )
            st.rerun()

    c_d1, c_d2 = st.columns(2)
    with c_d1:
        data_ini = st.date_input(
            "Data início*",
            format="DD/MM/YYYY",
            key="dash_input_di",
        )
    with c_d2:
        data_fim = st.date_input(
            "Data fim*",
            format="DD/MM/YYYY",
            key="dash_input_df",
        )

    if data_ini > data_fim:
        data_ini, data_fim = data_fim, data_ini

    op_ct = sorted({n for n in df["nome_ct"].dropna().unique() if n and n != "N/D"})
    op_inst = sorted(
        {n for n in df["nome_instrutor"].dropna().unique() if n and n != "N/D"}
    )
    op_emp = sorted(
        {n for n in df["nome_empresa"].dropna().unique() if n and n != "N/D"}
    )
    op_curso = sorted(
        {n for n in df["nome_curso"].dropna().unique() if n and n != "N/D"}
    )
    op_grupo = sorted({n for n in df["nome_grupo"].dropna().unique() if n})

    c1, c2, c3 = st.columns(3)
    with c1:
        if _ct_user:
            nome_ct_fix = (
                op_ct[0] if len(op_ct) == 1 else (op_ct[0] if op_ct else "CT vinculado")
            )
            st.selectbox("CT*", [nome_ct_fix], disabled=True, key="dash_ct_fixed")
            filt_ct = [nome_ct_fix] if op_ct else []
            st.caption("CT vinculado ao seu usuário.")
        else:
            filt_ct = st.multiselect("CT*", options=op_ct, default=[], key="dash_ct")
    with c2:
        filt_inst = st.multiselect(
            "Instrutor*", options=op_inst, default=[], key="dash_inst"
        )
    with c3:
        filt_curso = st.multiselect(
            "Curso*", options=op_curso, default=[], key="dash_curso"
        )

    c4, c5 = st.columns(2)
    with c4:
        filt_emp = st.multiselect(
            "Empresa*", options=op_emp, default=[], key="dash_emp"
        )
    with c5:
        filt_grupo = st.multiselect(
            "Grupo empresarial*", options=op_grupo, default=[], key="dash_grupo"
        )

    st.caption(
        "Multiselect vazio = **todos** da dimensão. O período é sempre aplicado."
    )

# ---------------------------------------------------------------------------
# Aplicar filtros
# ---------------------------------------------------------------------------
mask = (df["data_date"] >= data_ini) & (df["data_date"] <= data_fim)
if filt_ct:
    mask &= df["nome_ct"].isin(filt_ct)
if filt_inst:
    mask &= df["nome_instrutor"].isin(filt_inst)
if filt_curso:
    mask &= df["nome_curso"].isin(filt_curso)
if filt_emp:
    mask &= df["nome_empresa"].isin(filt_emp)
if filt_grupo:
    mask &= df["nome_grupo"].isin(filt_grupo)

dff = df.loc[mask].copy()

turma_ids = [str(i) for i in dff["id"].tolist() if i]
with st.spinner("Calculando matrículas do filtro..."):
    total_matriculas = _contagem_matriculas(turma_ids)
    mapa_mat = _mapa_matriculas_por_turma(turma_ids)

total_turmas = len(dff)
emitidas = int((dff["documento_emitido"] == True).sum()) if total_turmas else 0
pendentes = int((dff["documento_emitido"] == False).sum()) if total_turmas else 0
taxa_emissao = round(100.0 * emitidas / total_turmas, 1) if total_turmas else 0.0
media_alunos = round(total_matriculas / total_turmas, 1) if total_turmas else 0.0
pend_atrasadas = (
    int(((dff["data_date"] < hoje) & (dff["documento_emitido"] == False)).sum())
    if total_turmas
    else 0
)
empresas_distintas = dff["client_id"].nunique() if total_turmas else 0

st.markdown(
    f"**Período:** {data_ini.strftime('%d/%m/%Y')} → {data_fim.strftime('%d/%m/%Y')} "
    f"· **{total_turmas}** turma(s) no filtro"
)

# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------
k1, k2, k3, k4, k5 = st.columns(5)
with k1:
    st.markdown(
        _kpi_html("Turmas", _fmt_num(total_turmas), "No filtro", "accent"),
        unsafe_allow_html=True,
    )
with k2:
    st.markdown(
        _kpi_html(
            "Matrículas", _fmt_num(total_matriculas), f"Média {media_alunos}/turma"
        ),
        unsafe_allow_html=True,
    )
with k3:
    st.markdown(
        _kpi_html("Empresas", _fmt_num(empresas_distintas), "Distintas no filtro"),
        unsafe_allow_html=True,
    )
with k4:
    st.markdown(
        _kpi_html("Taxa de emissão", f"{taxa_emissao}%", f"{emitidas} emitidas"),
        unsafe_allow_html=True,
    )
with k5:
    st.markdown(
        _kpi_html(
            "Pendências atrasadas",
            _fmt_num(pend_atrasadas),
            f"{pendentes} pendentes no total",
            "warn" if pend_atrasadas else "ok",
        ),
        unsafe_allow_html=True,
    )

if dff.empty:
    st.warning("Nenhuma turma no período/filtros selecionados.")
    st.stop()

# ---------------------------------------------------------------------------
# Gráficos
# ---------------------------------------------------------------------------
st.markdown('<div class="df-section-title">Análise de turmas</div>', unsafe_allow_html=True)

turmas_mes_ct = (
    dff.groupby(["mes_ano", "nome_ct"]).size().reset_index(name="Quantidade")
)
turmas_mes_ct["data_sort"] = pd.to_datetime(
    turmas_mes_ct["mes_ano"], format="%m/%Y", errors="coerce"
)
turmas_mes_ct = turmas_mes_ct.sort_values("data_sort")
fig_mes = px.bar(
    turmas_mes_ct,
    x="mes_ano",
    y="Quantidade",
    color="nome_ct",
    barmode="group",
    text_auto=True,
    labels={"nome_ct": "CT", "mes_ano": "Mês"},
)
_apply_layout(fig_mes, "Turmas por mês (por CT)")
fig_mes.update_layout(
    xaxis_title=None,
    yaxis_title="Quantidade",
    legend_title_text="CT",
    height=420,
    margin=dict(l=40, r=20, t=48, b=60),
)
fig_mes.update_traces(marker_line_width=0, textposition="outside")
st.plotly_chart(fig_mes, use_container_width=True)

col_g2, col_g3 = st.columns(2)

with col_g2:
    status_counts = dff["Status"].value_counts().reset_index()
    status_counts.columns = ["Status", "Quantidade"]
    fig_donut = px.pie(
        status_counts,
        values="Quantidade",
        names="Status",
        hole=0.55,
        color="Status",
        color_discrete_map={"Emitido": _OK, "Pendente": _WARN},
    )
    _apply_layout(fig_donut, "Status de documentação")
    fig_donut.update_layout(
        legend=dict(orientation="h", yanchor="bottom", y=-0.15, x=0.2)
    )
    fig_donut.update_traces(textposition="inside", textinfo="percent+label")
    st.plotly_chart(fig_donut, use_container_width=True)

with col_g3:
    top_cursos = (
        dff.groupby("nome_curso")
        .size()
        .reset_index(name="Quantidade")
        .sort_values("Quantidade", ascending=False)
        .head(10)
    )
    fig_curso = px.pie(
        top_cursos,
        values="Quantidade",
        names="nome_curso",
        hole=0.35,
    )
    _apply_layout(fig_curso, "Top cursos (turmas)")
    fig_curso.update_traces(textposition="inside", textinfo="percent+label")
    fig_curso.update_layout(
        legend=dict(orientation="h", yanchor="bottom", y=-0.35, x=0.0)
    )
    st.plotly_chart(fig_curso, use_container_width=True)

col_funil, col_side = st.columns([1.2, 1])
with col_funil:
    modalidade_counts = dff["modalidade"].fillna("N/D").value_counts().reset_index()
    modalidade_counts.columns = ["Modalidade", "Quantidade"]
    modalidade_counts = modalidade_counts.sort_values("Quantidade", ascending=False)
    fig_mod = px.funnel(
        modalidade_counts,
        x="Quantidade",
        y="Modalidade",
        color_discrete_sequence=[_BAR, _BAR2, "#5b9bd5", "#8fbfef", "#c5dff5"],
    )
    _apply_layout(fig_mod, "Distribuição por modalidade")
    fig_mod.update_layout(showlegend=False, height=380)
    st.plotly_chart(fig_mod, use_container_width=True)

with col_side:
    top_inst = (
        dff.groupby("nome_instrutor")
        .size()
        .reset_index(name="Quantidade")
        .sort_values("Quantidade", ascending=True)
        .tail(10)
    )
    fig_inst = px.bar(
        top_inst,
        y="nome_instrutor",
        x="Quantidade",
        orientation="h",
        text_auto=True,
        color_discrete_sequence=[_BAR2],
    )
    _apply_layout(fig_inst, "Top instrutores (turmas)")
    fig_inst.update_layout(xaxis_title="Quantidade", yaxis_title=None, showlegend=False)
    st.plotly_chart(fig_inst, use_container_width=True)

top_emp = (
    dff.groupby("nome_empresa")
    .size()
    .reset_index(name="Quantidade")
    .sort_values("Quantidade", ascending=True)
    .tail(10)
)
fig_emp = px.bar(
    top_emp,
    y="nome_empresa",
    x="Quantidade",
    orientation="h",
    text_auto=True,
    color_discrete_sequence=[_BAR],
)
_apply_layout(fig_emp, "Top empresas (turmas)")
fig_emp.update_layout(xaxis_title="Quantidade", yaxis_title=None, showlegend=False)
st.plotly_chart(fig_emp, use_container_width=True)

# --- Turmas x pessoas (matrículas) — barras laterais ---
dff = dff.copy()
dff["n_pessoas"] = dff["id"].astype(str).map(lambda tid: mapa_mat.get(str(tid), 0))
# agrega por título curto / curso+data para legenda legível
dff["label_turma"] = dff.apply(
    lambda r: f"{(r.get('nome_curso') or 'Curso')[:28]} · {r['data_treinamento'].strftime('%d/%m') if pd.notnull(r.get('data_treinamento')) else ''}",
    axis=1,
)
# top 15 turmas por número de pessoas
top_pessoas = (
    dff[["label_turma", "n_pessoas", "titulo"]]
    .sort_values("n_pessoas", ascending=True)
    .tail(15)
)
# se muitos zeros, ainda mostra por ordem de pessoas
fig_pessoas = px.bar(
    top_pessoas,
    y="label_turma",
    x="n_pessoas",
    orientation="h",
    text_auto=True,
    color_discrete_sequence=[_BAR2],
    hover_data={"titulo": True, "label_turma": False},
)
_apply_layout(fig_pessoas, "Turmas × número de pessoas (matrículas)")
fig_pessoas.update_layout(
    xaxis_title="Pessoas",
    yaxis_title=None,
    showlegend=False,
    height=420,
)
st.plotly_chart(fig_pessoas, use_container_width=True)

# ---------------------------------------------------------------------------
# Pendências (recolhível)
# ---------------------------------------------------------------------------
with st.expander("Turmas pendentes de documentação", expanded=True):
    st.caption(
        "Turmas do filtro com documentação **ainda não emitida**. "
        "Colunas: Data, CT, Empresa, Curso, Modalidade, Instrutor."
    )
    df_pend = dff[dff["documento_emitido"] == False].copy()
    if not df_pend.empty:
        df_pend["Data"] = df_pend["data_treinamento"].dt.strftime("%d/%m/%Y")
        df_exibicao = (
            df_pend[
                [
                    "Data",
                    "nome_ct",
                    "nome_empresa",
                    "nome_curso",
                    "modalidade",
                    "nome_instrutor",
                ]
            ]
            .rename(
                columns={
                    "nome_ct": "CT",
                    "nome_empresa": "Empresa",
                    "nome_curso": "Curso",
                    "modalidade": "Modalidade",
                    "nome_instrutor": "Instrutor",
                }
            )
            .sort_values("Data", ascending=False)
        )
        st.dataframe(
            df_exibicao, hide_index=True, use_container_width=True, height=360
        )

        resumo_emp = (
            df_pend.groupby("nome_empresa")
            .size()
            .reset_index(name="Turmas pendentes")
            .sort_values("Turmas pendentes", ascending=False)
        )
        with st.expander("Resumo: empresas com turmas pendentes", expanded=False):
            st.dataframe(resumo_emp, hide_index=True, use_container_width=True)
    else:
        st.success("Nenhuma turma pendente de documentação no filtro atual.")
