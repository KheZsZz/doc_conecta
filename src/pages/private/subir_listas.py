import streamlit as st
import pandas as pd
from datetime import datetime

from src.config.database import supabase
from src.auth.permissions import exigir_permissao

exigir_permissao("subir_listas")

try:
    from src.utils.lista_lote import (
        gerar_template_excel,
        gerar_template_excel_chave,
        processar_lista_lote,
        processar_lista_lote_por_chave,
    )
except Exception as e:
    st.error(f"Erro ao carregar modulo de listas: {type(e).__name__}: {e}")
    st.stop()

MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MAX_UPLOAD_MB = 5
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

st.title("Subir Listas")

tab_id, tab_chave = st.tabs(["ID da turma", "CNPJ + Data + Unidade"])


def _usuario_log() -> dict:
    u = st.session_state.get("user")
    perfil = st.session_state.get("perfil") or {}
    return {
        "user_id": getattr(u, "id", None) or perfil.get("id"),
        "email": getattr(u, "email", None) or perfil.get("email"),
        "nome": (getattr(u, "user_metadata", None) or {}).get("nome")
        or perfil.get("nome"),
    }


def _log_importacao(
    origem: str,
    nome_arquivo: str,
    ok: bool,
    alunos: int,
    matriculas: int,
    mensagem: str,
) -> None:
    meta = _usuario_log()
    payload = {
        "origem": origem,
        "arquivo": (nome_arquivo or "")[:200],
        "sucesso": bool(ok),
        "alunos_processados": int(alunos or 0),
        "matriculas_criadas": int(matriculas or 0),
        "mensagem": (mensagem or "")[:500],
        "user_id": meta.get("user_id"),
        "user_email": meta.get("email"),
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    try:
        supabase.table("import_logs").insert(payload).execute()
    except Exception:
        # tabela opcional até rodar o SQL de hardening
        pass


def _bloco_upload_e_processar(processar_fn, key_prefix: str):
    arquivo = st.file_uploader(
        f"Arquivo Excel (.xlsx, máx. {MAX_UPLOAD_MB} MB)",
        type=["xlsx"],
        key=f"upload_{key_prefix}",
    )
    if not arquivo:
        return

    data = arquivo.getvalue()
    if len(data) > MAX_UPLOAD_BYTES:
        st.error(f"Arquivo acima do limite de {MAX_UPLOAD_MB} MB.")
        return
    if not (arquivo.name or "").lower().endswith(".xlsx"):
        st.error("Envie apenas arquivos .xlsx.")
        return

    try:
        df_preview = pd.read_excel(data, engine="openpyxl")
        st.write("Pré-visualização (primeiras linhas):")
        st.dataframe(df_preview.head(10), use_container_width=True)
        st.info(
            f"**{len(df_preview)}** linha(s). Colunas: "
            + ", ".join(str(c) for c in df_preview.columns)
        )

        if st.button(
            "Processar e matricular em lote",
            type="primary",
            use_container_width=True,
            key=f"btn_{key_prefix}",
        ):
            with st.spinner("Processando planilha e matriculando alunos..."):
                resultado = processar_fn(
                    arquivo_bytes=data,
                    nome_arquivo=arquivo.name,
                )

            _log_importacao(
                origem=f"subir_listas:{key_prefix}",
                nome_arquivo=arquivo.name,
                ok=bool(resultado.get("sucesso")),
                alunos=resultado.get("alunos_processados") or 0,
                matriculas=resultado.get("matriculas_criadas") or 0,
                mensagem=resultado.get("mensagem") or "",
            )

            if resultado["sucesso"]:
                st.success(resultado["mensagem"])
                c1, c2 = st.columns(2)
                c1.metric("Alunos processados", resultado["alunos_processados"])
                c2.metric("Novas matrículas", resultado["matriculas_criadas"])
                st.balloons()
            else:
                st.error(resultado["mensagem"])

            if resultado.get("erros"):
                with st.expander(
                    f"Avisos / linhas ignoradas ({len(resultado['erros'])})",
                    expanded=True,
                ):
                    for err in resultado["erros"]:
                        st.write(f"- {err}")
    except Exception as e:
        st.error("Erro ao ler o arquivo. Verifique se é um .xlsx válido.")
        st.caption(str(e)[:200])


with tab_id:
    st.subheader("Vínculo pelo ID da turma")

    try:
        st.download_button(
            label="Baixar modelo Excel (.xlsx)",
            data=gerar_template_excel(),
            file_name="modelo_lista_alunos_id_turma.xlsx",
            mime=MIME_XLSX,
            use_container_width=True,
            key="dl_modelo_id",
        )
    except Exception as e:
        st.error(f"Não foi possível gerar o modelo: {e}")

    st.markdown("---")
    st.subheader("Envie a planilha")
    _bloco_upload_e_processar(processar_lista_lote, "id_turma")


with tab_chave:
    st.subheader("Vínculo por CNPJ + data + unidade")
    st.markdown(
        "Ideal quando as turmas foram abertas em lote: a planilha de alunos "
        "não precisa do UUID — usa os mesmos dados da empresa/unidade."
    )

    try:
        st.download_button(
            label="Baixar modelo Excel (CNPJ + Data + Unidade)",
            data=gerar_template_excel_chave(),
            file_name="modelo_lista_alunos_cnpj_unidade.xlsx",
            mime=MIME_XLSX,
            use_container_width=True,
            key="dl_modelo_chave",
        )
    except Exception as e:
        st.error(f"Não foi possível gerar o modelo: {e}")

    st.subheader("Envie a planilha")
    _bloco_upload_e_processar(processar_lista_lote_por_chave, "chave")
