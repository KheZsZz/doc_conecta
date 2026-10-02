import streamlit as st
import uuid
from src.config.database import supabase

st.title("✒️ Gestão de Responsáveis Técnicos")
st.markdown(
    "Cadastre os responsáveis técnicos e gerencie suas assinaturas para emissão nos certificados."
)


def fazer_upload_assinatura_resp(arquivo_upload, cpf: str):
    if arquivo_upload is None:
        return None
    try:
        extensao = arquivo_upload.name.split(".")[-1]
        nome_arquivo = f"assinatura_resp_{cpf}_{uuid.uuid4().hex}.{extensao}"
        file_bytes = arquivo_upload.read()

        supabase.storage.from_("assinaturas").upload(
            file=file_bytes,
            path=nome_arquivo,
            file_options={"content-type": arquivo_upload.type},
        )
        return supabase.storage.from_("assinaturas").get_public_url(nome_arquivo)
    except Exception as e:
        st.error(f"Erro no upload da assinatura: {e}")
        return None


tab_listar, tab_cadastrar = st.tabs(
    ["📋 Responsáveis Cadastrados", "➕ Novo Responsável Técnico"]
)

with tab_listar:
    try:
        res = (
            supabase.table("responsaveis_tecnicos")
            .select("*")
            .order("nome")
            .execute()
        )

        if res and res.data and len(res.data) > 0:
            for resp in res.data:
                rid = resp.get("id")
                nome = resp.get("nome", "Sem Nome")
                cpf = resp.get("cpf", "Sem CPF")
                re_val = resp.get("re") or ""
                is_active = resp.get("is_active", True)
                is_default = resp.get("is_default", False)
                assinatura_url = resp.get("assinatura_url")

                status_str = "🟢 Ativo" if is_active else "🔴 Inativo"
                default_str = "⭐ (Padrão)" if is_default else ""

                with st.container(border=True):
                    col1, col2, col3 = st.columns([3, 1, 1.5])
                    with col1:
                        st.markdown(f"**{nome}** {default_str}")
                        linha = f"**CPF:** {cpf}"
                        if re_val:
                            linha += f" | **RE:** {re_val}"
                        linha += f" | Status: {status_str}"
                        st.markdown(linha)
                    with col2:
                        if assinatura_url:
                            st.image(assinatura_url, width=120)
                        else:
                            st.caption("Sem assinatura")
                    with col3:
                        if not is_default:
                            if st.button(
                                "Definir como Padrão",
                                key=f"def_{rid}",
                                use_container_width=True,
                            ):
                                supabase.table("responsaveis_tecnicos").update(
                                    {"is_default": False}
                                ).neq("id", rid).execute()
                                supabase.table("responsaveis_tecnicos").update(
                                    {"is_default": True}
                                ).eq("id", rid).execute()
                                st.rerun()

                        novo_status = not is_active
                        rotulo_btn = "Desativar" if is_active else "Reativar"
                        if st.button(
                            rotulo_btn, key=f"act_{rid}", use_container_width=True
                        ):
                            supabase.table("responsaveis_tecnicos").update(
                                {"is_active": novo_status}
                            ).eq("id", rid).execute()
                            st.rerun()

                        if st.button(
                            "🗑️ Excluir", key=f"del_{rid}", use_container_width=True
                        ):
                            supabase.table("responsaveis_tecnicos").delete().eq(
                                "id", rid
                            ).execute()
                            st.success("Removido!")
                            st.rerun()
        else:
            st.info("ℹ️ Nenhum responsável técnico cadastrado ainda.")

    except Exception as e:
        st.error(f"Erro ao buscar responsáveis técnicos: {e}")

with tab_cadastrar:
    with st.form("form_novo_responsavel", clear_on_submit=True):
        nome_resp = st.text_input("Nome Completo*")
        cpf_resp = st.text_input("CPF*")
        re_resp = st.text_input(
            "RE (Registro)",
            help="Registro profissional. Aparece junto da assinatura nos certificados.",
        )
        is_default_new = st.checkbox("Definir como Responsável Técnico Padrão")

        st.markdown("**Assinatura Digitalizada (PNG sem fundo recomendada):**")
        arquivo_assinatura = st.file_uploader(
            "Upload da Assinatura", type=["png", "jpg", "jpeg"]
        )

        submit = st.form_submit_button(
            "💾 Salvar Responsável", type="primary", use_container_width=True
        )

        if submit:
            if not nome_resp or not cpf_resp:
                st.warning("⚠️ Preencha o Nome e o CPF obrigatórios.")
            else:
                cpf_limpo = "".join(filter(str.isdigit, cpf_resp))
                cpf_formatado = cpf_resp.strip()

                busca_duplicidade = (
                    supabase.table("responsaveis_tecnicos")
                    .select("id")
                    .eq("cpf", cpf_formatado)
                    .execute()
                )

                if (
                    busca_duplicidade
                    and hasattr(busca_duplicidade, "data")
                    and len(busca_duplicidade.data) > 0
                ):
                    st.error(
                        f"❌ O CPF {cpf_formatado} já está cadastrado no sistema!"
                    )
                else:
                    with st.spinner("Salvando cadastro..."):
                        url_assinatura = (
                            fazer_upload_assinatura_resp(arquivo_assinatura, cpf_limpo)
                            if arquivo_assinatura
                            else None
                        )

                        if is_default_new:
                            supabase.table("responsaveis_tecnicos").update(
                                {"is_default": False}
                            ).eq("is_default", True).execute()

                        payload = {
                            "nome": nome_resp.strip(),
                            "cpf": cpf_formatado,
                            "re": re_resp.strip() if re_resp else None,
                            "assinatura_url": url_assinatura,
                            "is_active": True,
                            "is_default": is_default_new,
                        }

                        try:
                            supabase.table("responsaveis_tecnicos").insert(
                                payload
                            ).execute()
                            st.success("✅ Responsável Técnico cadastrado com sucesso!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Erro ao salvar: {e}")
                            if "re" in str(e).lower():
                                st.info(
                                    "Execute no Supabase:\n"
                                    "`ALTER TABLE responsaveis_tecnicos ADD COLUMN IF NOT EXISTS re text;`"
                                )
