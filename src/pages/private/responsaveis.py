import streamlit as st
import uuid
from src.config.database import supabase

st.title("✒️ Gestão de Responsáveis Técnicos")
st.markdown("Cadastre os responsáveis técnicos e gerencie suas assinaturas para emissão nos certificados.")

def fazer_upload_assinatura_resp(arquivo_upload, cpf: str):
    """Faz upload da imagem de assinatura para o bucket público 'assinaturas' no Supabase."""
    if arquivo_upload is None:
        return None
    try:
        extensao = arquivo_upload.name.split('.')[-1]
        nome_arquivo = f"assinatura_resp_{cpf}_{uuid.uuid4().hex}.{extensao}"
        file_bytes = arquivo_upload.read()
        
        supabase.storage.from_("assinaturas").upload(
            file=file_bytes,
            path=nome_arquivo,
            file_options={"content-type": arquivo_upload.type}
        )
        url_publica = supabase.storage.from_("assinaturas").get_public_url(nome_arquivo)
        return url_publica
    except Exception as e:
        st.error(f"Erro no upload da assinatura: {e}")
        return None

tab_listar, tab_cadastrar = st.tabs(["📋 Responsáveis Cadastrados", "➕ Novo Responsável Técnico"])

# ==========================================
# ABA 1: LISTAGEM E GERENCIAMENTO
# ==========================================
with tab_listar:
    try:
        res = supabase.table("responsaveis_tecnicos").select("*").order("nome").execute()
        if res and res.data:
            for resp in res.data:
                rid = resp["id"]
                nome = resp["nome"]
                cpf = resp["cpf"]
                is_active = resp.get("is_active", True)
                is_default = resp.get("is_default", False)
                assinatura_url = resp.get("assinatura_url")

                status_str = "🟢 Ativo" if is_active else "🔴 Inativo"
                default_str = "⭐ (Padrão)" if is_default else ""

                with st.container(border=True):
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.markdown(f"**{nome}** {default_str}")
                        st.markdown(f"**CPF:** {cpf} | Status: {status_str}")
                    with col2:
                        if assinatura_url:
                            st.image(assinatura_url, width=120)
                        else:
                            st.caption("Sem assinatura")
                    with col3:
                        if not is_default:
                            if st.button("Tornar Padrão", key=f"def_{rid}", use_container_width=True):
                                # Remove o padrão atual e seta o novo
                                supabase.table("responsaveis_tecnicos").update({"is_default": False}).neq("id", rid).execute()
                                supabase.table("responsaveis_tecnicos").update({"is_default": True}).eq("id", rid).execute()
                                st.rerun()
                            
                        novo_status = not is_active
                        rotulo_btn = "Desativar" if is_active else "Reativar"
                        if st.button(rotulo_btn, key=f"act_{rid}", use_container_width=True):
                            supabase.table("responsaveis_tecnicos").update({"is_active": novo_status}).eq("id", rid).execute()
                            st.rerun()
        else:
            st.info("Nenhum responsável técnico cadastrado.")
    except Exception as e:
        st.error(f"Erro ao buscar responsáveis: {e}")

# ==========================================
# ABA 2: CADASTRO DE NOVO RESPONSÁVEL
# ==========================================
with tab_cadastrar:
    with st.form("form_novo_responsavel", clear_on_submit=True):
        nome_resp = st.text_input("Nome Completo*")
        cpf_resp = st.text_input("CPF* (Apenas números ou formato padrão)")
        is_default_new = st.checkbox("Definir como Responsável Técnico Padrão")
        
        st.markdown("**Assinatura Digitalizada (Imagem .PNG sem fundo recomendada):**")
        arquivo_assinatura = st.file_uploader("Upload da Assinatura", type=["png", "jpg", "jpeg"])
        
        submit = st.form_submit_button("Salvar Responsável", type="primary", use_container_width=True)
        
        if submit:
            if not nome_resp or not cpf_resp:
                st.warning("Preencha o Nome e o CPF obrigatórios.")
            else:
                cpf_limpo = "".join(filter(str.isdigit, cpf_resp))
                url_assinatura = fazer_upload_assinatura_resp(arquivo_assinatura, cpf_limpo) if arquivo_assinatura else None
                
                # Se este for marcado como padrão, tira o padrão dos outros
                if is_default_new:
                    supabase.table("responsaveis_tecnicos").update({"is_default": False}).neq("is_default", False).execute()

                payload = {
                    "nome": nome_resp.strip(),
                    "cpf": cpf_resp.strip(),
                    "assinatura_url": url_assinatura,
                    "is_active": True,
                    "is_default": is_default_new
                }
                
                try:
                    supabase.table("responsaveis_tecnicos").insert(payload).execute()
                    st.success("✅ Responsável Técnico cadastrado com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao cadastrar: {e}")