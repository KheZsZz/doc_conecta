import streamlit as str_lit
import pandas as pd
import plotly.express as px
from datetime import date, timedelta

from src.config.database import supabase

str_lit.title("📊 Painel Geral (Dashboard)")
str_lit.markdown(
    "Acompanhe os principais indicadores do seu Centro de Treinamento em tempo real."
)


def _count_exact(table: str, filters: list | None = None) -> int:
    """Contagem real via PostgREST (não limitada a 1000 linhas)."""
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
    """Busca todas as linhas paginando (Supabase/PostgREST limita 1000 por request)."""
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
        # segurança: evita loop infinito em falhas estranhas
        if start > 200_000:
            break
    return out


@str_lit.cache_data(ttl=60)
def carregar_dados_dashboard():
    # KPIs com contagem exacta (sem teto de 1000)
    total_alunos = _count_exact("alunos")
    total_empresas = _count_exact("clients")
    total_certificados = _count_exact("matriculas", [("doc_emitida", "eq", True)])
    total_matriculas = _count_exact("matriculas")
    turmas_pendentes = _count_exact("turmas", [("documento_emitido", "eq", False)])
    total_turmas = _count_exact("turmas")

    # Turmas para gráficos (paginado, passa de 1000)
    turmas = _fetch_all(
        "turmas",
        "id, titulo, data_treinamento, documento_emitido, modalidade, cursos(name)",
    )

    return {
        "total_alunos": total_alunos,
        "total_empresas": total_empresas,
        "total_certificados": total_certificados,
        "total_matriculas": total_matriculas,
        "turmas_pendentes": turmas_pendentes,
        "total_turmas": total_turmas,
        "turmas": turmas,
    }


with str_lit.spinner("Carregando indicadores..."):
    dados = carregar_dados_dashboard()

df_turmas = pd.DataFrame(dados["turmas"])

total_alunos = dados["total_alunos"]
total_empresas = dados["total_empresas"]
total_certificados = dados["total_certificados"]
turmas_pendentes = dados["turmas_pendentes"]
total_turmas = dados["total_turmas"]
total_matriculas = dados["total_matriculas"]

taxa_emissao = (
    round(100.0 * (total_turmas - turmas_pendentes) / total_turmas, 1)
    if total_turmas
    else 0.0
)

# KPIs principais
col1, col2, col3, col4 = str_lit.columns(4)
with col1:
    str_lit.metric("👥 Total de Alunos", f"{total_alunos:,}".replace(",", "."))
with col2:
    str_lit.metric("🏢 Empresas Atendidas", f"{total_empresas:,}".replace(",", "."))
with col3:
    str_lit.metric(
        "🎓 Certificados Emitidos",
        f"{total_certificados:,}".replace(",", "."),
        help="Matrículas com documento emitido (doc_emitida = true).",
    )
with col4:
    delta_cor = "inverse" if turmas_pendentes > 0 else "normal"
    str_lit.metric(
        "⚠️ Turmas Pendentes",
        f"{turmas_pendentes:,}".replace(",", "."),
        delta=f"{turmas_pendentes} sem docs",
        delta_color=delta_cor,
    )

# KPIs secundários
c5, c6, c7 = str_lit.columns(3)
with c5:
    str_lit.metric("📚 Total de Turmas", f"{total_turmas:,}".replace(",", "."))
with c6:
    str_lit.metric("🧾 Total de Matrículas", f"{total_matriculas:,}".replace(",", "."))
with c7:
    str_lit.metric("✅ Taxa de emissão (turmas)", f"{taxa_emissao}%")

str_lit.markdown("---")

if df_turmas.empty:
    str_lit.info("Nenhuma turma cadastrada ainda para gerar os gráficos.")
else:
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

    # Resumo do período atual
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

    r1, r2, r3 = str_lit.columns(3)
    with r1:
        str_lit.metric("📅 Turmas neste mês", len(df_mes))
    with r2:
        str_lit.metric("🔜 Turmas nos próximos 7 dias", len(df_proximas))
    with r3:
        str_lit.metric("⏰ Pendentes de hoje", len(pendentes_hoje))

    str_lit.markdown("---")

    col_grafico1, col_grafico2 = str_lit.columns(2)

    with col_grafico1:
        turmas_por_mes = (
            df_turmas.groupby("mes_ano").size().reset_index(name="Quantidade")
        )
        turmas_por_mes["data_sort"] = pd.to_datetime(
            turmas_por_mes["mes_ano"], format="%m/%Y", errors="coerce"
        )
        turmas_por_mes = turmas_por_mes.sort_values("data_sort")

        fig_linha = px.bar(
            turmas_por_mes,
            x="mes_ano",
            y="Quantidade",
            title="📅 Turmas Realizadas por Mês",
            text_auto=True,
            color_discrete_sequence=["#1f77b4"],
        )
        fig_linha.update_layout(xaxis_title="Mês/Ano", yaxis_title="Nº de Turmas")
        str_lit.plotly_chart(fig_linha, use_container_width=True)

    with col_grafico2:
        status_counts = df_turmas["Status"].value_counts().reset_index()
        status_counts.columns = ["Status", "Quantidade"]

        fig_donut = px.pie(
            status_counts,
            values="Quantidade",
            names="Status",
            hole=0.45,
            title="📄 Status de Emissão (Turmas)",
            color="Status",
            color_discrete_map={"Emitido": "#2ca02c", "Pendente": "#d62728"},
        )
        str_lit.plotly_chart(fig_donut, use_container_width=True)

    str_lit.markdown("---")

    col_grafico3, col_tabela = str_lit.columns([1, 1])

    with col_grafico3:
        modalidade_counts = (
            df_turmas["modalidade"].fillna("N/D").value_counts().reset_index()
        )
        modalidade_counts.columns = ["Modalidade", "Quantidade"]

        fig_modalidade = px.bar(
            modalidade_counts,
            y="Modalidade",
            x="Quantidade",
            orientation="h",
            title="📍 Distribuição por Modalidade",
            text_auto=True,
            color="Modalidade",
            color_discrete_sequence=px.colors.qualitative.Pastel,
        )
        str_lit.plotly_chart(fig_modalidade, use_container_width=True)

    with col_tabela:
        str_lit.subheader("🚨 Turmas com Pendência de Documentos")

        df_pendentes = df_turmas[df_turmas["documento_emitido"] == False].copy()

        if not df_pendentes.empty:
            df_pendentes["Data"] = df_pendentes["data_treinamento"].dt.strftime(
                "%d/%m/%Y"
            )
            df_exibicao = (
                df_pendentes[["Data", "titulo", "nome_curso"]]
                .rename(
                    columns={
                        "titulo": "Título da Turma",
                        "nome_curso": "Curso",
                    }
                )
                .sort_values("Data", ascending=False)
            )
            str_lit.dataframe(df_exibicao, hide_index=True, use_container_width=True)
        else:
            str_lit.success(
                "🎉 Nenhuma pendência! Todas as turmas já tiveram seus documentos emitidos."
            )
