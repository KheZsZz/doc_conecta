import pandas as pd

def processar_planilha_alunos(arquivo_excel, data_padrao_turma: str):
    """
    Lê e trata um arquivo Excel (.xlsx) ou CSV, aplicando:
    - Nomes em CAIXA ALTA e sem espaços extras nas pontas.
    - CPFs contendo apenas dígitos numéricos.
    - Datas formatadas no padrão YYYY-MM-DD aceito pelo banco de dados.
    """
    if arquivo_excel.name.endswith(".csv"):
        df_alunos = pd.read_csv(arquivo_excel, dtype=str)
    else:
        df_alunos = pd.read_excel(arquivo_excel, dtype=str)
        
    # Padroniza os nomes das colunas da planilha (minúsculas e sem espaços)
    df_alunos.columns = [str(c).strip().lower() for c in df_alunos.columns]
    
    col_nome = next((c for c in df_alunos.columns if 'nome' in c), None)
    col_data = next((c for c in df_alunos.columns if 'data' in c or 'treinamento' in c), None)
    col_cpf = next((c for c in df_alunos.columns if 'cpf' in c), None)
    col_data_nasc = next((c for c in df_alunos.columns if 'nascimento' in c or 'data de nascimento' in c), None)
    
    if not col_nome or not col_cpf:
        raise ValueError("A planilha precisa conter obrigatoriamente colunas para 'Nome' e 'CPF'.")
        
    alunos_processados = []
    
    for _, row in df_alunos.iterrows():
        # 1. Nome: Maiúsculo e sem espaços nas pontas
        nome_aluno = str(row.get(col_nome, "")).strip().upper()
        if not nome_aluno or nome_aluno == 'NAN':
            continue
            
        # 2. CPF: Apenas números (remove pontos, traços, espaços, etc.)
        cpf_raw = str(row.get(col_cpf, ""))
        cpf_aluno = "".join(filter(str.isdigit, cpf_raw))
        if not cpf_aluno:
            continue
            
        # 3. Data do Treinamento: Formatada para o padrão do banco (YYYY-MM-DD)
        data_aluno_str = str(row.get(col_data, "")).strip() if col_data else ""
        if not data_aluno_str or data_aluno_str.lower() == 'nan':
            data_aluno_final = data_padrao_turma
        else:
            try:
                parsed_date = pd.to_datetime(data_aluno_str, errors='coerce')
                if pd.notnull(parsed_date):
                    data_aluno_final = parsed_date.strftime('%Y-%m-%d')
                else:
                    data_aluno_final = data_aluno_str
            except:
                data_aluno_final = data_aluno_str



        data_nasc_aluno = str(row.get(col_data_nasc, "")).strip() if col_data_nasc else ""
        if not data_nasc_aluno or data_nasc_aluno.lower() == 'nan':
            data_aluno_final = data_padrao_turma
        else:
            try:
                parsed_date = pd.to_datetime(data_nasc_aluno, errors='coerce')
                if pd.notnull(parsed_date):
                    data_aluno_final = parsed_date.strftime('%Y-%m-%d')
                else:
                    data_aluno_final = data_nasc_aluno
            except:
                data_aluno_final = data_nasc_aluno
        
                
        alunos_processados.append({
            "name": nome_aluno,
            "cpf": cpf_aluno,
            "data_treinamento": data_aluno_final,
            "data_nasc": str(row.get(col_data_nasc, "")).strip() if col_data_nasc else ""
        })
        
    return alunos_processados