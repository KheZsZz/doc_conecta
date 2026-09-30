import streamlit as str_lit
import pandas as pd
import re
from datetime import date, datetime
from src.config.database import supabase
from src.utils.import_helper import processar_planilha_alunos
from src.utils.atestado import gerar_atestado_pdf_de_arquivo
from src.utils.certificado import gerar_certificados_pdf, gerar_certificados_pdf_zip
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

def extrair_cidade_do_endereco(endereco):
    if not endereco:
        return "Itapecerica da Serra"
        
    endereco_str = str(endereco)
    
    if "Itapecerica da Serra" in endereco_str:
        return "Itapecerica da Serra"
    if "Guarulhos" in endereco_str:
        return "Guarulhos"
        
    match = re.search(r'([^,-]+)(?:/|-)\s*[A-Z]{2}(?:\s|-|$)', endereco_str)
    if match:
        cidade_bruta = match.group(1).strip()
        cidade_limpa = cidade_bruta.split(',')[-1].strip()
        return cidade_limpa
        
    return "Itapecerica da Serra"

def formatar_data_extenso(data_str, cidade="Itapecerica da Serra"):
    if not data_str:
        return f"{cidade}, data não informada."
        
    try:
        if "T" in str(data_str):
            data_str = str(data_str).split("T")[0]
            
        dt = pd.to_datetime(data_str)
        dia = dt.day
        mes = MESES_PT[dt.month]
        ano = dt.year
        return f"{cidade}, {dia} de {mes} de {ano}."
    except Exception as e:
        return f"{cidade}, {data_str}."

# ==========================================
# 0. FUNÇÕES DE MODAL / POPUPS
# ==========================================
@str_lit.dialog("👥 Adicionar Aluno Manualmente", width="medium")
def modal_adicionar_aluno(turma_id, titulo_turma, client_id, data_treinamento, carga_horaria):
    str_lit.write(f"**Turma:** {titulo_turma}")
    str_lit.caption("Os alunos adicionados aqui serão vinculados à empresa desta turma.")
    
    with str_lit.form(f"form_add_aluno_{turma_id}"):
        nome_aluno = str_lit.text_input("Nome Completo*")
        
        col1, col2 = str_lit.columns(2)
        with col1:
            cpf_aluno = str_lit.text_input("CPF")
        with col2:
            rg_aluno = str_lit.text_input("RG")
            
        col_nasc, _ = str_lit.columns(2)
        with col_nasc:
            data_nasc_input = str_lit.date_input("Data de Nascimento", value=None, min_value=date(1920, 1, 1))
            
        submit_aluno = str_lit.form_submit_button("💾 Salvar Aluno e Matricular", type="primary", use_container_width=True)
        
        if submit_aluno:
            if not nome_aluno.strip():
                str_lit.warning("⚠️ O nome do aluno é obrigatório.")
            else:
                try:
                    str_lit.info("Buscando se o aluno já existe (pelo CPF ou Nome)...")
                    aluno_id = None
                    
                    if cpf_aluno.strip():
                        cpf_limpo = re.sub(r'[^0-9]', '', cpf_aluno)
                        if len(cpf_limpo) > 0:
                            aluno_res = supabase.table("alunos").select("id").eq("cpf", cpf_aluno.strip()).execute()
                            if aluno_res and len(aluno_res.data) > 0:
                                aluno_id = aluno_res.data[0]['id']
                                
                    if not aluno_id:
                        aluno_res = supabase.table("alunos").select("id").ilike("name", nome_aluno.strip()).execute()
                        if aluno_res and len(aluno_res.data) > 0:
                            aluno_id = aluno_res.data[0]['id']
                            
                    data_nasc_str = data_nasc_input.isoformat() if data_nasc_input else None
                            
                    if not aluno_id:
                        novo_aluno = {
                            "name": nome_aluno.strip().upper(),
                            "cpf": cpf_aluno.strip() if cpf_aluno.strip() else None,
                            "rg": rg_aluno.strip() if rg_aluno.strip() else None,
                            "client_id": client_id,
                            "data_nasc": data_nasc_str
                        }
                        insert_res = supabase.table("alunos").insert(novo_aluno).execute()
                        if insert_res and len(insert_res.data) > 0:
                            aluno_id = insert_res.data[0]['id']
                            
                    if aluno_id:
                        matricula_res = supabase.table("matriculas").select("id").eq("turma_id", turma_id).eq("aluno_id", aluno_id).execute()
                        if matricula_res and len(matricula_res.data) > 0:
                            str_lit.warning("⚠️ Este aluno já está matriculado nesta turma!")
                        else:
                            nova_matricula = {
                                "turma_id": turma_id,
                                "aluno_id": aluno_id,
                                "data_treinamento": data_treinamento,
                                "carga_horaria": carga_horaria
                            }
                            supabase.table("matriculas").insert(nova_matricula).execute()
                            str_lit.success(f"✅ Aluno {nome_aluno} adicionado e matriculado com sucesso!")
                            str_lit.rerun()
                            
                except Exception as e:
                    str_lit.error(f"❌ Erro ao adicionar/matricular aluno: {e}")

