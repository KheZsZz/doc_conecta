from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.config.database import supabase

# ---------------------------------------------------------------------------
# Estilo
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
  .dash-hero {
    background: linear-gradient(135deg, #0b1f3a 0%, #123a6b 55%, #1a5f9e 100%);
    border-radius: 16px;
    padding: 1.4rem 1.6rem 1.2rem 1.6rem;
    margin-bottom: 1.25rem;
    color: #fff;
    box-shadow: 0 8px 24px rgba(11, 31, 58, 0.25);
  }
  .dash-hero h1 {
    margin: 0 0 0.25rem 0;
    font-size: 1.55rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: #fff !important;
  }
  .dash-hero p {
    margin: 0;
    opacity: 0.85;
    font-size: 0.95rem;
  }
  .kpi-card {
    background: #ffffff;
    border: 1px solid #e8eef5;
    border-radius: 14px;
    padding: 1rem 1.1rem 0.85rem 1.1rem;
    box-shadow: 0 2px 10px rgba(15, 40, 80, 0.06);
    height: 100%;
    min-height: 104px;
  }
  .kpi-label {
    font-size: 0.78rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #5b6b7c;
    margin-bottom: 0.35rem;
  }
  .kpi-value {
    font-size: 1.75rem;
    font-weight: 700;
    color: #0b1f3a;
    line-height: 1.15;
  }
  .kpi-hint {
    font-size: 0.78rem;
    color: #7a8a9a;
    margin-top: 0.3rem;
  }
  .kpi-card.warn .kpi-value { color: #c0392b; }
  .kpi-card.ok .kpi-value { color: #1e7e34; }
  .kpi-card.accent .kpi-value { color: #1a5f9e; }
  .section-title {
    font-size: 1.05rem;
    font-weight: 700;
    color: #0b1f3a;
    margin: 0.4rem 0 0.85rem 0;
    padding-bottom: 0.35rem;
    border-bottom: 2px solid #e8eef5;
  }
  div[data-testid="stMetric"] {
    background: #fff;
    border: 1px solid #e8eef5;
    border-radius: 12px;
    padding: 0.75rem 0.9rem;
  }
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="dash-hero">
  <h1>Painel operacional</h1>
  <p>Visão consolidada de turmas, matrículas e pendências de documentação.</p>
</div>
""",
    unsafe_allow_html=True,
)


def _fmt_num(n: int | float) -> str:
    return f"{int(n):,}".replace(",", ".")


def _count_exact(table: str, filters: list | None = None) -> int:
    """Contagem real via PostgREST (sem teto de 1000 linhas)."""
    try:
        q = supabase.table(table).select("id", count="exact").limit(1)
        if filters:
            for col, op, val in filters:
                if op == "eq":
                    q = q.eq(col, val)
                elif op == "neq":
                    q = q.neq(col, val)
        res = q.execute()
        if res and res.count is not None:
            return int(res.count)
    except Exception:
        pass
    return 0


def _fetch_all(table: str, select: str, page_size: int = 1000) -> list:
    out: list = []
    start = 0
    while True:
        try:
            res = (
                supabase.table(table)
                .select(select)
                .range(start, start + page_size - 1)
                .execute()
            )
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


@st.cache_data(ttl=60)
def carregar_dados_dashboard():
    total_empresas = _count_exact("clients")
    total_matriculas = _count_exact("matriculas")
    turmas_pendentes = _count_exact("turmas", [("documento_emitido", "eq", False)])
    total_turmas = _count_exact("turmas")

    turmas = _fetch_all(
        "turmas",
        "id, titulo, data_treinamento, documento_emitido, modalidade, cursos(name)",
    )

    return {
        "total_empresas": total_empresas,
        "total_matriculas": total_matriculas,
        "turmas_pendentes": turmas_pendentes,
        "total_turmas": total_turmas,
        "turmas": turmas,
    }


with st.spinner("Atualizando indicadores..."):
    dados = carregar_dados_dashboard()

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

# ---- KPIs principais ----
k1, k2, k3, k4 = st.columns(4)
with k1:
    st.markdown(
        _kpi_html("Matrículas", _fmt_num(total_matriculas), "Participações em turmas", "accent"),
        unsafe_allow_html=True,
    )
with k2:
    st.markdown(
        _kpi_html("Empresas", _fmt_num(total_empresas), "Clientes cadastrados"),
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

st.markdown('<div class="section-title">Operação no período</div>', unsafe_allow_html=True)
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
st.markdown('<div class="section-title">Análise de turmas</div>', unsafe_allow_html=True)

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, Segoe UI, sans-serif", color="#334",
              size=12),
    margin=dict(l=40, r=20, t=48, b=40),
    title=dict(font=dict(size=14, color="#0b1f3a")),
)

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
        color_discrete_sequence=["#1a5f9e"],
    )
    fig_mes.update_layout(
        **PLOTLY_LAYOUT,
        title="Turmas por mês",
        xaxis_title=None,
        yaxis_title="Quantidade",
        showlegend=False,
    )
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
        color_discrete_map={"Emitido": "#2e8b57", "Pendente": "#c0392b"},
    )
    fig_donut.update_layout(
        **PLOTLY_LAYOUT,
        title="Status de documentação",
        legend=dict(orientation="h", yanchor="bottom", y=-0.15, x=0.2),
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
        color_discrete_sequence=["#3d7ab5"],
    )
    fig_mod.update_layout(
        **PLOTLY_LAYOUT,
        title="Distribuição por modalidade",
        xaxis_title="Quantidade",
        yaxis_title=None,
        showlegend=False,
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
