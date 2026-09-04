import streamlit as str_lit
import pandas as pd
from datetime import date, datetime
from src.config.database import supabase
from src.utils.import_helper import processar_planilha_alunos
from src.utils.atestado import gerar_atestado_pdf_de_arquivo
from src.utils.certificado import gerar_certificados_pdf
from src.utils.certificado_empresa import gerar_certificado_empresa_pdf
from weasyprint import HTML

str_lit.title("📅 Abertura e Gestão de Turmas")
str_lit.markdown("Abra as turmas do centro de treinamento, importe listas de alunos e emita os documentos.")

tab_listar, tab_cadastrar = str_lit.tabs(["📋 Turmas Abertas", "➕ Abrir Nova Turma"])

MESES_PT = {
    1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril",
    5: "maio", 6: "junho", 7: "julho", 8: "agosto",
    9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro"
}

def formatar_data_extenso(data_str):
    try:
        dt = date.fromisoformat(data_str)
        mes_extenso = MESES_PT.get(dt.month, "")
        return f"Itapecerica da Serra, {dt.day:02d} de {mes_extenso} de {dt.year}"
    except Exception:
        return f"Itapecerica da Serra, {datetime.now().strftime('%d de %B de %Y')}"

# ==========================================
# 1. MODAL / POPUP DE VISUALIZAÇÃO E EDIÇÃO DE ALUNOS
# ==========================================
@str_lit.dialog("👥 Alunos Matriculados na Turma", width="large")
def modal_visualizar_alunos(turma_id, titulo_turma):
    str_lit.write(f"**Turma:** {titulo_turma}")
    str_lit.markdown("💡 *Edite o **Nome**, o **CPF** ou a **Carga Horária** diretamente na tabela abaixo e clique em Salvar Alterações.*")
    str_lit.markdown("---")
    
    try:
        res_mat = supabase.table("matriculas").select("id, data_treinamento, carga_horaria, alunos(id, name, cpf), clients(name, cnpj)").eq("turma_id", turma_id).execute()
        
        if res_mat and res_mat.data:
            dados_tabela = []
            for idx, m in enumerate(res_mat.data, 1):
                aluno = m.get("alunos") or {}
                empresa = m.get("clients") or {}
                
                cpf_limpo = aluno.get("cpf", "")
                if cpf_limpo and len(cpf_limpo) == 11:
                    cpf_fmt = f"{cpf_limpo[:3]}.{cpf_limpo[3:6]}.{cpf_limpo[6:9]}-{cpf_limpo[9:]}"
                else:
                    cpf_fmt = cpf_limpo
                
                dados_tabela.append({
                    "aluno_id": aluno.get("id"),
                    "matricula_id": m.get("id"),
                    "Nº": idx,
                    "Nome do Aluno": aluno.get("name", "Não informado"),
                    "CPF": cpf_fmt,
                    "Empresa Vínculo": empresa.get("name", "Particular / Aberta"),
                    "Carga Horária": m.get("carga_horaria", "08 Horas"),
                    "Data Matrícula/Treino": m.get("data_treinamento", ""),
                    "Data de Nascimento": m.get("data_nasc", "")
                })
                
            df_exibicao = pd.DataFrame(dados_tabela)
            
            edited_df = str_lit.data_editor(
                df_exibicao,
                column_config={
                    "aluno_id": None,
                    "matricula_id": None,
                    "Nº": str_lit.column_config.NumberColumn(disabled=True),
                    "Empresa Vínculo": str_lit.column_config.TextColumn(disabled=True),
                    "Data Matrícula/Treino": str_lit.column_config.TextColumn(disabled=True),
                    "Nome do Aluno": str_lit.column_config.TextColumn(required=True),
                    "CPF": str_lit.column_config.TextColumn(required=True),
                    "Carga Horária": str_lit.column_config.TextColumn(required=True),
                    "Data de Nascimento": str_lit.column_config.TextColumn(required=True)
                },
                disabled=["Nº", "Empresa Vínculo", "Data Matrícula/Treino"],
                hide_index=True,
                use_container_width=True,
                key=f"editor_alunos_{turma_id}"
            )
            
            str_lit.info(f"Total de alunos nesta turma: **{len(dados_tabela)}**")
            
            col1, col2 = str_lit.columns(2)
            with col1:
                if str_lit.button("💾 Salvar Alterações", type="primary", use_container_width=True):
                    alteracoes = 0
                    for index, row in edited_df.iterrows():
                        orig_row = df_exibicao.iloc[index]
                        
                        if (row["Nome do Aluno"] != orig_row["Nome do Aluno"] or 
                            row["CPF"] != orig_row["CPF"] or 
                            row["data_nasc"] != orig_row["Data de Nascimento"] or
                            row["Carga Horária"] != orig_row["Carga Horária"]):
                            
                            aluno_id = row["aluno_id"]
                            matricula_id = row["matricula_id"]
                            nome_novo = row["Nome do Aluno"]
                            cpf_novo = str(row["CPF"]).replace(".", "").replace("-", "").strip()
                            carga_nova = row["Carga Horária"]
                            data_nasc_nova = row["Data de Nascimento"]

                            supabase.table("alunos").update({
                                "name": nome_novo,
                                "cpf": cpf_novo,
                                "data_nasc": data_nasc_nova
                            }).eq("id", aluno_id).execute()
                            
                            supabase.table("matriculas").update({
                                "carga_horaria": carga_nova
                            }).eq("id", matricula_id).execute()
                            
                            alteracoes += 1
                            
                    if alteracoes > 0:
                        str_lit.success(f"✅ {alteracoes} registro(s) atualizado(s) com sucesso!")
                        str_lit.rerun()
                    else:
                        str_lit.warning("⚠️ Nenhuma alteração foi detectada.")
                        
            with col2:
                if str_lit.button("❌ Fechar", use_container_width=True):
                    str_lit.rerun()
        else:
            str_lit.info("ℹ️ Nenhum aluno matriculado nesta turma até o momento.")
            if str_lit.button("Fechar", use_container_width=True):
                str_lit.rerun()
            
    except Exception as e:
        str_lit.error(f"Erro ao carregar lista de alunos: {e}")