@str_lit.dialog("📝 Visualizar / Editar Matrículas", width="large")
def modal_editar_matriculas(tid, titulo_turma):
    str_lit.subheader(f"Matrículas: {titulo_turma}")
    
    try:
        mat_res = supabase.table("matriculas").select("id, aluno_id, carga_horaria, alunos(name, cpf, rg)").eq("turma_id", tid).execute()
        
        if not mat_res or not mat_res.data:
            str_lit.info("Nenhum aluno matriculado nesta turma até o momento.")
            return
            
        matriculas_lista = []
        for m in mat_res.data:
            aluno_info = m.get('alunos') or {}
            matriculas_lista.append({
                "matricula_id": m.get("id"),
                "aluno_id": m.get("aluno_id"),
                "Nome": aluno_info.get("name", "Sem Nome"),
                "CPF": aluno_info.get("cpf", ""),
                "RG": aluno_info.get("rg", ""),
                "Carga Horária": m.get("carga_horaria", "")
            })
            
        df_mat = pd.DataFrame(matriculas_lista)
        
        if not df_mat.empty:
            str_lit.dataframe(
                df_mat[["Nome", "CPF", "RG", "Carga Horária"]],
                use_container_width=True,
                hide_index=True
            )
            
            str_lit.markdown("---")
            str_lit.write("⚠️ **Ações de Remoção:**")
            
            aluno_para_remover = str_lit.selectbox(
                "Selecione um aluno para remover desta turma:",
                options=df_mat.to_dict('records'),
                format_func=lambda x: f"{x['Nome']} (CPF: {x['CPF']})",
                key=f"rem_aluno_{tid}"
            )
            
            if aluno_para_remover:
                if str_lit.button(f"🗑️ Remover {aluno_para_remover['Nome']} da Turma", type="primary", key=f"btn_rem_{tid}"):
                    try:
                        supabase.table("matriculas").delete().eq("id", aluno_para_remover['matricula_id']).execute()
                        str_lit.success("✅ Matrícula removida com sucesso!")
                        str_lit.rerun()
                    except Exception as e:
                        str_lit.error(f"Erro ao remover: {e}")
                        
    except Exception as e:
        str_lit.error(f"Erro ao buscar matrículas: {e}")

