import streamlit as str_lit
import uuid
import pandas as pd
from src.config.database import supabase

str_lit.title("🏢 Centros de Treinamento (CTs)")
str_lit.markdown("Gerencie os locais físicos de treinamento e suas respectivas logomarcas.")

tab_listar, tab_cadastrar = str_lit.tabs(["📋 Listar CTs", "➕ Cadastrar CT"])

# ==========================================
# FUNÇÃO AUXILIAR: UPLOAD DE LOGO PRO BUCKET
# ==========================================
def fazer_upload_logo(arquivo_upload):
    if arquivo_upload is not None:
        try:
            # Pega a extensão original do arquivo
            extensao = arquivo_upload.name.split('.')[-1]
            # Gera um nome único para não sobrescrever arquivos no bucket
            nome_arquivo = f"ct_logo_{uuid.uuid4().hex}.{extensao}"
            
            # Converte o arquivo do Streamlit para bytes
            file_bytes = arquivo_upload.getvalue()
            
            # Faz o upload pro bucket "logos"
            supabase.storage.from_("logos").upload(
                file=file_bytes,
                path=nome_arquivo,
                file_options={"content-type": arquivo_upload.type}
            )
            
            # Retorna a URL pública da imagem recém-upada
            url_publica = supabase.storage.from_("logos").get_public_url(nome_arquivo)
            return url_publica
            
        except Exception as e:
            str_lit.error(f"❌ Erro ao fazer upload da imagem: {e}")
            return None
    return None

# ==========================================
# MODAL / POPUP DE EDIÇÃO DE CT
# ==========================================
@str_lit.dialog("✏️ Editar Centro de Treinamento", width="medium")
def modal_editar_ct(ct_id, name_atual, full_name_atual, cnpj_atual, phone_atual, address_atual, logo_atual):
    with str_lit.form(f"form_editar_ct_{ct_id}"):
        novo_name = str_lit.text_input("Nome Fantasia / Apelido do CT*", value=name_atual)
        novo_full_name = str_lit.text_input("Razão Social (Nome Completo)", value=full_name_atual)
        
        col1, col2 = str_lit.columns(2)
        with col1:
            novo_cnpj = str_lit.text_input("CNPJ", value=cnpj_atual)
        with col2:
            novo_phone = str_lit.text_input("Telefone", value=phone_atual)
            
        novo_address = str_lit.text_area("Endereço Completo", value=address_atual)
        
        str_lit.markdown("---")
        str_lit.markdown("**Atualizar Logomarca (Opcional)**")
        if logo_atual:
            str_lit.image(logo_atual, width=150, caption="Logo atual")
            
        nova_logo = str_lit.file_uploader("Substituir logomarca (PNG, JPG)", type=["png", "jpg", "jpeg"], key=f"up_edit_{ct_id}")
        
        if str_lit.form_submit_button("💾 Salvar Alterações", type="primary", use_container_width=True):
            if not novo_name:
                str_lit.warning("O Nome Fantasia é obrigatório.")
            else:
                try:
                    payload = {
                        "name": novo_name.strip(),
                        "full_name": novo_full_name.strip() if novo_full_name else None,
                        "cnpj": novo_cnpj.strip() if novo_cnpj else None,
                        "phone": novo_phone.strip() if novo_phone else None,
                        "full_address": novo_address.strip() if novo_address else None
                    }
                    
                    # Se o usuário mandou uma nova imagem, faz o upload e adiciona a URL no payload
                    if nova_logo is not None:
                        url_nova = fazer_upload_logo(nova_logo)
                        if url_nova:
                            payload["logo_url"] = url_nova
                            
                    supabase.table("cts").update(payload).eq("id", ct_id).execute()
                    str_lit.success("✅ CT atualizado com sucesso!")
                    str_lit.rerun()
                except Exception as e:
                    str_lit.error(f"Erro ao atualizar CT: {e}")

