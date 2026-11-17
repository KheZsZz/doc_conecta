"""Estilos globais e helpers de layout para o DocFacil Conecta."""
from __future__ import annotations

import streamlit as st


def _tema_escuro() -> bool:
    try:
        theme = getattr(st.context, "theme", None)
        if theme is None:
            return False
        return getattr(theme, "type", "light") == "dark"
    except Exception:
        return False


def aplicar_estilo_global() -> None:
    """Injeta CSS global adaptado ao tema claro ou escuro."""
    dark = _tema_escuro()

    if dark:
        text = "#e8eef5"
        muted = "#9aabbc"
        hint = "#8a9baa"
        card_bg = "rgba(255,255,255,0.05)"
        card_border = "rgba(255,255,255,0.12)"
        section_border = "rgba(255,255,255,0.14)"
        accent = "#5ba3e0"
        ok = "#3dd68c"
        warn = "#ff6b6b"
        login_title = "#e8eef5"
        login_sub = "#9aabbc"
        shadow = "0 4px 18px rgba(0, 0, 0, 0.35)"
        shadow_hover = "0 8px 28px rgba(0, 0, 0, 0.45)"
        metric_shadow = "0 2px 12px rgba(0, 0, 0, 0.28)"
    else:
        text = "#0b1f3a"
        muted = "#5b6b7c"
        hint = "#7a8a9a"
        card_bg = "#ffffff"
        card_border = "#e8eef5"
        section_border = "#e8eef5"
        accent = "#1a5f9e"
        ok = "#1e7e34"
        warn = "#c0392b"
        login_title = "#0b1f3a"
        login_sub = "#5b6b7c"
        shadow = "0 4px 16px rgba(11, 31, 58, 0.08)"
        shadow_hover = "0 8px 24px rgba(11, 31, 58, 0.14)"
        metric_shadow = "0 2px 10px rgba(11, 31, 58, 0.06)"

    st.markdown(
        f"""
<style>
  @keyframes df-fade-in {{
    from {{ opacity: 0; transform: translateY(6px); }}
    to {{ opacity: 1; transform: translateY(0); }}
  }}
  @keyframes df-success-pulse {{
    0% {{ box-shadow: 0 0 0 0 rgba(30, 126, 52, 0.35); }}
    70% {{ box-shadow: 0 0 0 10px rgba(30, 126, 52, 0); }}
    100% {{ box-shadow: 0 0 0 0 rgba(30, 126, 52, 0); }}
  }}
  @keyframes df-error-shake {{
    0%, 100% {{ transform: translateX(0); }}
    20% {{ transform: translateX(-4px); }}
    40% {{ transform: translateX(4px); }}
    60% {{ transform: translateX(-3px); }}
    80% {{ transform: translateX(3px); }}
  }}
  @keyframes df-soft-pop {{
    0% {{ transform: scale(0.98); opacity: 0.85; }}
    100% {{ transform: scale(1); opacity: 1; }}
  }}

  /* ---- Tipografia e hierarquia ---- */
  h1 {{
    font-size: 1.55rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em;
    color: {text} !important;
    margin-bottom: 0.35rem !important;
  }}
  h2, h3 {{
    color: {text} !important;
  }}
  [data-testid="stSidebar"] {{
    background: #0b1f3a;
  }}
  [data-testid="stSidebar"] * {{
    color: #e8eef5 !important;
  }}
  [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {{
    color: #e8eef5 !important;
  }}
  [data-testid="stSidebar"] .stCaption,
  [data-testid="stSidebar"] [data-testid="stCaption"] {{
    color: #9aabbc !important;
  }}
  [data-testid="stSidebar"] button {{
    background: rgba(255,255,255,0.08) !important;
    border: 1px solid rgba(255,255,255,0.15) !important;
    color: #fff !important;
    transition: background 0.2s ease, transform 0.15s ease, box-shadow 0.2s ease !important;
  }}
  [data-testid="stSidebar"] button:hover {{
    background: rgba(255,255,255,0.16) !important;
    transform: translateY(-1px);
  }}
  [data-testid="stSidebar"] button:active {{
    transform: translateY(0);
  }}
  [data-testid="stSidebarNav"] a {{
    border-radius: 8px;
    transition: background 0.15s ease;
  }}
  [data-testid="stSidebarNav"] a span {{
    color: #e8eef5 !important;
  }}

  /* ---- Botões (área principal) ---- */
  div[data-testid="stAppViewContainer"] .stButton > button,
  div[data-testid="stAppViewContainer"] .stDownloadButton > button,
  div[data-testid="stAppViewContainer"] .stFormSubmitButton > button {{
    transition:
      transform 0.15s ease,
      box-shadow 0.2s ease,
      filter 0.15s ease,
      background-color 0.15s ease !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    letter-spacing: 0.01em;
  }}
  div[data-testid="stAppViewContainer"] .stButton > button:hover,
  div[data-testid="stAppViewContainer"] .stDownloadButton > button:hover,
  div[data-testid="stAppViewContainer"] .stFormSubmitButton > button:hover {{
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(26, 95, 158, 0.22);
    filter: brightness(1.03);
  }}
  div[data-testid="stAppViewContainer"] .stButton > button:active,
  div[data-testid="stAppViewContainer"] .stDownloadButton > button:active,
  div[data-testid="stAppViewContainer"] .stFormSubmitButton > button:active {{
    transform: translateY(0);
    box-shadow: 0 1px 2px rgba(0,0,0,0.1);
  }}
  /* Primary */
  div[data-testid="stAppViewContainer"] .stButton > button[kind="primary"],
  div[data-testid="stAppViewContainer"] .stFormSubmitButton > button[kind="primary"] {{
    box-shadow: 0 2px 8px rgba(26, 95, 158, 0.28);
  }}
  div[data-testid="stAppViewContainer"] .stButton > button[kind="primary"]:hover,
  div[data-testid="stAppViewContainer"] .stFormSubmitButton > button[kind="primary"]:hover {{
    box-shadow: 0 6px 16px rgba(26, 95, 158, 0.38);
  }}

  /* ---- Cards / seções ---- */
  .df-hero {{
    background: linear-gradient(135deg, #0b1f3a 0%, #123a6b 55%, #1a5f9e 100%);
    border-radius: 16px;
    padding: 1.4rem 1.6rem 1.2rem 1.6rem;
    margin-bottom: 1.25rem;
    color: #fff;
    box-shadow: {shadow_hover};
    animation: df-fade-in 0.35s ease-out;
  }}
  .df-hero h1 {{
    margin: 0 0 0.25rem 0 !important;
    font-size: 1.55rem !important;
    font-weight: 700 !important;
    color: #fff !important;
  }}
  .df-hero p {{
    margin: 0;
    opacity: 0.88;
    font-size: 0.95rem;
    color: #fff !important;
  }}
  .df-section-title {{
    font-size: 1.05rem;
    font-weight: 700;
    color: {text};
    margin: 0.75rem 0 0.85rem 0;
    padding-bottom: 0.35rem;
    border-bottom: 2px solid {section_border};
  }}
  .df-page-subtitle {{
    color: {muted};
    font-size: 0.95rem;
    margin: -0.25rem 0 1rem 0;
  }}
  .kpi-card {{
    background: {card_bg};
    border: 1px solid {card_border};
    border-radius: 14px;
    padding: 1rem 1.1rem 0.85rem 1.1rem;
    box-shadow: {shadow};
    height: 100%;
    min-height: 104px;
    transition: box-shadow 0.2s ease, transform 0.2s ease;
    animation: df-fade-in 0.4s ease-out;
  }}
  .kpi-card:hover {{
    box-shadow: {shadow_hover};
    transform: translateY(-2px);
  }}
  .kpi-label {{
    font-size: 0.78rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: {muted};
    margin-bottom: 0.35rem;
  }}
  .kpi-value {{
    font-size: 1.75rem;
    font-weight: 700;
    color: {text};
    line-height: 1.15;
  }}
  .kpi-hint {{
    font-size: 0.78rem;
    color: {hint};
    margin-top: 0.3rem;
  }}
  .kpi-card.warn .kpi-value {{ color: {warn}; }}
  .kpi-card.ok .kpi-value {{ color: {ok}; }}
  .kpi-card.accent .kpi-value {{ color: {accent}; }}

  /* Containers com borda (listagens) */
  div[data-testid="stVerticalBlockBorderWrapper"] {{
    box-shadow: {shadow};
    border-radius: 12px !important;
    transition: box-shadow 0.2s ease, transform 0.2s ease;
    animation: df-fade-in 0.3s ease-out;
  }}
  div[data-testid="stVerticalBlockBorderWrapper"]:hover {{
    box-shadow: {shadow_hover};
  }}

  div[data-testid="stVerticalBlock"] > div[data-testid="stHorizontalBlock"] {{
    gap: 0.75rem;
  }}
  div[data-testid="stMetric"] {{
    background: {card_bg};
    border: 1px solid {card_border};
    border-radius: 12px;
    padding: 0.75rem 0.9rem;
    box-shadow: {metric_shadow};
    transition: box-shadow 0.2s ease, transform 0.2s ease;
  }}
  div[data-testid="stMetric"]:hover {{
    box-shadow: {shadow};
    transform: translateY(-1px);
  }}

  /* ---- Feedback: sucesso / erro / info / warning ---- */
  div[data-testid="stAlert"] {{
    border-radius: 10px !important;
    animation: df-soft-pop 0.25s ease-out;
  }}
  /* success */
  div[data-testid="stAlert"]:has([data-testid="stMarkdownContainer"]) {{
    /* fallback geral */
  }}
  .stSuccess, div[data-baseweb="notification"][kind="positive"],
  div[data-testid="stAlert"][data-testid="stNotificationContentSuccess"],
  div[data-testid="stNotificationContentSuccess"],
  .stAlert[data-baseweb="notification"] {{
    /* Streamlit varia o DOM; mira pelo tipo via role/cor */
  }}
  div[data-testid="stAlert"] {{
    box-shadow: {metric_shadow};
  }}
  /* Animação quando a mensagem de sucesso aparece */
  div[data-testid="stAlert"]:has(svg) {{
    animation: df-soft-pop 0.28s ease-out, df-success-pulse 0.9s ease-out 0.1s;
  }}
  /* Erros: leve shake */
  div[role="alert"] {{
    animation: df-error-shake 0.35s ease-out;
  }}

  /* Tabs e expanders */
  button[data-baseweb="tab"] {{
    transition: color 0.15s ease, border-color 0.15s ease !important;
  }}
  div[data-testid="stExpander"] {{
    border-radius: 10px;
    box-shadow: {metric_shadow};
    transition: box-shadow 0.2s ease;
  }}
  div[data-testid="stExpander"]:hover {{
    box-shadow: {shadow};
  }}

  /* ---- Login ---- */
  .df-login-wrap {{
    max-width: 420px;
    margin: 2.5rem auto 0 auto;
    animation: df-fade-in 0.4s ease-out;
  }}
  .df-login-brand {{
    text-align: center;
    margin-bottom: 1.5rem;
  }}
  .df-login-brand h1 {{
    margin: 0.5rem 0 0.25rem 0 !important;
    color: {login_title} !important;
  }}
  .df-login-brand p {{
    color: {login_sub};
    margin: 0;
  }}

  /* Formulários com borda */
  div[data-testid="stForm"] {{
    box-shadow: {shadow};
    border-radius: 14px;
    transition: box-shadow 0.2s ease;
  }}
  div[data-testid="stForm"]:focus-within {{
    box-shadow: {shadow_hover};
  }}
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