@str_lit.dialog("📤 Importar Alunos (Excel)", width="large")
def modal_importar_excel(tid, titulo_turma, client_id, data_treinamento_str, carga_horaria_str):
    str_lit.subheader(f"Importar Lista de Presença para a Turma")
    str_lit.write(f"**Turma:** {titulo_turma}")
    
    str_lit.info("""
    Para facilitar o processo, você pode usar a nossa ferramenta de Extração Automática via OCR 
    na página "Leitor de PDF/Imagens" para converter a sua lista assinada em um arquivo Excel (.xlsx).
    
    A planilha deve conter preferencialmente as colunas: **NOME, RG, CPF**.
    """)
    
    arquivo_upload = str_lit.file_uploader("Selecione o arquivo Excel (.xlsx ou .xls)", type=["xlsx", "xls"], key=f"up_excel_{tid}")
    
    if arquivo_upload:
        try:
            df_temp = pd.read_excel(arquivo_upload)
            str_lit.write("📊 Pré-visualização das Colunas Encontradas:")
            str_lit.dataframe(df_temp.head(3), use_container_width=True)
            
            colunas_disp = ["(Nenhuma)"] + list(df_temp.columns)
            
            str_lit.markdown("### Mapeamento de Colunas")
            col1, col2, col3 = str_lit.columns(3)
            with col1:
                col_nome = str_lit.selectbox("Coluna de NOME*", options=colunas_disp, index=colunas_disp.index("NOME") if "NOME" in colunas_disp else 0)
            with col2:
                col_cpf = str_lit.selectbox("Coluna de CPF", options=colunas_disp, index=colunas_disp.index("CPF") if "CPF" in colunas_disp else 0)
            with col3:
                col_rg = str_lit.selectbox("Coluna de RG", options=colunas_disp, index=colunas_disp.index("RG") if "RG" in colunas_disp else 0)
                
            if str_lit.button("🚀 Processar e Matricular Alunos", type="primary", use_container_width=True, key=f"btn_proc_excel_{tid}"):
                if col_nome == "(Nenhuma)":
                    str_lit.error("⚠️ Você deve selecionar qual é a coluna que contém o NOME dos alunos.")
                    str_lit.stop()
                    
                mapa_colunas = {
                    "NOME": col_nome,
                    "CPF": col_cpf if col_cpf != "(Nenhuma)" else None,
                    "RG": col_rg if col_rg != "(Nenhuma)" else None
                }
                
                with str_lit.spinner("A analisar a planilha e matricular os alunos no sistema... (Isto pode levar alguns segundos)"):
                    resultado = processar_planilha_alunos(
                        arquivo_bytes=arquivo_upload.getvalue(),
                        nome_arquivo=arquivo_upload.name,
                        mapeamento_colunas=mapa_colunas,
                        turma_id=tid,
                        client_id=client_id,
                        data_treinamento=data_treinamento_str,
                        carga_horaria=carga_horaria_str
                    )
                    
                    if resultado["sucesso"]:
                        str_lit.success(resultado["mensagem"])
                        
                        col_met1, col_met2 = str_lit.columns(2)
                        col_met1.metric("Alunos Inseridos/Encontrados", resultado["alunos_processados"])
                        col_met2.metric("Novas Matrículas", resultado["matriculas_criadas"])
                        
                        if resultado["erros"]:
                            str_lit.warning("Algumas linhas tiveram erros ou alunos já estavam matriculados:")
                            for err in resultado["erros"]:
                                str_lit.write(f"- {err}")
                                
                        str_lit.balloons()
                    else:
                        str_lit.error(f"Falha no processamento: {resultado['mensagem']}")
                        
        except Exception as e:
            str_lit.error(f"Erro ao ler o arquivo Excel: {e}")