# ==========================================
# 2. MODAL / POPUP DE EDIÇÃO DA TURMA 
# ==========================================
@str_lit.dialog("✏️ Editar Informações da Turma", width="medium")
def modal_editar_turma(tid, titulo_atual, modalidade_atual, curso_id_atual, instrutor_id_atual, data_treinamento_atual_str, ct_id_atual):
    try:
        try:
            if data_treinamento_atual_str:
                data_treinamento_atual = date.fromisoformat(data_treinamento_atual_str)
            else:
                data_treinamento_atual = date.today()
        except ValueError:
            data_treinamento_atual = date.today()

        instr_res = supabase.table("instrutores").select("id, name").eq("is_active", True).execute()
        curso_res = supabase.table("cursos").select("id, name").execute()
        cts_res = supabase.table("cts").select("id, name, cnpj").execute()
        
        edit_instrutores = {i["name"]: i["id"] for i in instr_res.data} if instr_res.data else {}
        edit_cursos = {c["name"]: c["id"] for c in curso_res.data} if curso_res.data else {}
        
        edit_cts = {}
        if cts_res and cts_res.data:
            for ct in cts_res.data:
                ct_nome = ct.get('name', 'Centro de Treinamento')
                ct_cnpj = ct.get('cnpj', 'N/D')
                label_ct = f"{ct_nome} — CNPJ: {ct_cnpj}"
                edit_cts[label_ct] = ct["id"]
        
        with str_lit.form(f"form_edit_turma_modal_{tid}"):
            novo_titulo = str_lit.text_input("Título da Turma", value=titulo_atual)
            
            modalidades_opcoes = ["Presencial", "In Company", "Online"]
            mod_idx = modalidades_opcoes.index(modalidade_atual) if modalidade_atual in modalidades_opcoes else 0
            nova_modalidade = str_lit.selectbox("Modalidade", options=modalidades_opcoes, index=mod_idx)
            
            nova_data = str_lit.date_input("Data do Treinamento", value=data_treinamento_atual)
            
            c_keys = list(edit_cursos.keys())
            curso_idx = c_keys.index(next((k for k, v in edit_cursos.items() if v == curso_id_atual), c_keys[0])) if c_keys else 0
            novo_curso = str_lit.selectbox("Curso", options=c_keys if c_keys else ["Nenhum"], index=curso_idx)
            
            i_keys = list(edit_instrutores.keys())
            instr_idx = i_keys.index(next((k for k, v in edit_instrutores.items() if v == instrutor_id_atual), i_keys[0])) if i_keys else 0
            novo_instrutor = str_lit.selectbox("Instrutor Responsável", options=i_keys if i_keys else ["Nenhum"], index=instr_idx)
            
            ct_keys = list(edit_cts.keys())
            ct_idx = ct_keys.index(next((k for k, v in edit_cts.items() if v == ct_id_atual), ct_keys[0])) if ct_keys else 0
            novo_ct = str_lit.selectbox("Centro de Treinamento (CT)", options=ct_keys if ct_keys else ["Nenhum CT cadastrado"], index=ct_idx)
            
            salvar_edicao = str_lit.form_submit_button("💾 Salvar Alterações", type="primary", use_container_width=True)
            
            if salvar_edicao:
                payload_update = {
                    "titulo": novo_titulo.strip(),
                    "modalidade": nova_modalidade,
                    "data_treinamento": nova_data.isoformat(),
                    "curso_id": edit_cursos.get(novo_curso),
                    "instrutor_id": edit_instrutores.get(novo_instrutor),
                    "ct_id": edit_cts.get(novo_ct) if novo_ct != "Nenhum CT cadastrado" else None
                }
                supabase.table("turmas").update(payload_update).eq("id", tid).execute()
                str_lit.success("✅ Turma atualizada com sucesso!")
                str_lit.rerun()
    except Exception as e:
        str_lit.error(f"Erro ao carregar formulário de edição: {e}")

