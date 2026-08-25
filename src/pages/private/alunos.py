import streamlit as str_lit
from datetime import date
from src.config.database import supabase

str_lit.title("🎓 Cadastro Individual de Alunos")
str_lit.markdown("Matricule alunos manualmente em turmas ativas (turmas de hoje ou com emissão de documentos pendente).")

# ==========================================
# 1. BUSCAR E FILTRAR TURMAS ATIVAS
# ==========================================
hoje_str = date.today().isoformat()
turmas_dict = {}
turmas_info_completa = {}

try:
    # Busca as turmas ordenadas por data
    res_turmas = supabase.table("turmas").select("*").order("data_treinamento", desc=True).execute()
    
    if res_turmas and res_turmas.data:
        for t in res_turmas.data:
            data_t = t.get("data_treinamento")
            doc_emitido = t.get("documento_emitido", False)
            
            # FILTRO: Apenas turmas de HOJE ou que NÃO tiveram documentação emitida
            if data_t == hoje_str or not doc_emitido:
                tid = t.get("id")
                titulo = t.get("titulo", "Sem título")
                
                # Monta um rótulo amigável para o Selectbox
                status_doc = "⚠️ Pendente" if not doc_emitido else "✅ Emitido"
                rotulo = f"{data_t} | {titulo} ({status_doc})"
                
                turmas_dict[rotulo] = tid
                turmas_info_completa[tid] = t

except Exception as e:
    str_lit.error(f"Erro ao buscar turmas: {e}")

# ==========================================
# 2. BUSCAR EMPRESAS (CLIENTS)
# ==========================================
empresas_dict = {}
try:
    res_cli = supabase.table("clients").select("id, name, cnpj").order("name").execute()
    if res_cli and res_cli.data:
        for cli in res_cli.data:
            rotulo_cli = f"{cli.get('name')} (CNPJ: {cli.get('cnpj', 'N/D')})"
            empresas_dict[rotulo_cli] = cli.get("id")
except Exception as e:
    str_lit.warning(f"Aviso ao buscar empresas: {e}")

# ==========================================
# 3. INTERFACE DE CADASTRO
# ==========================================
if not turmas_dict:
    str_lit.success("🎉 Ótima notícia! Não há turmas pendentes de documentação no momento nem turmas agendadas para hoje.")
else:
    str_lit.subheader("1. Selecione a Turma")
    
    turma_selecionada_rotulo = str_lit.selectbox(
        "Turmas Disponíveis",
        options=list(turmas_dict.keys()),
        help="Apenas turmas de hoje ou com documentos pendentes são exibidas."
    )
    
    # Recupera o ID e os dados da turma escolhida
    turma_id_escolhida = turmas_dict[turma_selecionada_rotulo]
    dados_turma = turmas_info_completa[turma_id_escolhida]
    
    str_lit.markdown("---")
    str_lit.subheader("2. Dados do Aluno")
    
    with str_lit.form("form_cadastro_aluno", clear_on_submit=True):
        col1, col2 = str_lit.columns(2)
        
        with col1:
            nome_aluno = str_lit.text_input("Nome Completo do Aluno*")
            cpf_aluno = str_lit.text_input("CPF* (Apenas números)", max_chars=14)
            data_nasc = str_lit.date_input("Data de Nascimento", value=None, min_value=date(1940, 1, 1), max_value=date.today())
            
        with col2:
            rg_aluno = str_lit.text_input("RG (Apenas números)", max_chars=11)
            email_aluno = str_lit.text_input("E-mail (Opcional)")
            telefone_aluno = str_lit.text_input("Telefone (Opcional)")
            
        str_lit.markdown("---")
        str_lit.subheader("3. Vínculo e Matrícula")
        
        col3, col4 = str_lit.columns(2)
        with col3:
            # Tenta preencher a empresa padrão com a empresa que já está vinculada na Turma
            empresa_padrao_turma = dados_turma.get("client_id")
            idx_empresa = 0
            opcoes_empresa = ["Particular / Sem Empresa"] + list(empresas_dict.keys())
            
            if empresa_padrao_turma:
                # Descobre qual é a posição dessa empresa na lista para deixar pré-selecionada
                for idx, emp_name in enumerate(empresas_dict.keys()):
                    if empresas_dict[emp_name] == empresa_padrao_turma:
                        idx_empresa = idx + 1 # +1 por causa do "Particular"
                        break

            empresa_selecionada = str_lit.selectbox("Empresa do Aluno", options=opcoes_empresa, index=idx_empresa)
            
        with col4:
            carga_horaria = str_lit.text_input("Carga Horária", value="08 Horas")
            
        submit_aluno = str_lit.form_submit_button("💾 Salvar Aluno e Matricular", type="primary", use_container_width=True)
        
        if submit_aluno:
            # Limpa formatação do CPF e RG
            cpf_limpo = cpf_aluno.replace(".", "").replace("-", "").strip() if cpf_aluno else ""
            rg_limpo = rg_aluno.replace(".", "").replace("-", "").strip() if rg_aluno else None
            
            if not nome_aluno or not cpf_limpo:
                str_lit.warning("⚠️ Os campos Nome e CPF são obrigatórios!")
            elif len(cpf_limpo) != 11:
                str_lit.warning("⚠️ O CPF deve conter 11 dígitos numéricos.")
            else:
                try:
                    with str_lit.spinner("Processando matrícula..."):
                        # 1. VERIFICA SE O ALUNO JÁ EXISTE PELO CPF
                        aluno_id = None
                        aluno_existente = supabase.table("alunos").select("id").eq("cpf", cpf_limpo).execute()
                        
                        if aluno_existente and aluno_existente.data:
                            # Aluno já existe, pega o ID dele e atualiza os dados
                            aluno_id = aluno_existente.data[0].get("id")
                            
                            payload_update = {"name": nome_aluno.strip()}
                            if rg_limpo: payload_update["rg"] = rg_limpo
                            if data_nasc: payload_update["data_nasc"] = data_nasc.isoformat()
                            if email_aluno: payload_update["email"] = email_aluno.strip()
                            if telefone_aluno: payload_update["phone"] = telefone_aluno.strip()
                            
                            supabase.table("alunos").update(payload_update).eq("id", aluno_id).execute()
                        else:
                            # Aluno não existe, cria um novo
                            payload_novo = {
                                "name": nome_aluno.strip(),
                                "cpf": cpf_limpo,
                                "rg": rg_limpo,
                                "data_nasc": data_nasc.isoformat() if data_nasc else None,
                                "email": email_aluno.strip() if email_aluno else None,
                                "phone": telefone_aluno.strip() if telefone_aluno else None
                            }
                            res_novo = supabase.table("alunos").insert(payload_novo).execute()
                            aluno_id = res_novo.data[0].get("id")
                            
                        # 2. CRIA A MATRÍCULA
                        cliente_id_final = empresas_dict.get(empresa_selecionada) if empresa_selecionada != "Particular / Sem Empresa" else None
                        
                        payload_matricula = {
                            "aluno_id": aluno_id,
                            "turma_id": turma_id_escolhida,
                            "client_id": cliente_id_final,
                            "carga_horaria": carga_horaria.strip(),
                            "data_treinamento": dados_turma.get("data_treinamento") # Herda a data da turma
                        }
                        
                        supabase.table("matriculas").insert(payload_matricula).execute()
                        
                        str_lit.success(f"✅ Aluno **{nome_aluno}** cadastrado e matriculado com sucesso na turma!")
                        str_lit.balloons()
                        
                except Exception as e:
                    str_lit.error(f"❌ Erro ao processar o cadastro do aluno. Detalhes: {e}")