@str_lit.dialog("📄 Emitir Documentos", width="large")
def modal_emitir_documentacao(tid, titulo_turma, client_id, ct_id=None):
    str_lit.write(f"**Turma:** {titulo_turma}")
    
    # 1. Pega os dados da turma para descobrir o curso
    turma_data = {}
    try:
        t_res = supabase.table("turmas").select("*").eq("id", tid).single().execute()
        if t_res and t_res.data:
            turma_data = t_res.data
    except Exception:
        pass
    
    # 2. Verifica se o curso emite atestado e traz os dizeres específicos
    curso_id = turma_data.get("curso_id")
    exige_atestado = True
    dizeres_aluno = ""
    dizeres_empresa = ""
    nome_curso = "Treinamento"
    if curso_id:
        try:
            c_res = supabase.table("cursos").select("*").eq("id", curso_id).single().execute()
            if c_res and c_res.data:
                exige_atestado = c_res.data.get("exige_atestado", True)
                dizeres_aluno = c_res.data.get("dizeres_certificado_aluno", "")
                dizeres_empresa = c_res.data.get("dizeres_certificado_empresa", "")
                nome_curso = c_res.data.get("name", "Treinamento")
        except: pass

    str_lit.markdown("Selecione o documento desejado para emissão:")
    str_lit.markdown("---")

    opcoes_documentos = [
        "Certificado da Empresa",
        "Certificados Individuais (Alunos)",
        "Lista de Presença"
    ]
    
    # Só adiciona o Atestado se o curso permitir
    if exige_atestado:
        opcoes_documentos.insert(0, "Atestado de Brigada (Empresa)")
    else:
        str_lit.info("ℹ️ Este curso está configurado para **NÃO emitir Atestado**.")

    tipo_documento = str_lit.selectbox("Tipo de Documento", opcoes_documentos)

    modalidade_oficial = turma_data.get("modalidade", "Presencial")
    nivel_oficial = turma_data.get("nivel", "Básico")
    carga_horaria_oficial = turma_data.get("carga_horaria", "8 Horas")
    normativa_cert = turma_data.get("normativa", "")

    resp_res = supabase.table("responsaveis_tecnicos").select("*").execute()
    responsaveis = resp_res.data if resp_res and resp_res.data else []

    opcoes_resp = {f"{r.get('nome', 'Sem Nome')} (CPF: {r.get('cpf', 'N/D')})": r for r in responsaveis}
    default_idx = 0
    for i, r in enumerate(responsaveis):
        if r.get("is_default"):
            default_idx = i
            break

    dados_resp_tecnico = {}
    if tipo_documento in ["Certificado da Empresa", "Certificados Individuais (Alunos)"]:
        if responsaveis:
            resp_selecionado = str_lit.selectbox(
                "Responsável Técnico Assinante", 
                options=list(opcoes_resp.keys()), 
                index=default_idx, 
                key=f"sel_resp_{tipo_documento}_{tid}"
            )
            dados_resp_tecnico = opcoes_resp.get(resp_selecionado)
        else:
            dados_resp_tecnico = {"nome": "Cristiano Reis", "cpf": "214.135.358-01", "assinatura_url": None}
            str_lit.warning("⚠️ Nenhum responsável técnico ativo encontrado. Usando padrão.")
        str_lit.markdown("---")

    if tipo_documento == "Atestado de Brigada (Empresa)":
        str_lit.info(f"ℹ️ O atestado usará os dados oficiais da turma: **{modalidade_oficial} | {nivel_oficial} | {carga_horaria_oficial}**")

        if str_lit.button("🚀 Processar e Gerar Atestado", type="primary", use_container_width=True):
            try:
                with str_lit.spinner("Buscando dados e gerando atestado..."):
                    ct_id_resolvido = ct_id or turma_data.get("ct_id")
                    ct_data = None
                    cidade_ct = "Itapecerica da Serra"
                    if ct_id_resolvido:
                        ct_res = supabase.table("cts").select("*").eq("id", ct_id_resolvido).single().execute()
                        if ct_res and ct_res.data:
                            ct_data = ct_res.data
                            cidade_ct = extrair_cidade_do_endereco(ct_data.get("full_address"))

                    curso_res = supabase.table("cursos").select("*").eq("id", curso_id).single().execute() if curso_id else None
                    cidade_data_formatada = formatar_data_extenso(turma_data.get("data_treinamento", ""), cidade=cidade_ct)

                    empresa_data = {}
                    if client_id:
                        cli_res = supabase.table("clients").select("*").eq("id", client_id).single().execute()
                        if cli_res and cli_res.data:
                            empresa_data = cli_res.data

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
                                "horas": m.get("carga_horaria") or carga_horaria_oficial,
                                "Treinamento": nivel_oficial 
                            })

                    pdf_bytes = gerar_atestado_pdf_de_arquivo(
                        alunos=alunos_lista,
                        turma=turma_data,
                        empresa=empresa_data,
                        curso=curso_res.data if curso_res else None,
                        instrutor=instrutor_data,
                        ct=ct_data,
                        cidade_data_formatada=cidade_data_formatada
                    )
                    
                    supabase.table("turmas").update({"documento_emitido": True}).eq("id", tid).execute()

                    str_lit.success("✅ Atestado gerado com sucesso!")
                    str_lit.download_button("📥 Baixar Atestado (PDF)", data=pdf_bytes, file_name=f"atestado_{titulo_turma.replace(' ', '_')}.pdf", mime="application/pdf", use_container_width=True, key=f"dl_atest_{tid}")

            except Exception as e:
                str_lit.error(f"❌ Erro ao gerar o atestado: {e}")

    elif tipo_documento == "Certificado da Empresa":
        if str_lit.button("🚀 Processar e Gerar Certificado (Empresa)", type="primary", use_container_width=True):
            try:
                with str_lit.spinner("Gerando certificado corporativo..."):
                    cidade_ct = "Itapecerica da Serra"
                    if ct_id:
                        ct_res = supabase.table("cts").select("full_address").eq("id", ct_id).single().execute()
                        if ct_res and ct_res.data:
                            cidade_ct = extrair_cidade_do_endereco(ct_res.data.get("full_address"))
                    cidade_data_cert = formatar_data_extenso(turma_data.get("data_treinamento", ""), cidade=cidade_ct)

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
                                "horas": m.get("carga_horaria") or carga_horaria_oficial,
                            })

                    turma_cert = {
                        "modalidade": modalidade_oficial,
                        "nivel": nivel_oficial,
                        "carga_horaria": carga_horaria_oficial,
                        "resp_tecnico": dados_resp_tecnico.get("nome", ""),
                        "cpf_resp_tecnico": dados_resp_tecnico.get("cpf", ""),
                        "assinatura_resp_url": dados_resp_tecnico.get("assinatura_url"),
                        "curso_nome": nome_curso, 
                        "dizeres_certificado_empresa": dizeres_empresa 
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
                str_lit.error(f"❌ Erro ao gerar certificado corporativo: {e}")

    elif tipo_documento == "Certificados Individuais (Alunos)":
        if str_lit.button("🚀 Processar e Baixar Lote (ZIP)", type="primary", use_container_width=True):
            try:
                with str_lit.spinner("Processando certificados individuais..."):
                    cidade_ct = "Itapecerica da Serra"
                    if ct_id:
                        ct_res = supabase.table("cts").select("full_address").eq("id", ct_id).single().execute()
                        if ct_res and ct_res.data:
                            cidade_ct = extrair_cidade_do_endereco(ct_res.data.get("full_address"))
                    cidade_data_cert = formatar_data_extenso(turma_data.get("data_treinamento", ""), cidade=cidade_ct)

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
                                "data_nasc": aluno_info.get("data_nasc", ""),
                                "horas": m.get("carga_horaria") or carga_horaria_oficial,
                            })

                    if not alunos_lista:
                        str_lit.warning("⚠️ Nenhum aluno matriculado nesta turma.")
                        str_lit.stop()

                    turma_cert = {
                        "modalidade": modalidade_oficial,
                        "nivel": nivel_oficial,
                        "carga_horaria": carga_horaria_oficial,
                        "resp_tecnico": dados_resp_tecnico.get("nome", ""),
                        "cpf_resp_tecnico": dados_resp_tecnico.get("cpf", ""),
                        "assinatura_resp_url": dados_resp_tecnico.get("assinatura_url"),
                        "curso_nome": nome_curso, 
                        "dizeres_certificado_aluno": dizeres_aluno 
                    }

                    zip_bytes = gerar_certificados_pdf_zip(
                        alunos_matriculas=alunos_lista,
                        turma=turma_cert,
                        instrutor=instrutor_data,
                        empresa=empresa_data,
                        ct=None,
                        normativa=normativa_cert,
                        cidade_data=cidade_data_cert,
                    )

                    supabase.table("turmas").update({"documento_emitido": True}).eq("id", tid).execute()

                    str_lit.success("✅ Certificados gerados com sucesso!")
                    str_lit.download_button("📥 Baixar Certificados (ZIP)", data=zip_bytes, file_name=f"certificados_{titulo_turma.replace(' ', '_')}.zip", mime="application/zip", use_container_width=True, key=f"dl_cert_zip_{tid}")

            except Exception as e:
                str_lit.error(f"❌ Erro ao gerar os certificados: {e}")

    elif tipo_documento == "Lista de Presença":
        if str_lit.button("🚀 Processar e Gerar Lista", type="primary", use_container_width=True):
            try:
                with str_lit.spinner("Buscando alunos matriculados..."):
                    mat_res = supabase.table("matriculas").select("alunos(name, rg, cpf)").eq("turma_id", tid).execute()
                    
                    if not mat_res or not mat_res.data:
                        str_lit.warning("⚠️ Nenhum aluno matriculado para gerar a lista.")
                        str_lit.stop()
                        
                    alunos_lista = []
                    for m in mat_res.data:
                        aluno_info = m.get("alunos") or {}
                        alunos_lista.append({
                            "Nome": aluno_info.get("name", ""),
                            "RG": aluno_info.get("rg", ""),
                            "CPF": aluno_info.get("cpf", ""),
                            "Assinatura": "_________________________________"
                        })
                        
                    df_presenca = pd.DataFrame(alunos_lista)
                    
                    import io
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        df_presenca.to_excel(writer, index=False, sheet_name='Lista de Presença')
                    
                    str_lit.success("✅ Lista gerada com sucesso!")
                    str_lit.download_button(
                        label="📥 Baixar Lista de Presença (.xlsx)",
                        data=buffer.getvalue(),
                        file_name=f"lista_presenca_{titulo_turma.replace(' ', '_')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        key=f"dl_lista_{tid}"
                    )
            except Exception as e:
                str_lit.error(f"❌ Erro ao gerar a lista de presença: {e}")