# ==========================================
# 3. MODAL / POPUP DE UPLOAD DE PLANILHA
# ==========================================
@str_lit.dialog("📥 Importar Lista de Alunos por Planilha", width="medium")
def modal_importar_planilha(tid, titulo_turma, data_turma):
    str_lit.write(f"**Turma:** {titulo_turma}")
    str_lit.markdown("---")
    
    try:
        clients_res = supabase.table("clients").select("id, name, cnpj").order("name").execute()
        empresas_opcoes = {}
        if clients_res and clients_res.data:
            for cli in clients_res.data:
                empresas_opcoes[f"{cli.get('name')} (CNPJ: {cli.get('cnpj')})"] = cli.get('id')
        
        empresa_escolhida_str = str_lit.selectbox(
            "Selecione a Empresa dos Alunos da Planilha",
            options=list(empresas_opcoes.keys()) if empresas_opcoes else ["Nenhuma empresa cadastrada"]
        )
        
        carga_horaria_padrao = str_lit.text_input("Carga Horária Padrão para os Alunos", value="08 Horas")
        
        arquivo_excel = str_lit.file_uploader(
            "Envie a planilha (Excel .xlsx ou CSV)",
            type=["xlsx", "csv"]
        )
        
        if arquivo_excel is not None:
            if str_lit.button("🚀 Processar e Importar Alunos", type="primary", use_container_width=True):
                try:
                    alunos_tratados = processar_planilha_alunos(arquivo_excel, data_turma)
                    client_id_destino = empresas_opcoes.get(empresa_escolhida_str) if empresas_opcoes else None
                    importados_count = 0
                    
                    for aluno in alunos_tratados:
                        nome_aluno = aluno["name"]
                        cpf_aluno = aluno["cpf"]
                        data_aluno_final = aluno["data_treinamento"]
                        data_nasc_aluno = aluno["data_nasc"]
                        
                        aluno_existente = supabase.table("alunos").select("id").eq("cpf", cpf_aluno).execute()
                        
                        if aluno_existente and aluno_existente.data:
                            aluno_id = aluno_existente.data[0].get("id")
                            supabase.table("alunos").update({"name": nome_aluno, "data_nasc": data_nasc_aluno}).eq("id", aluno_id).execute()
                        else:
                            novo_aluno_payload = {"name": nome_aluno, "cpf": cpf_aluno, "data_nasc": data_nasc_aluno}
                            res_novo_aluno = supabase.table("alunos").insert(novo_aluno_payload).execute()
                            if res_novo_aluno and res_novo_aluno.data:
                                aluno_id = res_novo_aluno.data[0].get("id")
                            else:
                                continue
                        
                        matricula_payload = {
                            "turma_id": tid,
                            "aluno_id": aluno_id,
                            "client_id": client_id_destino,
                            "carga_horaria": carga_horaria_padrao,
                            "data_treinamento": data_aluno_final
                        }
                        supabase.table("matriculas").insert(matricula_payload).execute()
                        importados_count += 1
                        
                    str_lit.success(f"✅ {importados_count} alunos importados com sucesso!")
                    str_lit.rerun()
                except Exception as err:
                    str_lit.error(f"❌ Erro ao processar planilha: {err}")
    except Exception as e:
        str_lit.error(f"Erro ao abrir importação: {e}")

