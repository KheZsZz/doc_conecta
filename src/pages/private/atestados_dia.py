import io
import zipfile
from datetime import date
import streamlit as st
from src.config.database import (  # Utilitário de conexão existente
    get_connection,
)
from src.utils.atestado import (  # Gerador de PDF de atestado do projeto
    gerar_pdf_atestado,
)


def render_pagina_atestados_dia():
    st.title("📄 Atestados do Dia")
    st.markdown(
        "Gere e baixe em lote todos os atestados emitidos no dia selecionado."
    )

    # Seleção de data (padrão: hoje)
    data_filtro = st.date_input("Data de referência:", value=date.today())

    if st.button("🚀 Processar e Gerar Atestados em Lote", type="primary"):
        with st.spinner("Buscando registros e gerando PDFs..."):
            # 1. Consulta ao banco de dados filtrando pela data selecionada
            conn = get_connection()
            cursor = conn.cursor()

            query = """
                SELECT 
                    a.id AS aluno_id,
                    a.nome AS nome_aluno,
                    a.cpf,
                    c.nome AS nome_curso,
                    t.data_inicio,
                    t.data_fim
                FROM matriculas m
                JOIN alunos a ON m.aluno_id = a.id
                JOIN turmas t ON m.turma_id = t.id
                JOIN cursos c ON t.curso_id = c.id
                WHERE DATE(m.created_at) = %s
            """
            cursor.execute(query, (data_filtro,))
            registros = cursor.fetchall()
            conn.close()

            if not registros:
                st.warning("Nenhum atestado encontrado para a data informada.")
                return

            # 2. Criação do arquivo ZIP em memória
            buffer_zip = io.BytesIO()

            with zipfile.ZipFile(
                buffer_zip, "w", zipfile.ZIP_DEFLATED
            ) as zip_file:
                for reg in registros:
                    aluno_id, nome, cpf, curso, data_inicio, data_fim = reg

                    dados_atestado = {
                        "nome": nome,
                        "cpf": cpf,
                        "curso": curso,
                        "data_inicio": data_inicio,
                        "data_fim": data_fim,
                        "data_emissao": data_filtro.strftime("%d/%m/%Y"),
                    }

                    # Gera o PDF usando o template e regras do atestado.py
                    pdf_bytes = gerar_pdf_atestado(dados_atestado)

                    # Sanitiza o nome do arquivo individual
                    nome_limpo = "".join(
                        c if c.isalnum() else "_" for c in nome
                    )
                    nome_arquivo = f"atestado_{nome_limpo}_{cpf}.pdf"

                    # Adiciona ao pacote ZIP
                    zip_file.writestr(nome_arquivo, pdf_bytes)

            buffer_zip.seek(0)

            st.success(
                f"✅ Sucesso! {len(registros)} atestado(s) gerado(s) com sucesso."
            )

            # 3. Botão de Download do arquivo final
            st.download_button(
                label="📦 Baixar Todos os Atestados (.ZIP)",
                data=buffer_zip.getvalue(),
                file_name=f"atestados_{data_filtro.strftime('%Y_%m_%d')}.zip",
                mime="application/zip",
            )


if __name__ == "__main__":
    render_pagina_atestados_dia()