import streamlit as str_lit
import uuid
from src.config.database import supabase

str_lit.title("🏢 Centros de Treinamento (CTs)")
str_lit.markdown(
    "Gerencie os locais físicos de treinamento e suas logomarcas, "
    "fundos de certificado e de carteirinha."
)

tab_listar, tab_cadastrar = str_lit.tabs(["📋 Listar CTs", "➕ Cadastrar CT"])


def fazer_upload_arquivo(arquivo_upload, bucket_name: str, prefixo: str):
    if arquivo_upload is not None:
        try:
            extensao = arquivo_upload.name.split(".")[-1]
            nome_arquivo = f"{prefixo}_{uuid.uuid4().hex}.{extensao}"
            file_bytes = arquivo_upload.getvalue()
            supabase.storage.from_(bucket_name).upload(
                file=file_bytes,
                path=nome_arquivo,
                file_options={"content-type": arquivo_upload.type},
            )
            return supabase.storage.from_(bucket_name).get_public_url(nome_arquivo)
        except Exception as e:
            str_lit.error(f"❌ Erro ao fazer upload do arquivo: {e}")
            return None
    return None


@str_lit.dialog("✏️ Editar Centro de Treinamento", width="medium")
def modal_editar_ct(
    ct_id,
    name_atual,
    full_name_atual,
    cnpj_atual,
    phone_atual,
    address_atual,
    logo_atual,
    fundo_cert_atual,
    fundo_cart_atual,
):
    with str_lit.form(f"form_editar_ct_{ct_id}"):
        novo_name = str_lit.text_input("Nome Fantasia / Apelido do CT*", value=name_atual)
        novo_full_name = str_lit.text_input(
            "Razão Social (Nome Completo)", value=full_name_atual
        )

        col1, col2 = str_lit.columns(2)
        with col1:
            novo_cnpj = str_lit.text_input("CNPJ", value=cnpj_atual)
        with col2:
            novo_phone = str_lit.text_input("Telefone", value=phone_atual)

        novo_address = str_lit.text_area("Endereço Completo", value=address_atual)

        str_lit.markdown("---")
        str_lit.markdown("**🏷️ Logomarca do CT (Opcional)**")
        if logo_atual:
            str_lit.image(logo_atual, width=150, caption="Logo atual")
        nova_logo = str_lit.file_uploader(
            "Substituir logomarca (PNG, JPG)",
            type=["png", "jpg", "jpeg"],
            key=f"up_edit_logo_{ct_id}",
        )

        str_lit.markdown("---")
        str_lit.markdown("**🖼️ Fundo de Certificado (Opcional)**")
        if fundo_cert_atual:
            str_lit.image(fundo_cert_atual, width=150, caption="Fundo certificado atual")
        novo_fundo_cert = str_lit.file_uploader(
            "Substituir fundo de certificado (PNG, JPG)",
            type=["png", "jpg", "jpeg"],
            key=f"up_edit_fundo_{ct_id}",
        )

        str_lit.markdown("---")
        str_lit.markdown("**🪪 Fundo de Carteirinha (Opcional)**")
        str_lit.caption(
            "Imagem de fundo usada nas carteirinhas dos alunos deste CT. "
            "Recomendado proporção próxima de um cartão (frente+verso lado a lado)."
        )
        if fundo_cart_atual:
            str_lit.image(fundo_cart_atual, width=150, caption="Fundo carteirinha atual")
        novo_fundo_cart = str_lit.file_uploader(
            "Substituir fundo de carteirinha (PNG, JPG)",
            type=["png", "jpg", "jpeg"],
            key=f"up_edit_fundo_cart_{ct_id}",
        )

        salvar = str_lit.form_submit_button(
            "💾 Salvar Alterações", type="primary", use_container_width=True
        )

        if salvar:
            if not novo_name:
                str_lit.warning("O Nome Fantasia é obrigatório.")
            else:
                try:
                    payload = {
                        "name": novo_name.strip(),
                        "full_name": novo_full_name.strip() if novo_full_name else None,
                        "cnpj": novo_cnpj.strip() if novo_cnpj else None,
                        "phone": novo_phone.strip() if novo_phone else None,
                        "full_address": novo_address.strip() if novo_address else None,
                    }

                    if nova_logo is not None:
                        url_nova_logo = fazer_upload_arquivo(nova_logo, "logos", "ct_logo")
                        if url_nova_logo:
                            payload["logo_url"] = url_nova_logo

                    if novo_fundo_cert is not None:
                        url_novo_fundo = fazer_upload_arquivo(
                            novo_fundo_cert, "certificados_fundos", "ct_fundo"
                        )
                        if url_novo_fundo:
                            payload["fundo_certificado_url"] = url_novo_fundo

                    if novo_fundo_cart is not None:
                        url_fundo_cart = fazer_upload_arquivo(
                            novo_fundo_cart, "certificados_fundos", "ct_fundo_carteirinha"
                        )
                        if url_fundo_cart:
                            payload["fundo_carteirinha_url"] = url_fundo_cart

                    supabase.table("cts").update(payload).eq("id", ct_id).execute()
                    str_lit.success("✅ CT atualizado com sucesso!")
                    str_lit.rerun()
                except Exception as e:
                    str_lit.error(f"Erro ao atualizar CT: {e}")


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
                            str_lit.markdown(
                                "<div style='text-align: center; color: gray; padding-top: 20px;'>Sem Logo</div>",
                                unsafe_allow_html=True,
                            )

                    with col_info:
                        str_lit.markdown(f"### {ct.get('name', 'Sem Nome')}")
                        str_lit.markdown(
                            f"**Razão Social:** {ct.get('full_name', 'N/D')} | **CNPJ:** {ct.get('cnpj', 'N/D')}"
                        )
                        str_lit.markdown(
                            f"📍 **Endereço:** {ct.get('full_address', 'Não informado')}"
                        )
                        str_lit.markdown(
                            f"📞 **Telefone:** {ct.get('phone', 'Não informado')}"
                        )

                        fundo_cert = (
                            "✅ Configurado"
                            if ct.get("fundo_certificado_url")
                            else "⚠️ Não configurado"
                        )
                        fundo_cart = (
                            "✅ Configurado"
                            if ct.get("fundo_carteirinha_url")
                            else "⚠️ Não configurado"
                        )
                        str_lit.markdown(f"🖼️ **Fundo de Certificado:** {fundo_cert}")
                        str_lit.markdown(f"🪪 **Fundo de Carteirinha:** {fundo_cart}")

                    with col_acao:
                        str_lit.markdown(
                            "<div style='height: 25px;'></div>", unsafe_allow_html=True
                        )
                        if str_lit.button(
                            "✏️ Editar",
                            key=f"edit_ct_{ct.get('id')}",
                            use_container_width=True,
                        ):
                            modal_editar_ct(
                                ct_id=ct.get("id"),
                                name_atual=ct.get("name", ""),
                                full_name_atual=ct.get("full_name", ""),
                                cnpj_atual=ct.get("cnpj", ""),
                                phone_atual=ct.get("phone", ""),
                                address_atual=ct.get("full_address", ""),
                                logo_atual=ct.get("logo_url", ""),
                                fundo_cert_atual=ct.get("fundo_certificado_url", ""),
                                fundo_cart_atual=ct.get("fundo_carteirinha_url", ""),
                            )
        else:
            str_lit.info("Nenhum Centro de Treinamento cadastrado ainda.")

    except Exception as e:
        str_lit.error(f"Erro ao buscar CTs: {e}")


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
        str_lit.markdown("**🏷️ Logomarca do CT**")
        logo_file = str_lit.file_uploader(
            "Selecione a imagem da logomarca (PNG, JPG)",
            type=["png", "jpg", "jpeg"],
            key="up_novo_logo",
        )

        str_lit.markdown("---")
        str_lit.markdown("**🖼️ Fundo de Certificado**")
        str_lit.info(
            "💡 Aplicado automaticamente nos certificados (individual e empresa) deste CT."
        )
        fundo_file = str_lit.file_uploader(
            "Selecione a imagem do fundo de certificado (PNG, JPG)",
            type=["png", "jpg", "jpeg"],
            key="up_novo_fundo",
        )

        str_lit.markdown("---")
        str_lit.markdown("**🪪 Fundo de Carteirinha**")
        str_lit.info(
            "💡 Aplicado nas carteirinhas dos alunos emitidas para turmas deste CT."
        )
        fundo_cart_file = str_lit.file_uploader(
            "Selecione a imagem do fundo de carteirinha (PNG, JPG)",
            type=["png", "jpg", "jpeg"],
            key="up_novo_fundo_cart",
        )

        submit_novo_ct = str_lit.form_submit_button(
            "🚀 Cadastrar CT", type="primary", use_container_width=True
        )

        if submit_novo_ct:
            if not name:
                str_lit.warning("⚠️ O Nome Fantasia é obrigatório para cadastrar o CT.")
            else:
                try:
                    with str_lit.spinner("Salvando CT e fazendo upload das imagens..."):
                        url_logo = None
                        url_fundo = None
                        url_fundo_cart = None

                        if logo_file is not None:
                            url_logo = fazer_upload_arquivo(
                                logo_file, "logos", "ct_logo"
                            )

                        if fundo_file is not None:
                            url_fundo = fazer_upload_arquivo(
                                fundo_file, "certificados_fundos", "ct_fundo"
                            )

                        if fundo_cart_file is not None:
                            url_fundo_cart = fazer_upload_arquivo(
                                fundo_cart_file,
                                "certificados_fundos",
                                "ct_fundo_carteirinha",
                            )

                        novo_ct = {
                            "name": name.strip(),
                            "full_name": full_name.strip() if full_name else None,
                            "cnpj": cnpj.strip() if cnpj else None,
                            "phone": phone.strip() if phone else None,
                            "full_address": full_address.strip() if full_address else None,
                            "logo_url": url_logo,
                            "fundo_certificado_url": url_fundo,
                            "fundo_carteirinha_url": url_fundo_cart,
                        }

                        supabase.table("cts").insert(novo_ct).execute()

                        str_lit.success("✅ Centro de Treinamento cadastrado com sucesso!")
                        str_lit.rerun()
                except Exception as e:
                    str_lit.error(f"❌ Erro ao cadastrar CT: {e}")