# ==========================================
# 3.5 MODAL / POPUP DE EXCLUSÃO DE TURMA
# ==========================================
@str_lit.dialog("🗑️ Excluir Turma", width="medium")
def modal_excluir_turma(tid, titulo_turma):
    str_lit.warning(f"⚠️ Você está prestes a excluir permanentemente a turma **{titulo_turma}**.")
    str_lit.markdown(
        "Essa ação também vai remover todas as **matrículas** vinculadas a esta turma "
        "(os registros dos alunos na tabela `alunos` **não** serão apagados, apenas o vínculo com esta turma)."
    )
    str_lit.markdown("---")

    confirmar = str_lit.checkbox(
        "Sim, eu entendo e quero excluir esta turma definitivamente.",
        key=f"confirma_del_{tid}"
    )

    col1, col2 = str_lit.columns(2)
    with col1:
        if str_lit.button(
            "🗑️ Excluir Turma",
            type="primary",
            use_container_width=True,
            disabled=not confirmar,
            key=f"btn_del_turma_{tid}"
        ):
            try:
                with str_lit.spinner("Excluindo turma e matrículas..."):
                    # Remove primeiro as matrículas (preserva os alunos, apenas o vínculo com a turma)
                    supabase.table("matriculas").delete().eq("turma_id", tid).execute()
                    # Depois remove a turma
                    supabase.table("turmas").delete().eq("id", tid).execute()

                str_lit.success("✅ Turma excluída com sucesso!")
                str_lit.rerun()
            except Exception as e:
                str_lit.error(f"❌ Erro ao excluir turma: {e}")
    with col2:
        if str_lit.button("Cancelar", use_container_width=True, key=f"btn_cancel_del_{tid}"):
            str_lit.rerun()

