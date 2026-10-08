import mimetypes
import uuid

import streamlit as st

from src.config.database import supabase

st.title("🏢 Centros de Treinamento (CTs)")
st.markdown(
    "Gerencie os locais físicos de treinamento e suas logomarcas, "
    "fundos de certificado e de carteirinha."
)

tab_listar, tab_cadastrar = st.tabs(["📋 Listar CTs", "➕ Cadastrar CT"])


def _content_type(arquivo_upload) -> str:
    ct = (getattr(arquivo_upload, "type", None) or "").strip()
    if ct:
        return ct
    nome = getattr(arquivo_upload, "name", "") or ""
    guess, _ = mimetypes.guess_type(nome)
    if guess:
        return guess
    ext = nome.rsplit(".", 1)[-1].lower() if "." in nome else ""
    return {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "webp": "image/webp",
    }.get(ext, "application/octet-stream")


def fazer_upload_arquivo(arquivo_upload, bucket_name: str, prefixo: str):
    """
    Envia arquivo para o Storage do Supabase e devolve a URL pública.
    Tenta a API path/file e, em falha, a variante com kwargs legados.
    """
    if arquivo_upload is None:
        return None

    try:
        extensao = (arquivo_upload.name.rsplit(".", 1)[-1] or "png").lower()
        if extensao not in ("png", "jpg", "jpeg", "webp"):
            extensao = "png"
        nome_arquivo = f"{prefixo}_{uuid.uuid4().hex}.{extensao}"
        file_bytes = arquivo_upload.getvalue()
        if not file_bytes:
            st.error("Arquivo vazio — selecione a imagem novamente.")
            return None

        mime = _content_type(arquivo_upload)
        options = {
            "content-type": mime,
            "upsert": "true",
        }

        bucket = supabase.storage.from_(bucket_name)

        # API atual do supabase-py: upload(path, file, file_options=...)
        try:
            bucket.upload(nome_arquivo, file_bytes, file_options=options)
        except TypeError:
            # Fallback kwargs antigos
            bucket.upload(
                path=nome_arquivo,
                file=file_bytes,
                file_options=options,
            )
        except Exception as e1:
            # Segunda tentativa com upsert via header x-upsert
            try:
                bucket.upload(
                    nome_arquivo,
                    file_bytes,
                    file_options={
                        "content-type": mime,
                        "x-upsert": "true",
                    },
                )
            except Exception:
                raise e1

        url = bucket.get_public_url(nome_arquivo)
        # algumas versões devolvem string com query; ok para uso público
        return url
    except Exception as e:
        msg = str(e)
        st.error(f"❌ Erro ao fazer upload ({bucket_name}/{prefixo}): {msg}")
        if "Bucket not found" in msg or "not found" in msg.lower():
            st.info(
                f"Confira no Supabase Storage se o bucket **`{bucket_name}`** existe "
                "e está **público** (ou com policy de INSERT/SELECT para o app)."
            )
        if "row-level security" in msg.lower() or "policy" in msg.lower():
            st.info(
                "Policy do Storage bloqueando o upload. Em Storage → Policies, "
                "libere INSERT (e SELECT) no bucket para o role usado pelo app."
            )
        if "413" in msg or "too large" in msg.lower():
            st.info("Arquivo muito grande. Use PNG/JPG com poucos MB.")
        return None


@st.dialog("✏️ Editar Centro de Treinamento", width="medium")
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
    with st.form(f"form_editar_ct_{ct_id}"):
        novo_name = st.text_input("Nome Fantasia / Apelido do CT*", value=name_atual)
        novo_full_name = st.text_input(
            "Razão Social (Nome Completo)", value=full_name_atual
        )

        col1, col2 = st.columns(2)
        with col1:
            novo_cnpj = st.text_input("CNPJ", value=cnpj_atual)
        with col2:
            novo_phone = st.text_input("Telefone", value=phone_atual)

        novo_address = st.text_area("Endereço Completo", value=address_atual)

        st.markdown("---")
        st.markdown("**🏷️ Logomarca do CT (Opcional)**")
        if logo_atual:
            st.image(logo_atual, width=150, caption="Logo atual")
        nova_logo = st.file_uploader(
            "Substituir logomarca (PNG, JPG)",
            type=["png", "jpg", "jpeg", "webp"],
            key=f"up_edit_logo_{ct_id}",
        )

        st.markdown("---")
        st.markdown("**🖼️ Fundo de Certificado (Opcional)**")
        if fundo_cert_atual:
            st.image(fundo_cert_atual, width=150, caption="Fundo certificado atual")
        novo_fundo_cert = st.file_uploader(
            "Substituir fundo de certificado (PNG, JPG)",
            type=["png", "jpg", "jpeg", "webp"],
            key=f"up_edit_fundo_{ct_id}",
        )

        st.markdown("---")
        st.markdown("**🪪 Fundo de Carteirinha (Opcional)**")
        st.caption(
            "Imagem de fundo usada nas carteirinhas dos alunos deste CT."
        )
        if fundo_cart_atual:
            st.image(fundo_cart_atual, width=150, caption="Fundo carteirinha atual")
        novo_fundo_cart = st.file_uploader(
            "Substituir fundo de carteirinha (PNG, JPG)",
            type=["png", "jpg", "jpeg", "webp"],
            key=f"up_edit_fundo_cart_{ct_id}",
        )

        salvar = st.form_submit_button(
            "💾 Salvar Alterações", type="primary", use_container_width=True
        )

        if salvar:
            if not novo_name:
                st.warning("O Nome Fantasia é obrigatório.")
            else:
                try:
                    payload = {
                        "name": novo_name.strip(),
                        "full_name": novo_full_name.strip() if novo_full_name else None,
                        "cnpj": novo_cnpj.strip() if novo_cnpj else None,
                        "phone": novo_phone.strip() if novo_phone else None,
                        "full_address": novo_address.strip() if novo_address else None,
                    }

                    falhou_upload = False

                    if nova_logo is not None:
                        url_nova_logo = fazer_upload_arquivo(
                            nova_logo, "logos", "ct_logo"
                        )
                        if url_nova_logo:
                            payload["logo_url"] = url_nova_logo
                        else:
                            falhou_upload = True

                    if novo_fundo_cert is not None:
                        url_novo_fundo = fazer_upload_arquivo(
                            novo_fundo_cert, "certificados_fundos", "ct_fundo"
                        )
                        if url_novo_fundo:
                            payload["fundo_certificado_url"] = url_novo_fundo
                        else:
                            falhou_upload = True

                    if novo_fundo_cart is not None:
                        url_fundo_cart = fazer_upload_arquivo(
                            novo_fundo_cart,
                            "certificados_fundos",
                            "ct_fundo_carteirinha",
                        )
                        if url_fundo_cart:
                            payload["fundo_carteirinha_url"] = url_fundo_cart
                        else:
                            falhou_upload = True

                    supabase.table("cts").update(payload).eq("id", ct_id).execute()

                    if falhou_upload:
                        st.warning(
                            "CT atualizado, mas algum upload de imagem falhou. "
                            "Veja a mensagem de erro acima."
                        )
                    else:
                        st.success("✅ CT atualizado com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao atualizar CT: {e}")