# ==========================================
# ABA 1: LISTAGEM E ALTERAÇÃO DOS CTs
# ==========================================
with tab_listar:
    str_lit.subheader("Centros de Treinamento Cadastrados")
    
    try:
        res_cts = supabase.table("cts").select("*").order("name").execute()
        
        if res_cts and res_cts.data:
            for ct in res_cts.data:
                with str_lit.container(border=True):
                    col_logo, col_info, col_acao = str_lit.columns([1, 4, 1])
                    
                    with col_logo:
                        logo_url = ct.get("logo_url")
                        if logo_url:
                            str_lit.image(logo_url, use_container_width=True)
                        else:
                            str_lit.markdown("<div style='text-align: center; color: gray; padding-top: 20px;'>Sem Logo</div>", unsafe_allow_html=True)
                            
                    with col_info:
                        str_lit.markdown(f"### {ct.get('name', 'Sem Nome')}")
                        str_lit.markdown(f"**Razão Social:** {ct.get('full_name', 'N/D')} | **CNPJ:** {ct.get('cnpj', 'N/D')}")
                        str_lit.markdown(f"📍 **Endereço:** {ct.get('full_address', 'Não informado')}")
                        str_lit.markdown(f"📞 **Telefone:** {ct.get('phone', 'Não informado')}")
                        
                    with col_acao:
                        str_lit.markdown("<div style='height: 25px;'></div>", unsafe_allow_html=True)
                        if str_lit.button("✏️ Editar", key=f"edit_ct_{ct.get('id')}", use_container_width=True):
                            modal_editar_ct(
                                ct_id=ct.get("id"),
                                name_atual=ct.get("name", ""),
                                full_name_atual=ct.get("full_name", ""),
                                cnpj_atual=ct.get("cnpj", ""),
                                phone_atual=ct.get("phone", ""),
                                address_atual=ct.get("full_address", ""),
                                logo_atual=ct.get("logo_url", "")
                            )
        else:
            str_lit.info("Nenhum Centro de Treinamento cadastrado ainda.")
            
    except Exception as e:
        str_lit.error(f"Erro ao buscar CTs: {e}")

# ==========================================
# ABA 2: CADASTRO DE NOVO CT
# ==========================================
with tab_cadastrar:
    str_lit.subheader("Cadastrar Novo CT")
    
    with str_lit.form("form_novo_ct", clear_on_submit=True):
        col1, col2 = str_lit.columns(2)
        
        with col1:
            name = str_lit.text_input("Nome Fantasia / Apelido do CT*")
            cnpj = str_lit.text_input("CNPJ (Apenas números)")
            
        with col2:
            full_name = str_lit.text_input("Razão Social (Nome Completo)")
            phone = str_lit.text_input("Telefone (Apenas números)")
            
        full_address = str_lit.text_area("Endereço Completo")
        
        str_lit.markdown("---")
        str_lit.markdown("**Logomarca do CT**")
        logo_file = str_lit.file_uploader("Selecione a imagem (PNG, JPG)", type=["png", "jpg", "jpeg"])
        
        submit_novo_ct = str_lit.form_submit_button("🚀 Cadastrar CT", type="primary", use_container_width=True)
        
        if submit_novo_ct:
            if not name:
                str_lit.warning("⚠️ O Nome Fantasia é obrigatório para cadastrar o CT.")
            else:
                try:
                    with str_lit.spinner("Salvando CT e fazendo upload da logo..."):
                        url_logo = None
                        
                        # Se escolheu uma logo, dispara a função de upload pro bucket
                        if logo_file is not None:
                            url_logo = fazer_upload_logo(logo_file)
                            
                        novo_ct = {
                            "name": name.strip(),
                            "full_name": full_name.strip() if full_name else None,
                            "cnpj": cnpj.strip() if cnpj else None,
                            "phone": phone.strip() if phone else None,
                            "full_address": full_address.strip() if full_address else None,
                            "logo_url": url_logo
                        }
                        
                        # Insere no banco
                        supabase.table("cts").insert(novo_ct).execute()
                        
                        str_lit.success("✅ Centro de Treinamento cadastrado com sucesso!")
                        str_lit.rerun()
                except Exception as e:
                    str_lit.error(f"❌ Erro ao cadastrar CT: {e}")