# ==========================================
# 4. MODAL / POPUP DE EMISSÃO DE DOCUMENTOS
# ==========================================
@str_lit.dialog("📄 Emitir Documentação da Turma", width="medium")
def modal_emitir_documentacao(tid, titulo_turma, client_id, ct_id=None):
    str_lit.write(f"**Turma:** {titulo_turma}")
    str_lit.markdown("Selecione o documento desejado para emissão:")
    str_lit.markdown("---")

    # Inclusão da opção "Certificado da Empresa"
    tipo_documento = str_lit.selectbox(
        "Tipo de Documento",
        [
            "Atestado de Brigada (Empresa)",
            "Certificado da Empresa",
            "Certificados Individuais (Alunos)",
            "Lista de Presença"
        ]
    )

    str_lit.markdown("---")

    if tipo_documento == "Atestado de Brigada (Empresa)":
        str_lit.info("ℹ️ O atestado usará o template configurado e aplicará dinamicamente as colunas e a carga horária de cada matrícula.")

        if str_lit.button("🚀 Processar e Gerar Atestado", type="primary", use_container_width=True):
            try:
                with str_lit.spinner("Buscando dados e gerando atestado..."):

                    turma_res = supabase.table("turmas").select("*").eq("id", tid).single().execute()
                    turma_data = turma_res.data if turma_res and turma_res.data else {}
                    ct_id_resolvido = ct_id or turma_data.get("ct_id")

                    curso_id = turma_data.get("curso_id")
                    curso_res = supabase.table("cursos").select("*").eq("id", curso_id).single().execute() if curso_id else None
                    cidade_data_formatada = formatar_data_extenso(turma_data.get("data_treinamento", ""))

                    empresa_data = {}
                    if client_id:
                        cli_res = supabase.table("clients").select("*").eq("id", client_id).single().execute()
                        if cli_res and cli_res.data:
                            empresa_data = cli_res.data

                    ct_data = None
                    if ct_id_resolvido:
                        ct_res = supabase.table("cts").select("*").eq("id", ct_id_resolvido).single().execute()
                        if ct_res and ct_res.data:
                            ct_data = ct_res.data

                    instrutor_data = {}
                    instrutor_id = turma_data.get("instrutor_id")
                    if instrutor_id:
                        inst_res = supabase.table("instrutores").select("*").eq("id", instrutor_id).single().execute()
                        if inst_res and inst_res.data:
                            instrutor_data = inst_res.data

                    mat_res = supabase.table("matriculas").select("data_treinamento, carga_horaria, alunos(name, rg, cpf, data_nasc)").eq("turma_id", tid).execute()

                    alunos_lista = []
                    if mat_res and mat_res.data:
                        for m in mat_res.data:
                            aluno_info = m.get("alunos") or {}
                            alunos_lista.append({
                                "nome": aluno_info.get("name", ""),
                                "rg": aluno_info.get("rg", ""),
                                "cpf": aluno_info.get("cpf", ""),
                                "data_nasc": aluno_info.get("data_nasc", ""),
                                "data_matricula": m.get("data_treinamento", ""),
                                "horas": m.get("carga_horaria") or "08 Horas"
                            })

                    normativa_curso = curso_res.data.get("normativa", "") if curso_res and curso_res.data else ""
                    dados_turma_config = {"normativa": normativa_curso, "cidade_data": cidade_data_formatada, "logo_conecta": ""}

                    html_gerado = gerar_atestado_pdf_de_arquivo(
                        dados_turma=dados_turma_config,
                        alunos_matriculas=alunos_lista,
                        instrutor=instrutor_data,
                        empresa=empresa_data,
                        ct=ct_data
                    )

                    pdf_bytes = HTML(string=html_gerado).write_pdf()

                    supabase.table("turmas").update({"documento_emitido": True}).eq("id", tid).execute()
                    supabase.table("matriculas").update({"doc_emitida": True}).eq("turma_id", tid).execute()

                    str_lit.success("✅ Atestado em PDF gerado com sucesso!")
                    str_lit.download_button("📥 Baixar Atestado (PDF)", data=pdf_bytes, file_name=f"atestado_{titulo_turma.replace(' ', '_')}.pdf", mime="application/pdf", use_container_width=True)

            except Exception as e:
                str_lit.error(f"❌ Erro ao gerar atestado: {e}")
                
    elif tipo_documento == "Certificado da Empresa":
        str_lit.write("🏢 Gera um PDF do certificado geral emitido em nome da Empresa Cliente.")

        if not client_id:
            str_lit.warning("⚠️ Esta turma não possui uma empresa vinculada (Particular/Aberta). Vincule uma empresa na tela de edição da turma para emitir este documento.")
            str_lit.stop()

        col_nivel, col_resp = str_lit.columns(2)
        with col_nivel:
            nivel_cert = str_lit.selectbox("Nível do Treinamento", ["Intermediário", "Básico", "Avançado", ""], key=f"nivel_emp_{tid}")
        with col_resp:
            resp_tecnico = str_lit.text_input("Responsável Técnico", value="Cristiano Reis", key=f"resp_tec_emp_{tid}")
        cpf_resp = str_lit.text_input("CPF do Resp. Técnico", value="214.135.358-01", key=f"cpf_resp_emp_{tid}")

        str_lit.markdown("---")

        if str_lit.button("🏢 Gerar Certificado da Empresa (PDF)", type="primary", use_container_width=True, key=f"btn_cert_emp_{tid}"):
            try:
                with str_lit.spinner("Gerando certificado da empresa..."):
                    turma_res = supabase.table("turmas").select("*").eq("id", tid).single().execute()
                    turma_data = turma_res.data if turma_res and turma_res.data else {}

                    curso_id = turma_data.get("curso_id")
                    normativa_cert = ""
                    if curso_id:
                        curso_res = supabase.table("cursos").select("normativa").eq("id", curso_id).single().execute()
                        if curso_res and curso_res.data:
                            normativa_cert = curso_res.data.get("normativa", "")

                    cidade_data_cert = formatar_data_extenso(turma_data.get("data_treinamento", ""))

                    instrutor_data = {}
                    instrutor_id = turma_data.get("instrutor_id")
                    if instrutor_id:
                        inst_res = supabase.table("instrutores").select("*").eq("id", instrutor_id).single().execute()
                        if inst_res and inst_res.data:
                            instrutor_data = inst_res.data

                    cli_res = supabase.table("clients").select("*").eq("id", client_id).single().execute()
                    empresa_data = cli_res.data if cli_res and cli_res.data else {}

                    mat_res = supabase.table("matriculas").select("data_treinamento, carga_horaria, alunos(name, rg, cpf, data_nasc)").eq("turma_id", tid).execute()
                    alunos_lista = []
                    
                    if mat_res and mat_res.data:
                        for m in mat_res.data:
                            aluno_info = m.get("alunos") or {}
                            alunos_lista.append({
                                "name": aluno_info.get("name", ""),
                                "cpf": aluno_info.get("cpf", ""),
                                "rg": aluno_info.get("rg", ""),
                                "horas": m.get("carga_horaria") or "8 Horas",
                            })

                    turma_cert = {
                        "modalidade": turma_data.get("modalidade", "Presencial"),
                        "nivel": nivel_cert,
                        "carga_horaria": "8 Horas",
                        "resp_tecnico": resp_tecnico.strip() if resp_tecnico else "",
                        "cpf_resp_tecnico": cpf_resp.strip() if cpf_resp else "",
                    }

                    pdf_bytes = gerar_certificado_empresa_pdf(
                        turma=turma_cert,
                        instrutor=instrutor_data,
                        empresa=empresa_data,
                        alunos=alunos_lista,
                        normativa=normativa_cert,
                        cidade_data=cidade_data_cert,
                    )

                    supabase.table("turmas").update({"documento_emitido": True}).eq("id", tid).execute()

                    str_lit.success("✅ Certificado da Empresa gerado com sucesso!")
                    str_lit.download_button("📥 Baixar Certificado Empresa (PDF)", data=pdf_bytes, file_name=f"certificado_empresa_{titulo_turma.replace(' ', '_')}.pdf", mime="application/pdf", use_container_width=True, key=f"dl_cert_emp_{tid}")

            except Exception as e:
                str_lit.error(f"❌ Erro ao gerar certificado da empresa: {e}")

    elif tipo_documento == "Certificados Individuais (Alunos)":
        str_lit.write("🎓 Gera um PDF com um certificado por página (paisagem A4) para todos os alunos da turma.")

        col_nivel, col_resp = str_lit.columns(2)
        with col_nivel:
            nivel_cert = str_lit.selectbox("Nível do Treinamento", ["Intermediário", "Básico", "Avançado", ""], key=f"nivel_cert_{tid}")
        with col_resp:
            resp_tecnico = str_lit.text_input("Responsável Técnico", value="Cristiano Reis", key=f"resp_tec_{tid}")
        cpf_resp = str_lit.text_input("CPF do Responsável Técnico", value="214.135.358-01", key=f"cpf_resp_{tid}")

        str_lit.markdown("---")

        if str_lit.button("🎓 Gerar Certificados (PDF)", type="primary", use_container_width=True, key=f"btn_cert_{tid}"):
            try:
                with str_lit.spinner("Gerando certificados..."):
                    turma_res = supabase.table("turmas").select("*").eq("id", tid).single().execute()
                    turma_data = turma_res.data if turma_res and turma_res.data else {}

                    curso_id = turma_data.get("curso_id")
                    normativa_cert = ""
                    if curso_id:
                        curso_res = supabase.table("cursos").select("normativa").eq("id", curso_id).single().execute()
                        if curso_res and curso_res.data:
                            normativa_cert = curso_res.data.get("normativa", "")

                    cidade_data_cert = formatar_data_extenso(turma_data.get("data_treinamento", ""))

                    instrutor_data = {}
                    instrutor_id = turma_data.get("instrutor_id")
                    if instrutor_id:
                        inst_res = supabase.table("instrutores").select("*").eq("id", instrutor_id).single().execute()
                        if inst_res and inst_res.data:
                            instrutor_data = inst_res.data

                    empresa_data = None
                    if client_id:
                        cli_res = supabase.table("clients").select("*").eq("id", client_id).single().execute()
                        if cli_res and cli_res.data:
                            empresa_data = cli_res.data

                    mat_res = supabase.table("matriculas").select("data_treinamento, carga_horaria, alunos(name, rg, cpf, data_nasc)").eq("turma_id", tid).execute()

                    alunos_lista = []
                    if mat_res and mat_res.data:
                        for m in mat_res.data:
                            aluno_info = m.get("alunos") or {}
                            alunos_lista.append({
                                "name": aluno_info.get("name", ""),
                                "cpf": aluno_info.get("cpf", ""),
                                "rg": aluno_info.get("rg", ""),
                                "horas": m.get("carga_horaria") or "8 Horas",
                            })

                    if not alunos_lista:
                        str_lit.warning("⚠️ Nenhum aluno matriculado nesta turma.")
                        str_lit.stop()

                    turma_cert = {
                        "modalidade": turma_data.get("modalidade", "Presencial"),
                        "nivel": nivel_cert,
                        "carga_horaria": "8 Horas",
                        "resp_tecnico": resp_tecnico.strip() if resp_tecnico else "",
                        "cpf_resp_tecnico": cpf_resp.strip() if cpf_resp else "",
                    }

                    pdf_bytes = gerar_certificados_pdf(
                        alunos_matriculas=alunos_lista,
                        turma=turma_cert,
                        instrutor=instrutor_data,
                        empresa=empresa_data,
                        normativa=normativa_cert,
                        cidade_data=cidade_data_cert,
                    )

                    supabase.table("turmas").update({"documento_emitido": True}).eq("id", tid).execute()
                    supabase.table("matriculas").update({"doc_emitida": True}).eq("turma_id", tid).execute()

                    str_lit.success(f"✅ {len(alunos_lista)} certificado(s) gerado(s) com sucesso!")
                    str_lit.download_button("📥 Baixar Certificados (PDF)", data=pdf_bytes, file_name=f"certificados_{titulo_turma.replace(' ', '_')}.pdf", mime="application/pdf", use_container_width=True, key=f"dl_cert_{tid}")

            except Exception as e:
                str_lit.error(f"❌ Erro ao gerar certificados: {e}")

    elif tipo_documento == "Lista de Presença":
        str_lit.write("📋 Opções para a Lista de Presença da turma.")
        if str_lit.button("Gerar Lista", type="primary", use_container_width=True):
            str_lit.info("Módulo de lista de presença em andamento.")