# ==========================================
# ABA 1: LISTAGEM DE TURMAS (EM LINHAS/CARDS)
# ==========================================
with tab_listar:
    str_lit.subheader("📋 Painel de Turmas e Emissão de Documentos")
    
    col_filtro1, col_filtro2 = str_lit.columns(2)
    with col_filtro1:
        busca_turma = str_lit.text_input("🔍 Buscar turma (Nome ou Empresa)", placeholder="Digite para filtrar...")
    with col_filtro2:
        filtro_status = str_lit.selectbox("Status dos Documentos", ["Todos", "Pendentes", "Emitidos"])

    try:
        query = supabase.table("turmas").select(
            "id, titulo, modalidade, nivel, carga_horaria, data_treinamento, "
            "documento_emitido, cursos(name), instrutores(name), clients(id, name), cts(id, name)"
        )
        
        if filtro_status == "Pendentes":
            query = query.eq("documento_emitido", False)
        elif filtro_status == "Emitidos":
            query = query.eq("documento_emitido", True)
            
        res_turmas = query.order('data_treinamento', desc=True).execute()
        
        if res_turmas and res_turmas.data:
            turmas_exibir = res_turmas.data
            
            if busca_turma.strip():
                busca_lower = busca_turma.lower()
                turmas_exibir = [
                    t for t in turmas_exibir 
                    if busca_lower in str(t.get('titulo', '')).lower() 
                    or busca_lower in str((t.get('clients') or {}).get('name', '')).lower()
                ]

            for t in turmas_exibir:
                tid = t.get('id')
                titulo = t.get('titulo', 'Turma Sem Título')
                data_trein = str(t.get('data_treinamento', ''))[:10]
                status_doc = t.get('documento_emitido', False)
                curso_nome = (t.get('cursos') or {}).get('name', 'N/A')
                empresa_nome = (t.get('clients') or {}).get('name', 'Sem Empresa Vinculada')
                empresa_id = (t.get('clients') or {}).get('id')
                ct_id = (t.get('cts') or {}).get('id')
                
                # Interface em linha (expander) para economizar espaço
                icon_status = "✅" if status_doc else "⚠️"
                cor_status = "green" if status_doc else "orange"
                
                label_expander = f"{icon_status} **{data_trein}** | {titulo} | {empresa_nome} | {curso_nome}"
                
                with str_lit.expander(label_expander):
                    str_lit.markdown(f"""
                    **📝 Detalhes da Turma:**
                    * **Curso:** {curso_nome}
                    * **Instrutor:** {(t.get('instrutores') or {}).get('name', 'N/A')}
                    * **Modalidade:** {t.get('modalidade')} | **Nível:** {t.get('nivel')} | **Carga:** {t.get('carga_horaria')}
                    * **Status de Emissão:** <span style="color:{cor_status}">{'Emitidos' if status_doc else 'Pendentes'}</span>
                    """, unsafe_allow_html=True)
                    
                    # Contar alunos
                    mat_count_res = supabase.table("matriculas").select("id", count="exact").eq("turma_id", tid).execute()
                    qtd_alunos = mat_count_res.count if mat_count_res else 0
                    
                    str_lit.info(f"👥 **Alunos Matriculados:** {qtd_alunos}")
                    
                    # BOTÕES DE AÇÃO NA LINHA
                    col_btn1, col_btn2, col_btn3, col_btn4 = str_lit.columns(4)
                    
                    with col_btn1:
                        if str_lit.button("➕ Adicionar Aluno", key=f"add_{tid}", use_container_width=True):
                            modal_adicionar_aluno(tid, titulo, empresa_id, data_trein, t.get('carga_horaria'))
                            
                    with col_btn2:
                        if str_lit.button("📤 Importar Lista (Excel)", key=f"up_{tid}", use_container_width=True):
                            modal_importar_excel(tid, titulo, empresa_id, data_trein, t.get('carga_horaria'))
                            
                    with col_btn3:
                        if str_lit.button("✏️ Ver / Editar Alunos", key=f"edit_{tid}", use_container_width=True):
                            modal_editar_matriculas(tid, titulo)
                            
                    with col_btn4:
                        if str_lit.button("📄 Gerar Documentos", key=f"doc_{tid}", type="primary", use_container_width=True):
                            modal_emitir_documentacao(tid, titulo, empresa_id, ct_id)

        else:
            str_lit.info("Nenhuma turma encontrada.")
            
    except Exception as e:
        str_lit.error(f"Erro ao carregar turmas: {e}")


