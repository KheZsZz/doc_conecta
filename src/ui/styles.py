"""Estilos globais e helpers de layout para o DocFacil Conecta."""
from __future__ import annotations

import streamlit as st

_ consolidating: = None  # keep module simple


def aplicar_estilo_global() -> None:
    """Injeta CSS global uma vez por sessão de página."""
    st.markdown(
        """
<style>
  /* ---- Tipografia e hierarquia ---- */
  h1 {
    font-size: 1.55rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em;
    color: #0b1f3a !important;
    margin-bottom: 0.35rem !important;
  }
  h2, h3 {
    color: #0b1f3a !important;
  }
  [data-testid="stSidebar"] {
    background: #0b1f3a;
  }
  [data-testid="stSidebar"] * {
    color: #e8eef5 !important;
  }
  [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
    color: #e8eef5 !important;
  }
  [data-testid="stSidebar"] .stCaption,
  [data-testid="stSidebar"] [data-testid="stCaption"] {
    color: #9aabbc !important;
  }
  [data-testid="stSidebar"] button {
    background: rgba(255,255,255,0.08) !important;
    border: 1px solid rgba(255,255,255,0.15) !important;
    color: #fff !important;
  }
  [data-testid="stSidebar"] button:hover {
    background: rgba(255,255,255,0.16) !important;
  }
  /* Nav ativa */
  [data-testid="stSidebarNav"] a {
    border-radius: 8px;
  }
  [data-testid="stSidebarNav"] a span {
    color: #e8eef5 !important;
  }

  /* ---- Cards / seções ---- */
  .df-hero {
    background: linear-gradient(135deg, #0b1f3a 0%, #123a6b 55%, #1a5f9e 100%);
    border-radius: 16px;
    padding: 1.4rem 1.6rem 1.2rem 1.6rem;
    margin-bottom: 1.25rem;
    color: #fff;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);
  }
  .df-hero h1 {
    margin: 0 0 0.25rem 0 !important;
    font-size: 1.55rem !important;
    font-weight: 700 !important;
    color: #fff !important;
  }
  .df-hero p {
    margin: 0;
    opacity: 0.88;
    font-size: 0.95rem;
    color: #fff !important;
  }
  .df-section-title {
    font-size: 1.05rem;
    font-weight: 700;
    color: #0b1f3a;
    margin: 0.75rem 0 0.85rem 0;
    padding-bottom: 0.35rem;
    border-bottom: 2px solid #e8eef5;
  }
  .df-page-subtitle {
    color: #5b6b7c;
    font-size: 0.95rem;
    margin: -0.25rem 0 1rem 0;
  }
  .kpi-card {
    background: #ffffff;
    border: 1px solid #e8eef5;
    border-radius: 14px;
    padding: 1rem 1.1rem 0.85rem 1.1rem;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.06);
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

  /* ---- Espaçamento de formulários ---- */
  div[data-testid="stVerticalBlock"] > div[data-testid="stHorizontalBlock"] {
    gap: 0.75rem;
  }
  div[data-testid="stMetric"] {
    background: #ffffff;
    border: 1px solid #e8eef5;
    border-radius: 12px;
    padding: 0.75rem 0.9rem;
  }

  /* ---- Login ---- */
  .df-login-wrap {
    max-width: 420px;
    margin: 2.5rem auto 0 auto;
  }
  .df-login-brand {
    text-align: center;
    margin-bottom: 1.5rem;
  }
  .df-login-brand h1 {
    margin: 0.5rem 0 0.25rem 0 !important;
    color: #0b1f3a !important;
  }
  .df-login-brand p {
    color: #5b6b7c;
    margin: 0;
  }
</style>
""",
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str | None = None) -> None:
    """Título padronizado de página."""
    st.title(title)
    if subtitle:
        st.markdown(
            f'<p class="df-page-subtitle">{subtitle}</p>',
            unsafe_allow_html=True,
        )