# ==========================================
# ABA 1: LISTAGEM DE TURMAS (EM LINHAS/CARDS)
# ==========================================
with tab_listar:
    str_lit.subheader("Turmas Abertas e Emissão de Documentos")
    
    try:
        response = supabase.table("turmas").select("*").order("data_treinamento", desc=True).execute()
        
        if response and isinstance(response.data, list) and len(response.data) > 0:
            for t in response.data:
                if isinstance(t, dict):
                    tid = t.get("id")
                    titulo = str(t.get("titulo", "Sem Título"))
                    data_treinamento = str(t.get("data_treinamento", ""))
                    modalidade = str(t.get("modalidade", "Presencial"))
                    
                    curso_id = t.get("curso_id")
                    instrutor_id = t.get("instrutor_id")
                    client_id = t.get("client_id")
                    ct_id = t.get("ct_id")
                    
                    doc_emitido = t.get("documento_emitido", False)
                    status_str = "🟢 Documentações Emitidas" if doc_emitido else "🟡 A Emitir"
                    
                    nome_empresa = "Aberta ao Público / Particular"
                    if client_id:
                        cli_res = supabase.table("clients").select("name").eq("id", client_id).execute()
                        if cli_res and cli_res.data:
                            nome_empresa = cli_res.data[0].get("name", "Aberta ao Público")
                            
                    instrutor_nome = "Não definido"
                    if instrutor_id:
                        i_res = supabase.table("instrutores").select("name").eq("id", instrutor_id).execute()
                        if i_res and i_res.data:
                            instrutor_nome = i_res.data[0].get("name", "Não definido")

                    with str_lit.container(border=True):
                        col_info, col_acoes = str_lit.columns([4, 1.5])
                        
                        with col_info:
                            str_lit.markdown(f"**{titulo}** — *{modalidade}*")
                            str_lit.markdown(f"Status: **{status_str}**")
                            str_lit.markdown(f"🏢 **Empresa:** {nome_empresa} &nbsp;&nbsp;|&nbsp;&nbsp; 📅 **Data:** {data_treinamento}")
                            str_lit.markdown(f"👨‍🏫 **Instrutor:** {instrutor_nome}")
                            
                        with col_acoes:
                            str_lit.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)
                            b1, b2, b3, b4, b5 = str_lit.columns(5)
                            
                            with b1:
                                if str_lit.button("👁️", key=f"view_{tid}", help="Visualizar e Editar lista de alunos e cargas horárias"):
                                    modal_visualizar_alunos(tid, titulo)
                                    
                            with b2:
                                if str_lit.button("✏️", key=f"edit_{tid}", help="Alterar informações da turma"):
                                    modal_editar_turma(tid, titulo, modalidade, curso_id, instrutor_id, data_treinamento, ct_id)
                                    
                            with b3:
                                if str_lit.button("✅", key=f"emit_{tid}", help="Emitir documentações"):
                                    modal_emitir_documentacao(tid, titulo, client_id, ct_id)
                                    
                            with b4:
                                if str_lit.button("📥", key=f"imp_{tid}", help="Importar planilha de alunos"):
                                    modal_importar_planilha(tid, titulo, data_treinamento)

                            with b5:
                                if not doc_emitido:
                                    if str_lit.button("🗑️", key=f"del_{tid}", help="Excluir turma (somente turmas sem documentação emitida)"):
                                        modal_excluir_turma(tid, titulo)
                                else:
                                    str_lit.button("🔒", key=f"locked_{tid}", help="Turma com documentação já emitida não pode ser excluída", disabled=True)
        else:
            str_lit.info("Nenhuma turma aberta no momento.")
            
    except Exception as e:
        str_lit.error(f"Erro ao buscar turmas: {e}")