# ==========================================
# ABA 2: ABRIR NOVA TURMA (CADASTRO ÚNICO)
# ==========================================
with tab_cadastrar:
    str_lit.subheader("Formulário de Abertura de Turma")
    str_lit.markdown("Ao abrir uma turma, os dados do curso e instrutor ficarão atrelados. Depois você poderá inserir os alunos e gerar os documentos na aba anterior.")
    
    # 1. Carregar listas (Comboboxes)
    try:
        cursos_res = supabase.table("cursos").select("id, name").execute()
        instrutores_res = supabase.table("instrutores").select("id, name").execute()
        empresas_res = supabase.table("clients").select("id, name, cnpj").execute()
        cts_res = supabase.table("cts").select("id, name").execute()
        
        cursos_dict = {c['name']: c['id'] for c in cursos_res.data} if cursos_res.data else {}
        instrutores_dict = {i['name']: i['id'] for i in instrutores_res.data} if instrutores_res.data else {}
        
        # Para empresas, mostra Nome - CNPJ
        empresas_dict = {}
        if empresas_res.data:
            for e in empresas_res.data:
                cnpj_fmt = e.get('cnpj', 'Sem CNPJ')
                empresas_dict[f"{e['name']} ({cnpj_fmt})"] = e['id']
                
        cts_dict = {c['name']: c['id'] for c in cts_res.data} if cts_res.data else {}

    except Exception as e:
        str_lit.error(f"Erro ao carregar dados auxiliares: {e}")
        cursos_dict, instrutores_dict, empresas_dict, cts_dict = {}, {}, {}, {}

    # 2. Formulário
    with str_lit.form("form_nova_turma", clear_on_submit=True):
        titulo = str_lit.text_input("Título Identificador da Turma*", placeholder="Ex: Turma CIPA - Outubro 2026 - Empresa XPTO")
        
        col1, col2, col3 = str_lit.columns(3)
        with col1:
            data_treinamento = str_lit.date_input("Data do Treinamento*", value=datetime.today())
        with col2:
            curso_selecionado = str_lit.selectbox("Curso / Treinamento*", ["(Nenhum curso cadastrado)"] if not cursos_dict else list(cursos_dict.keys()))
        with col3:
            instrutor_selecionado = str_lit.selectbox("Instrutor Titular*", ["(Nenhum instrutor cadastrado)"] if not instrutores_dict else list(instrutores_dict.keys()))
            
        col4, col5 = str_lit.columns(2)
        with col4:
            empresa_selecionada = str_lit.selectbox("Empresa Contratante (Cliente)*", ["Nenhuma Empresa"] + list(empresas_dict.keys()))
        with col5:
            ct_selecionado = str_lit.selectbox("CT Responsável / Local*", ["(Nenhum CT cadastrado)"] if not cts_dict else list(cts_dict.keys()))

        str_lit.markdown("#### Especificações do Treinamento")
        col6, col7, col8 = str_lit.columns(3)
        with col6:
            modalidade = str_lit.selectbox("Modalidade", ["In Company", "Presencial (No CT)", "EAD", "Semipresencial"])
        with col7:
            nivel = str_lit.selectbox("Nível", ["Básico", "Intermediário", "Avançado", "Reciclagem", "Único"])
        with col8:
            carga_horaria_num = str_lit.number_input("Carga Horária (Apenas números)", min_value=1, value=8, step=1)

        submit_turma = str_lit.form_submit_button("✅ Criar e Salvar Nova Turma", type="primary")

        if submit_turma:
            if not titulo.strip():
                str_lit.warning("⚠️ O título da turma é obrigatório.")
            elif "(Nenhum" in curso_selecionado or "(Nenhum" in instrutor_selecionado or "(Nenhum" in ct_selecionado:
                str_lit.warning("⚠️ Você precisa ter cursos, instrutores e CTs cadastrados antes de abrir uma turma.")
            else:
                try:
                    client_id_val = empresas_dict.get(empresa_selecionada) if empresa_selecionada and "Nenhuma" not in empresa_selecionada else None
                    carga_final_str = f"{carga_horaria_num} Horas" if carga_horaria_num > 1 else "1 Hora"
                    
                    nova_turma = {
                        "titulo": titulo.strip(), 
                        "modalidade": modalidade,
                        "nivel": nivel,
                        "carga_horaria": carga_final_str,
                        "data_treinamento": data_treinamento.isoformat(),
                        "curso_id": cursos_dict[curso_selecionado], 
                        "instrutor_id": instrutores_dict[instrutor_selecionado],
                        "client_id": client_id_val, 
                        "ct_id": cts_dict[ct_selecionado]
                    }
                    supabase.table("turmas").insert(nova_turma).execute()
                    str_lit.success("✅ Turma aberta com sucesso!")
                    str_lit.balloons()
                    str_lit.rerun()
                except Exception as e:
                    str_lit.error(f"❌ Erro ao abrir turma: {e}")