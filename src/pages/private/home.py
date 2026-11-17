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
  <p>Visão consolidada de turmas, matrículas e pendências de documentação.</p>
</div>
""",
    unsafe_allow_html=True,
)


def _fmt_num(n: int | float) -> str:
    return f"{int(n):,}".replace(",", ".")


def _count_exact(table: str, filters: list | None = None) -> int:
    try:
        q = supabase.table(table).select("id", count="exact").limit(1)
        if filters:
            for col, op, val in filters:
                if op == "eq":
                    q = q.eq(col, val)
                elif op == "neq":
                    q = q.neq(col, val)
                elif op == "in":
                    q = q.in_(col, val)
        res = q.execute()
        if res and res.count is not None:
            return int(res.count)
    except Exception:
        pass
    return 0


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


@st.cache_data(ttl=60)
def carregar_dados_dashboard(ct_id: str | None = None):
    filtros_turma: list = []
    if ct_id:
        filtros_turma.append(("ct_id", "eq", ct_id))

    total_turmas = _count_exact("turmas", filtros_turma or None)
    turmas_pendentes = _count_exact(
        "turmas",
        (filtros_turma + [("documento_emitido", "eq", False)]) or None,
    )

    turmas = _fetch_all(
        "turmas",
        "id, titulo, data_treinamento, documento_emitido, modalidade, ct_id, client_id, cursos(name)",
        filters=filtros_turma or None,
    )

    if ct_id:
        client_ids = list({str(t["client_id"]) for t in turmas if t.get("client_id")})
        total_empresas = len(client_ids)
        turma_ids = [str(t["id"]) for t in turmas if t.get("id")]
        total_matriculas = 0
        for i in range(0, len(turma_ids), 80):
            lote = turma_ids[i : i + 80]
            total_matriculas += _count_exact("matriculas", [("turma_id", "in", lote)])
        ct_nome = ""
        try:
            res = (
                supabase.table("cts")
                .select("name, full_name")
                .eq("id", ct_id)
                .limit(1)
                .execute()
            )
            if res and res.data:
                ct_nome = (
                    res.data[0].get("name") or res.data[0].get("full_name") or ""
                ).strip()
        except Exception:
            pass
    else:
        total_empresas = _count_exact("clients")
        total_matriculas = _count_exact("matriculas")
        ct_nome = ""

    return {
        "total_empresas": total_empresas,
        "total_matriculas": total_matriculas,
        "turmas_pendentes": turmas_pendentes,
        "total_turmas": total_turmas,
        "turmas": turmas,
        "ct_id": ct_id,
        "ct_nome": ct_nome,
    }


_ct_dash = ct_id_atual()
with st.spinner("Atualizando indicadores..."):
    dados = carregar_dados_dashboard(_ct_dash)

if dados.get("ct_id"):
    _nome_ct = dados.get("ct_nome") or "seu CT"
    st.caption(f"Dashboard filtrado pelo CT **{_nome_ct}** (vinculado ao seu usuário).")
else:
    st.caption("Dashboard geral — todos os CTs.")

df_turmas = pd.DataFrame(dados["turmas"])
total_empresas = dados["total_empresas"]
total_matriculas = dados["total_matriculas"]
turmas_pendentes = dados["turmas_pendentes"]
total_turmas = dados["total_turmas"]

taxa_emissao = (
    round(100.0 * (total_turmas - turmas_pendentes) / total_turmas, 1)
    if total_turmas
    else 0.0
)

k1, k2, k3, k4 = st.columns(4)
with k1:
    st.markdown(
        _kpi_html("Matrículas", _fmt_num(total_matriculas), "Participações em turmas", "accent"),
        unsafe_allow_html=True,
    )
with k2:
    st.markdown(
        _kpi_html(
            "Empresas",
            _fmt_num(total_empresas),
            "Com turmas neste CT" if dados.get("ct_id") else "Clientes cadastrados",
        ),
        unsafe_allow_html=True,
    )
with k3:
    st.markdown(
        _kpi_html("Turmas", _fmt_num(total_turmas), f"Taxa de emissão {taxa_emissao}%"),
        unsafe_allow_html=True,
    )
with k4:
    st.markdown(
        _kpi_html(
            "Pendentes de docs",
            _fmt_num(turmas_pendentes),
            "Turmas sem documentação",
            "warn" if turmas_pendentes else "ok",
        ),
        unsafe_allow_html=True,
    )

st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)

if df_turmas.empty:
    st.info("Nenhuma turma cadastrada ainda para gerar os gráficos.")
    st.stop()

df_turmas["data_treinamento"] = pd.to_datetime(
    df_turmas["data_treinamento"], errors="coerce"
)
df_turmas["mes_ano"] = df_turmas["data_treinamento"].dt.strftime("%m/%Y")
df_turmas["nome_curso"] = df_turmas["cursos"].apply(
    lambda x: x["name"] if isinstance(x, dict) else "N/D"
)
df_turmas["Status"] = df_turmas["documento_emitido"].map(
    {True: "Emitido", False: "Pendente"}
)

hoje = date.today()
inicio_mes = hoje.replace(day=1)
em_7_dias = hoje + timedelta(days=7)

df_mes = df_turmas[
    (df_turmas["data_treinamento"].dt.date >= inicio_mes)
    & (df_turmas["data_treinamento"].dt.date <= hoje)
]
df_proximas = df_turmas[
    (df_turmas["data_treinamento"].dt.date >= hoje)
    & (df_turmas["data_treinamento"].dt.date <= em_7_dias)
]
pendentes_hoje = df_turmas[
    (df_turmas["data_treinamento"].dt.date == hoje)
    & (df_turmas["documento_emitido"] == False)
]

st.markdown('<div class="df-section-title">Operação no período</div>', unsafe_allow_html=True)
p1, p2, p3, p4 = st.columns(4)
with p1:
    st.metric("Turmas neste mês", len(df_mes))
with p2:
    st.metric("Próximos 7 dias", len(df_proximas))
with p3:
    st.metric("Pendentes hoje", len(pendentes_hoje))
with p4:
    st.metric("Taxa de emissão", f"{taxa_emissao}%")

st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
st.markdown('<div class="df-section-title">Análise de turmas</div>', unsafe_allow_html=True)

col_g1, col_g2 = st.columns(2)

with col_g1:
    turmas_por_mes = df_turmas.groupby("mes_ano").size().reset_index(name="Quantidade")
    turmas_por_mes["data_sort"] = pd.to_datetime(
        turmas_por_mes["mes_ano"], format="%m/%Y", errors="coerce"
    )
    turmas_por_mes = turmas_por_mes.sort_values("data_sort")

    fig_mes = px.bar(
        turmas_por_mes,
        x="mes_ano",
        y="Quantidade",
        text_auto=True,
        color_discrete_sequence=[_BAR],
    )
    _apply_layout(fig_mes, "Turmas por mês")
    fig_mes.update_layout(xaxis_title=None, yaxis_title="Quantidade", showlegend=False)
    fig_mes.update_traces(marker_line_width=0, textposition="outside")
    st.plotly_chart(fig_mes, use_container_width=True)

with col_g2:
    status_counts = df_turmas["Status"].value_counts().reset_index()
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

col_g3, col_tab = st.columns([1, 1.15])

with col_g3:
    modalidade_counts = (
        df_turmas["modalidade"].fillna("N/D").value_counts().reset_index()
    )
    modalidade_counts.columns = ["Modalidade", "Quantidade"]
    modalidade_counts = modalidade_counts.sort_values("Quantidade", ascending=True)

    fig_mod = px.bar(
        modalidade_counts,
        y="Modalidade",
        x="Quantidade",
        orientation="h",
        text_auto=True,
        color_discrete_sequence=[_BAR2],
    )
    _apply_layout(fig_mod, "Distribuição por modalidade")
    fig_mod.update_layout(
        xaxis_title="Quantidade", yaxis_title=None, showlegend=False
    )
    st.plotly_chart(fig_mod, use_container_width=True)

with col_tab:
    st.markdown("**Pendências de documentação**")
    df_pendentes = df_turmas[df_turmas["documento_emitido"] == False].copy()

    if not df_pendentes.empty:
        df_pendentes["Data"] = df_pendentes["data_treinamento"].dt.strftime("%d/%m/%Y")
        df_exibicao = (
            df_pendentes[["Data", "titulo", "nome_curso", "modalidade"]]
            .rename(
                columns={
                    "titulo": "Turma",
                    "nome_curso": "Curso",
                    "modalidade": "Modalidade",
                }
            )
            .sort_values("Data", ascending=False)
        )
        st.dataframe(
            df_exibicao,
            hide_index=True,
            use_container_width=True,
            height=320,
        )
    else:
        st.success("Nenhuma pendência. Todas as turmas com documentação emitida.")
