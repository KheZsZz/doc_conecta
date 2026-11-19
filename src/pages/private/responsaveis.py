import streamlit as st
import uuid
from src.config.database import supabase
from src.pages.private.turmas.modals.emitir_documentos.data import (
    fetch_cursos_ids_do_responsavel,
    salvar_cursos_do_responsavel,
)

st.title("Responsáveis Técnicos")
st.markdown(
    "Cadastre os responsáveis técnicos, vincule os **cursos** de que são responsáveis "
    "e gerencie assinaturas para emissão nos certificados."
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


def _carregar_cursos_dict() -> dict[str, str]:
    try:
        res = supabase.table("cursos").select("id, name").order("name").execute()
        return {c["name"]: c["id"] for c in (res.data or []) if c.get("id") and c.get("name")}
    except Exception:
        return {}


@st.dialog("Editar Responsável Técnico", width="large")
def modal_editar_responsavel(
    rid: str,
    nome_atual: str,
    cpf_atual: str,
    re_atual: str,
    formacao_atual: str,
    assinatura_atual: str | None,
    ativo_atual: bool,
    default_atual: bool,
    cursos_dict: dict[str, str],
    cursos_vinculados_ids: list[str],
):
    with st.form(f"form_edit_resp_{rid}"):
        novo_nome = st.text_input("Nome Completo*", value=nome_atual or "")
        novo_cpf = st.text_input("CPF*", value=cpf_atual or "")
        novo_re = st.text_input(
            "RE (Registro)",
            value=re_atual or "",
            help="Registro profissional. Aparece junto da assinatura nos certificados.",
        )
        nova_formacao = st.text_input(
            "Formação / Especialização",
            value=formacao_atual or "",
            help="Ex.: Engenheiro de Segurança do Trabalho, Técnico em Segurança do Trabalho.",
        )

        nomes_cursos = list(cursos_dict.keys())
        ids_set = set(str(x) for x in (cursos_vinculados_ids or []))
        default_nomes = [n for n, cid in cursos_dict.items() if str(cid) in ids_set]
        cursos_sel = st.multiselect(
            "Cursos sob responsabilidade técnica",
            options=nomes_cursos,
            default=default_nomes,
            help="Este RT será sugerido automaticamente nas turmas desses cursos.",
        )

        st.markdown("---")
        st.write("**Assinatura**")
        if assinatura_atual:
            st.image(assinatura_atual, width=180, caption="Assinatura atual")

        arquivo_assinatura = st.file_uploader(
            "Enviar nova imagem de assinatura (PNG/JPG)",
            type=["png", "jpg", "jpeg"],
            key=f"up_edit_resp_{rid}",
        )

        novo_ativo = st.checkbox("Responsável ativo", value=bool(ativo_atual))
        novo_default = st.checkbox(
            "Fallback global (só se o curso não tiver RT vinculado)",
            value=bool(default_atual),
            help="Não é mais o padrão absoluto: só entra quando o curso da turma não tem RT vinculado.",
        )

        salvar = st.form_submit_button(
            "Salvar Alterações", type="primary", use_container_width=True
        )

        if salvar:
            if not (novo_nome or "").strip() or not (novo_cpf or "").strip():
                st.warning("Nome e CPF são obrigatórios.")
            else:
                try:
                    cpf_limpo = "".join(ch for ch in novo_cpf if ch.isdigit())
                    caminho_assinatura = assinatura_atual
                    if arquivo_assinatura is not None:
                        url_nova = fazer_upload_assinatura_resp(
                            arquivo_assinatura, cpf_limpo or "semcpf"
                        )
                        if url_nova:
                            caminho_assinatura = url_nova

                    if novo_default:
                        supabase.table("responsaveis_tecnicos").update(
                            {"is_default": False}
                        ).neq("id", rid).execute()

                    payload = {
                        "nome": novo_nome.strip(),
                        "cpf": novo_cpf.strip(),
                        "re": (novo_re or "").strip() or None,
                        "formacao": (nova_formacao or "").strip() or None,
                        "assinatura_url": caminho_assinatura,
                        "is_active": novo_ativo,
                        "is_default": novo_default,
                    }
                    supabase.table("responsaveis_tecnicos").update(payload).eq(
                        "id", rid
                    ).execute()

                    try:
                        ids_sel = [cursos_dict[n] for n in cursos_sel if n in cursos_dict]
                        salvar_cursos_do_responsavel(rid, ids_sel)
                    except Exception as e_vinc:
                        st.warning(
                            f"Dados salvos, mas vínculos de curso falharam: {e_vinc}. "
                            "Confira se a tabela responsavel_cursos existe no Supabase."
                        )

                    st.success("Responsável Técnico atualizado!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao atualizar: {e}")
                    if "formacao" in str(e).lower():
                        st.info(
                            "Execute no Supabase:\n"
                            "`ALTER TABLE responsaveis_tecnicos ADD COLUMN IF NOT EXISTS formacao text;`"
                        )


tab_listar, tab_cadastrar = st.tabs(
    ["Responsáveis Cadastrados", "Novo Responsável Técnico"]
)

cursos_dict_global = _carregar_cursos_dict()

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
                formacao_val = resp.get("formacao") or ""
                is_active = resp.get("is_active", True)
                is_default = resp.get("is_default", False)
                assinatura_url = resp.get("assinatura_url")
                cursos_ids = fetch_cursos_ids_do_responsavel(rid)
                nomes_vinc = [
                    n for n, cid in cursos_dict_global.items() if str(cid) in set(cursos_ids)
                ]

                status_str = "Ativo" if is_active else "Inativo"
                default_str = "(Fallback global)" if is_default else ""

                with st.container(border=True):
                    col1, col2, col3 = st.columns([3, 1, 1.5])
                    with col1:
                        st.markdown(f"**{nome}** {default_str}")
                        linha = f"**CPF:** {cpf}"
                        if re_val:
                            linha += f" | **RE:** {re_val}"
                        if formacao_val:
                            linha += f" | **Formação:** {formacao_val}"
                        linha += f" | Status: {status_str}"
                        st.markdown(linha)
                        if nomes_vinc:
                            st.caption("Cursos: " + ", ".join(nomes_vinc[:8]) + ("…" if len(nomes_vinc) > 8 else ""))
                        else:
                            st.caption("Nenhum curso vinculado.")
                    with col2:
                        if assinatura_url:
                            st.image(assinatura_url, width=120)
                        else:
                            st.caption("Sem assinatura")
                    with col3:
                        if st.button(
                            "Editar",
                            key=f"edit_resp_{rid}",
                            use_container_width=True,
                        ):
                            modal_editar_responsavel(
                                rid,
                                nome,
                                cpf,
                                re_val,
                                formacao_val,
                                assinatura_url,
                                is_active,
                                is_default,
                                cursos_dict_global,
                                cursos_ids,
                            )

                        if not is_default:
                            if st.button(
                                "Definir fallback",
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
                            "Excluir", key=f"del_{rid}", use_container_width=True
                        ):
                            try:
                                supabase.table("responsavel_cursos").delete().eq(
                                    "responsavel_id", rid
                                ).execute()
                            except Exception:
                                pass
                            supabase.table("responsaveis_tecnicos").delete().eq(
                                "id", rid
                            ).execute()
                            st.success("Removido!")
                            st.rerun()
        else:
            st.info("Nenhum responsável técnico cadastrado ainda.")

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
        formacao_resp = st.text_input(
            "Formação / Especialização",
            help="Ex.: Engenheiro de Segurança do Trabalho, Técnico em Segurança do Trabalho.",
        )
        cursos_sel_new = st.multiselect(
            "Cursos sob responsabilidade técnica",
            options=list(cursos_dict_global.keys()),
            help="Este RT será sugerido automaticamente nas turmas desses cursos.",
        )
        is_default_new = st.checkbox(
            "Fallback global (só se o curso não tiver RT vinculado)",
            help="Não é mais o padrão absoluto: só entra quando o curso da turma não tem RT vinculado.",
        )

        st.markdown("**Assinatura Digitalizada (PNG sem fundo recomendada):**")
        arquivo_assinatura = st.file_uploader(
            "Upload da Assinatura", type=["png", "jpg", "jpeg"]
        )

        submit = st.form_submit_button(
            "Salvar Responsável", type="primary", use_container_width=True
        )

        if submit:
            if not nome_resp or not cpf_resp:
                st.warning("Preencha o Nome e o CPF obrigatórios.")
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
                        f"O CPF {cpf_formatado} já está cadastrado no sistema!"
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
                            "formacao": formacao_resp.strip() if formacao_resp else None,
                            "assinatura_url": url_assinatura,
                            "is_active": True,
                            "is_default": is_default_new,
                        }

                        try:
                            ins = (
                                supabase.table("responsaveis_tecnicos")
                                .insert(payload)
                                .execute()
                            )
                            novo_id = None
                            if ins and ins.data:
                                novo_id = ins.data[0].get("id")
                            if novo_id and cursos_sel_new:
                                try:
                                    ids_sel = [
                                        cursos_dict_global[n]
                                        for n in cursos_sel_new
                                        if n in cursos_dict_global
                                    ]
                                    salvar_cursos_do_responsavel(novo_id, ids_sel)
                                except Exception as e_vinc:
                                    st.warning(
                                        f"RT salvo, mas vínculos de curso falharam: {e_vinc}. "
                                        "Rode o SQL da tabela responsavel_cursos no Supabase."
                                    )
                            st.success("Responsável Técnico cadastrado com sucesso!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao salvar: {e}")
                            if "formacao" in str(e).lower() or "re" in str(e).lower():
                                st.info(
                                    "Execute no Supabase:\n"
                                    "`ALTER TABLE responsaveis_tecnicos ADD COLUMN IF NOT EXISTS formacao text;`"
                                )