with tab_listar:
    st.subheader("Centros de Treinamento Cadastrados")

    try:
        res_cts = supabase.table("cts").select("*").order("name").execute()

        if res_cts and res_cts.data:
            for ct in res_cts.data:
                with st.container(border=True):
                    col_logo, col_info, col_acao = st.columns([1, 4, 1])

                    with col_logo:
                        logo_url = ct.get("logo_url")
                        if logo_url:
                            st.image(logo_url, use_container_width=True)
                        else:
                            st.markdown(
                                "<div style='text-align: center; color: gray; padding-top: 20px;'>Sem Logo</div>",
                                unsafe_allow_html=True,
                            )

                    with col_info:
                        st.markdown(f"### {ct.get('name', 'Sem Nome')}")
                        st.markdown(
                            f"**Razão Social:** {ct.get('full_name', 'N/D')} | **CNPJ:** {ct.get('cnpj', 'N/D')}"
                        )
                        st.markdown(
                            f"📍 **Endereço:** {ct.get('full_address', 'Não informado')}"
                        )
                        st.markdown(
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
                        st.markdown(f"🖼️ **Fundo de Certificado:** {fundo_cert}")
                        st.markdown(f"🪪 **Fundo de Carteirinha:** {fundo_cart}")

                    with col_acao:
                        st.markdown(
                            "<div style='height: 25px;'></div>", unsafe_allow_html=True
                        )
                        if st.button(
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
            st.info("Nenhum Centro de Treinamento cadastrado ainda.")

    except Exception as e:
        st.error(f"Erro ao buscar CTs: {e}")


with tab_cadastrar:
    st.subheader("Cadastrar Novo CT")

    with st.form("form_novo_ct", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            name = st.text_input("Nome Fantasia / Apelido do CT*")
            cnpj = st.text_input("CNPJ (Apenas números)")

        with col2:
            full_name = st.text_input("Razão Social (Nome Completo)")
            phone = st.text_input("Telefone (Apenas números)")

        full_address = st.text_area("Endereço Completo")

        st.markdown("---")
        st.markdown("**🏷️ Logomarca do CT**")
        logo_file = st.file_uploader(
            "Selecione a imagem da logomarca (PNG, JPG)",
            type=["png", "jpg", "jpeg", "webp"],
            key="up_novo_logo",
        )

        st.markdown("---")
        st.markdown("**🖼️ Fundo de Certificado**")
        st.info(
            "💡 Aplicado automaticamente nos certificados (individual e empresa) deste CT."
        )
        fundo_file = st.file_uploader(
            "Selecione a imagem do fundo de certificado (PNG, JPG)",
            type=["png", "jpg", "jpeg", "webp"],
            key="up_novo_fundo",
        )

        st.markdown("---")
        st.markdown("**🪪 Fundo de Carteirinha**")
        st.info(
            "💡 Aplicado nas carteirinhas dos alunos emitidas para turmas deste CT."
        )
        fundo_cart_file = st.file_uploader(
            "Selecione a imagem do fundo de carteirinha (PNG, JPG)",
            type=["png", "jpg", "jpeg", "webp"],
            key="up_novo_fundo_cart",
        )

        submit_novo_ct = st.form_submit_button(
            "🚀 Cadastrar CT", type="primary", use_container_width=True
        )

        if submit_novo_ct:
            if not name:
                st.warning("⚠️ O Nome Fantasia é obrigatório para cadastrar o CT.")
            else:
                try:
                    with st.spinner("Salvando CT e fazendo upload das imagens..."):
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
                            "full_address": full_address.strip()
                            if full_address
                            else None,
                            "logo_url": url_logo,
                            "fundo_certificado_url": url_fundo,
                            "fundo_carteirinha_url": url_fundo_cart,
                        }

                        supabase.table("cts").insert(novo_ct).execute()

                        st.success("✅ Centro de Treinamento cadastrado com sucesso!")
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ Erro ao cadastrar CT: {e}")
