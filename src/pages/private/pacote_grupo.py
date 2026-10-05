from datetime import date

import streamlit as st

from src.auth.permissions import exigir_permissao
from src.utils.pacote_grupo import (
    empresas_do_grupo,
    gerar_pacote_grupo,
    listar_grupos,
    responsavel_padrao,
    turmas_do_periodo,
)

exigir_permissao("pacote_grupo")

st.title("📦 Pacote por Grupo / Período")
st.markdown(
    "Gera um **ZIP** com a documentação de todas as turmas de um "
    "**grupo empresarial** em um intervalo de datas (mês ou ano)."
)

grupos = listar_grupos()
if not grupos:
    st.warning(
        "Nenhum grupo empresarial cadastrado. "
        "Crie um em **Empresas → Grupos Empresariais** e vincule as unidades."
    )
    st.stop()

nome_para_id = {g.get("nome") or str(g.get("id")): g["id"] for g in grupos}
grupo_nome = st.selectbox("Grupo empresarial*", options=list(nome_para_id.keys()))
grupo_id = nome_para_id[grupo_nome]

empresas = empresas_do_grupo(grupo_id)
if not empresas:
    st.warning(
        f"O grupo **{grupo_nome}** não tem empresas vinculadas. "
        "Edite as empresas e escolha este grupo."
    )
    st.stop()

with st.expander(f"Empresas do grupo ({len(empresas)})", expanded=False):
    for e in empresas:
        unidade = e.get("sigla") or ""
        extra = f" · {unidade}" if unidade else ""
        st.caption(f"- {e.get('name')}{extra} — CNPJ {e.get('cnpj') or '—'}")

col_a, col_b = st.columns(2)
with col_a:
    data_inicio = st.date_input(
        "Data início*",
        value=date(date.today().year, 1, 1),
        format="DD/MM/YYYY",
    )
with col_b:
    data_fim = st.date_input(
        "Data fim*",
        value=date.today(),
        format="DD/MM/YYYY",
    )

if data_inicio > data_fim:
    st.error("A data início não pode ser maior que a data fim.")
    st.stop()

# Atalhos de período
c1, c2, c3 = st.columns(3)
with c1:
    if st.button("Este mês", use_container_width=True):
        hoje = date.today()
        st.session_state["pkg_di"] = date(hoje.year, hoje.month, 1)
        st.session_state["pkg_df"] = hoje
        st.rerun()
with c2:
    if st.button("Este ano", use_container_width=True):
        hoje = date.today()
        st.session_state["pkg_di"] = date(hoje.year, 1, 1)
        st.session_state["pkg_df"] = hoje
        st.rerun()
with c3:
    if st.button("Ano anterior", use_container_width=True):
        y = date.today().year - 1
        st.session_state["pkg_di"] = date(y, 1, 1)
        st.session_state["pkg_df"] = date(y, 12, 31)
        st.rerun()

# Aplica atalhos se gravados (próximo load — date_input já tem value; atalhos
# via session e widgets separados é limitado no Streamlit; datas manuais bastam)

st.markdown("**Documentos a incluir**")
ocol1, ocol2, ocol3 = st.columns(3)
with ocol1:
    opt_atestado = st.checkbox("Atestado (se o curso exigir)", value=True)
    opt_cert_emp = st.checkbox("Certificado da empresa", value=True)
with ocol2:
    opt_cert_alunos = st.checkbox("Certificados individuais", value=True)
    opt_carteirinhas = st.checkbox("Carteirinhas", value=True)
with ocol3:
    opt_lista = st.checkbox("Lista de presença", value=True)

client_ids = [e["id"] for e in empresas if e.get("id")]
empresas_por_id = {e["id"]: e for e in empresas if e.get("id")}

turmas = turmas_do_periodo(client_ids, data_inicio, data_fim)

st.subheader(
    f"Turmas no período: **{len(turmas)}** "
    f"({data_inicio.strftime('%d/%m/%Y')} → {data_fim.strftime('%d/%m/%Y')})"
)

if not turmas:
    st.info("Nenhuma turma encontrada para este grupo no período selecionado.")
    st.stop()

preview = []
for t in turmas:
    emp = empresas_por_id.get(t.get("client_id")) or {}
    preview.append(
        {
            "Data": str(t.get("data_treinamento") or "")[:10],
            "Turma": t.get("titulo") or "",
            "Empresa": emp.get("name") or "",
            "Unidade": emp.get("sigla") or "",
            "Emitido": "Sim" if t.get("documento_emitido") else "Não",
        }
    )

# data BR no preview
from datetime import datetime as _dt

for row in preview:
    try:
        row["Data"] = _dt.strptime(row["Data"], "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        pass

st.dataframe(preview, use_container_width=True, hide_index=True)

ss_zip = "pacote_grupo_zip"
ss_meta = "pacote_grupo_meta"
ss_nome = "pacote_grupo_nome"

if st.session_state.get(ss_zip):
    meta = st.session_state.get(ss_meta) or {}
    st.success(
        f"✅ Pacote pronto: **{meta.get('total_docs', 0)}** documento(s) "
        f"em **{meta.get('total_turmas', 0)}** turma(s)."
    )
    if meta.get("erros"):
        with st.expander("Avisos / falhas", expanded=False):
            for e in meta["erros"]:
                st.write(f"- {e}")
    st.download_button(
        "📥 Baixar pacote (ZIP)",
        data=st.session_state[ss_zip],
        file_name=st.session_state.get(ss_nome) or "pacote_grupo.zip",
        mime="application/zip",
        use_container_width=True,
        key="dl_pacote_persist",
    )

if st.button(
    "🚀 Gerar pacote de documentação",
    type="primary",
    use_container_width=True,
):
    with st.spinner(
        f"Gerando documentação de {len(turmas)} turma(s)... pode levar alguns minutos."
    ):
        try:
            zip_bytes, meta = gerar_pacote_grupo(
                grupo_nome=grupo_nome,
                turmas=turmas,
                empresas_por_id=empresas_por_id,
                dados_resp=responsavel_padrao(),
                incluir_atestado=opt_atestado,
                incluir_cert_empresa=opt_cert_emp,
                incluir_cert_alunos=opt_cert_alunos,
                incluir_carteirinhas=opt_carteirinhas,
                incluir_lista=opt_lista,
            )
        except Exception as e:
            st.error(f"Erro ao gerar pacote: {e}")
            st.stop()

    if meta.get("total_docs", 0) == 0:
        st.error("Nenhum documento foi gerado.")
        if meta.get("erros"):
            for e in meta["erros"]:
                st.write(f"- {e}")
        st.stop()

    nome_zip = (
        f"pacote_{grupo_nome.replace(' ', '_')}_"
        f"{data_inicio.strftime('%Y%m%d')}_{data_fim.strftime('%Y%m%d')}.zip"
    )
    st.session_state[ss_zip] = zip_bytes
    st.session_state[ss_meta] = meta
    st.session_state[ss_nome] = nome_zip

    st.success(
        f"✅ **{meta['total_docs']}** documento(s) gerados "
        f"para **{meta['total_turmas']}** turma(s)."
    )
    if meta.get("resumo"):
        st.dataframe(meta["resumo"], use_container_width=True, hide_index=True)
    if meta.get("erros"):
        with st.expander("Avisos / falhas", expanded=True):
            for e in meta["erros"]:
                st.write(f"- {e}")

    st.download_button(
        "📥 Baixar pacote (ZIP)",
        data=zip_bytes,
        file_name=nome_zip,
        mime="application/zip",
        use_container_width=True,
        key="dl_pacote_new",
    )