# ==========================================
# ABA 2: FORMULÁRIO DE ABERTURA DE TURMA
# ==========================================
with tab_cadastrar:
    str_lit.subheader("Abrir Nova Turma")
    
    instrutores_dict, cursos_dict, empresas_dict, cts_dict = {}, {}, {}, {}
    
    try:
        instr_res = supabase.table("instrutores").select("id, name").eq("is_active", True).execute()
        if instr_res and isinstance(instr_res.data, list):
            for i in instr_res.data:
                if isinstance(i, dict) and i.get("name") and i.get("id"):
                    instrutores_dict[str(i.get("name"))] = i.get("id")
                
        curso_res = supabase.table("cursos").select("id, name").execute()
        if curso_res and isinstance(curso_res.data, list):
            for c in curso_res.data:
                if isinstance(c, dict) and c.get("name") and c.get("id"):
                    cursos_dict[str(c.get("name"))] = c.get("id")

        client_res = supabase.table("clients").select("id, name, sigla, cnpj").order("name", desc=False).execute()
        if client_res and isinstance(client_res.data, list):
            for cl in client_res.data:
                if isinstance(cl, dict):
                    cid, c_name, c_sigla, c_cnpj = cl.get("id"), cl.get("name", "Sem Nome"), cl.get("sigla", ""), cl.get("cnpj", "")
                    rotulo_empresa = f"{c_name}{' [' + c_sigla + ']' if c_sigla else ''} — CNPJ: {c_cnpj}"
                    if cid: empresas_dict[rotulo_empresa] = cid

        cts_res = supabase.table("cts").select("id, name, cnpj").execute()
        if cts_res and isinstance(cts_res.data, list):
            for ct in cts_res.data:
                if isinstance(ct, dict):
                    ct_id, ct_nome, ct_cnpj = ct.get("id"), ct.get("name", "CT"), ct.get("cnpj", "N/D")
                    ct_label = f"{ct_nome} — CNPJ: {ct_cnpj}"
                    if ct_id: cts_dict[ct_label] = ct_id

    except Exception as e:
        str_lit.warning(f"Aviso ao carregar dependências: {e}")

    with str_lit.form("form_abertura_turma_master_v3", clear_on_submit=True):
        col1, col2 = str_lit.columns(2)
        with col1:
            titulo = str_lit.text_input("Título da Turma*", value=f"Treinamento Brigada - {date.today().strftime('%d/%m/%Y')}")
            modalidade = str_lit.selectbox("Modalidade*", options=["Presencial", "In Company", "Online"])
            curso_selecionado = str_lit.selectbox("Curso*", options=list(cursos_dict.keys()) if cursos_dict else ["Nenhum curso cadastrado"])
        with col2:
            data_treinamento = str_lit.date_input("Data Real do Treinamento*", value=date.today())
            instrutor_selecionado = str_lit.selectbox("Instrutor Responsável*", options=list(instrutores_dict.keys()) if instrutores_dict else ["Nenhum instrutor cadastrado"])
            
        str_lit.markdown("---")
        str_lit.subheader("🏢 Centro de Treinamento e Empresa Contratante")
        
        ct_selecionado = str_lit.selectbox("Centro de Treinamento (CT)*", options=list(cts_dict.keys()) if cts_dict else ["Nenhum CT cadastrado"])
        empresa_selecionada = str_lit.selectbox("Empresa Cliente (Opcional ou In Company)", options=["Nenhuma / Aberta ao Público"] + list(empresas_dict.keys()) if empresas_dict else ["Nenhuma empresa cadastrada"])
            
        if str_lit.form_submit_button("Criar Turma", type="primary", use_container_width=True):
            if not titulo or not curso_selecionado or not instrutor_selecionado or not ct_selecionado:
                str_lit.warning("⚠️ Por favor, preencha todos os campos obrigatórios.")
            elif "Nenhum" in curso_selecionado or "Nenhum" in instrutor_selecionado or "Nenhum" in ct_selecionado:
                str_lit.warning("⚠️ Você precisa ter cursos, instrutores e CTs cadastrados antes de abrir uma turma.")
            else:
                try:
                    client_id_val = empresas_dict.get(empresa_selecionada) if empresa_selecionada and "Nenhuma" not in empresa_selecionada else None
                    nova_turma = {
                        "titulo": titulo.strip(), "modalidade": modalidade, "data_treinamento": data_treinamento.isoformat(),
                        "curso_id": cursos_dict[curso_selecionado], "instrutor_id": instrutores_dict[instrutor_selecionado],
                        "client_id": client_id_val, "ct_id": cts_dict[ct_selecionado]
                    }
                    supabase.table("turmas").insert(nova_turma).execute()
                    str_lit.success("✅ Turma aberta com sucesso!")
                    str_lit.balloons()
                    str_lit.rerun()
                except Exception as e:
                    str_lit.error(f"❌ Erro ao abrir turma: {e}")