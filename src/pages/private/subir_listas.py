import io

import streamlit as st
import pandas as pd

from src.config.database import supabase

try:
    from src.utils.lista_lote import (
        gerar_template_excel,
        gerar_export_turmas_excel,
        processar_lista_lote,
        COLUNAS_MODELO,
    )
except Exception as e:
    st.error(f"Erro ao carregar modulo de listas: {type(e).__name__}: {e}")
    st.stop()

MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

st.title("📤 Subir Listas")
st.markdown(
    "Importe planilhas de alunos em **lote**, vinculadas pelo **ID da turma**. "
    "Campos opcionais (RG, NASC, e-mail, data) podem ficar em branco — "
    "a documentação só exibe o que estiver cadastrado."
)

# ---------------------------------------------------------------------------
# 1. Modelo para download (Excel)
# ---------------------------------------------------------------------------
st.subheader("1. Baixe o modelo")
st.caption(
    "Colunas do modelo: **" + " | ".join(COLUNAS_MODELO) + "**  \n"
    "Obrigatórios: **ID TURMA**, **NOME** e **CPF**. Os demais são opcionais."
)

st.info(
    """
**Regras de normalização automática:**
- **NOME:** maiúsculas, sem acentos (ex.: CONCEIÇÃO → CONCEICAO), sem caracteres especiais, sem espaços extras.
- **CPF:** somente números; se tiver menos de 11 dígitos, completa com zeros à esquerda.
"""
)

try:
    _bytes_modelo = gerar_template_excel()
except Exception as e:
    st.error(f"Não foi possível gerar o modelo Excel: {e}")
    _bytes_modelo = None

if _bytes_modelo:
    st.download_button(
        label="📥 Baixar modelo Excel (.xlsx)",
        data=_bytes_modelo,
        file_name="modelo_lista_alunos.xlsx",
        mime=MIME_XLSX,
        use_container_width=True,
        key="dl_modelo_lista",
    )

st.markdown("---")

# ---------------------------------------------------------------------------
# 2. Ajuda: listar IDs de turmas recentes + export Excel
# ---------------------------------------------------------------------------
with st.expander("🔎 Ver IDs das turmas recentes (para preencher a planilha)"):
    try:
        res = (
            supabase.table("turmas")
            .select("id, titulo, data_treinamento, clients(name)")
            .order("data_treinamento", desc=True)
            .limit(50)
            .execute()
        )
        if res and res.data:
            rows = []
            for t in res.data:
                rows.append(
                    {
                        "ID TURMA": t.get("id"),
                        "Título": t.get("titulo"),
                        "Data": str(t.get("data_treinamento", ""))[:10],
                        "Empresa": (t.get("clients") or {}).get("name", "—"),
                    }
                )
            df_turmas = pd.DataFrame(rows)

            try:
                bytes_turmas = gerar_export_turmas_excel(rows)
                st.download_button(
                    label="📥 Baixar lista de turmas em Excel (.xlsx)",
                    data=bytes_turmas,
                    file_name="ids_turmas.xlsx",
                    mime=MIME_XLSX,
                    use_container_width=True,
                    key="dl_export_turmas",
                )
            except Exception as e:
                st.warning(f"Não foi possível gerar o Excel das turmas: {e}")

            st.caption(
                f"**{len(rows)}** turma(s). Use o botão acima para baixar em Excel "
                "(não use export da tabela — gera CSV)."
            )
            st.table(df_turmas)
        else:
            st.info("Nenhuma turma cadastrada.")
    except Exception as e:
        st.error(f"Erro ao listar turmas: {e}")

st.markdown("---")

# ---------------------------------------------------------------------------
# 3. Upload e processamento
# ---------------------------------------------------------------------------
st.subheader("2. Envie a planilha preenchida")

arquivo = st.file_uploader(
    "Arquivo Excel (.xlsx, .xls ou .xlsm)",
    type=["xlsx", "xls", "xlsm"],
    key="upload_lista_lote",
)

if arquivo:
    try:
        df_preview = pd.read_excel(arquivo)

        st.write("📊 Pré-visualização (primeiras linhas):")
        st.dataframe(df_preview.head(10), use_container_width=True)

        st.info(
            f"**{len(df_preview)}** linha(s) detectada(s). "
            "Colunas encontradas: " + ", ".join(str(c) for c in df_preview.columns)
        )

        if st.button(
            "🚀 Processar e matricular em lote",
            type="primary",
            use_container_width=True,
        ):
            with st.spinner("Processando planilha e matriculando alunos..."):
                resultado = processar_lista_lote(
                    arquivo_bytes=arquivo.getvalue(),
                    nome_arquivo=arquivo.name,
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
                    f"⚠️ Avisos / linhas ignoradas ({len(resultado['erros'])})",
                    expanded=True,
                ):
                    for err in resultado["erros"]:
                        st.write(f"- {err}")

    except Exception as e:
        st.error(f"Erro ao ler o arquivo: {e}")
