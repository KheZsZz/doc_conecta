import streamlit as st
from src.config.database import supabase

st.title("🏢 Gestão de Empresas")
st.markdown(
    "Cadastre empresas (CNPJ) e **grupos empresariais** para unificar unidades "
    "com CNPJs diferentes no mesmo cliente."
)

tab_listar, tab_cadastrar, tab_grupos = st.tabs(
    ["📋 Empresas Cadastradas", "➕ Nova Empresa", "🗂️ Grupos Empresariais"]
)


def carregar_grupos() -> list[dict]:
    try:
        res = (
            supabase.table("grupos_empresariais")
            .select("*")
            .order("nome")
            .execute()
        )
        return res.data if res and isinstance(res.data, list) else []
    except Exception as e:
        st.warning(
            f"Não foi possível carregar grupos. Rode o SQL de criação no Supabase. ({e})"
        )
        return []


def mapa_grupos(grupos: list[dict]) -> dict[str, str]:
    """id -> nome"""
    return {g["id"]: g.get("nome") or "Sem nome" for g in grupos if g.get("id")}


def opcoes_grupo(grupos: list[dict]) -> tuple[list[str], dict[str, str | None]]:
    """
    Retorna (labels, label -> grupo_id|None).
    Primeira opção = sem grupo.
    """
    labels = ["— Sem grupo —"]
    mapa: dict[str, str | None] = {"— Sem grupo —": None}
    for g in grupos:
        lab = g.get("nome") or str(g.get("id"))
        labels.append(lab)
        mapa[lab] = g.get("id")
    return labels, mapa


def label_grupo_atual(grupo_id, grupos: list[dict]) -> str:
    if not grupo_id:
        return "— Sem grupo —"
    for g in grupos:
        if g.get("id") == grupo_id:
            return g.get("nome") or "— Sem grupo —"
    return "— Sem grupo —"


# ==========================================
# MODAL DE EDIÇÃO
# ==========================================
@st.dialog("✏️ Editar Empresa", width="medium")
def modal_editar_empresa(
    empresa_id,
    nome_atual,
    unidade_atual,
    cnpj_atual,
    endereco_atual,
    responsavel_atual,
    phone_atual,
    email_atual,
    grupo_id_atual,
    grupos: list[dict],
):
    labels, mapa = opcoes_grupo(grupos)
    idx_grupo = 0
    atual_label = label_grupo_atual(grupo_id_atual, grupos)
    if atual_label in labels:
        idx_grupo = labels.index(atual_label)

    with st.form(f"form_edit_empresa_{empresa_id}"):
        novo_nome = st.text_input("Razão Social*", value=nome_atual)

        grupo_label = st.selectbox(
            "Grupo empresarial",
            options=labels,
            index=idx_grupo,
            help="Une várias unidades/CNPJs do mesmo cliente.",
        )

        col1, col2 = st.columns(2)
        with col1:
            nova_unidade = st.text_input(
                "Unidade",
                value=unidade_atual if unidade_atual else "",
                help="Identificação livre da unidade (ex.: Indaiatuba, Planta 2).",
            )
            novo_cnpj = st.text_input(
                "CNPJ (Até 14 dígitos)",
                value=cnpj_atual if cnpj_atual else "",
                max_chars=14,
            )
            novo_telefone = st.text_input(
                "Telefone", value=phone_atual if phone_atual else ""
            )
        with col2:
            novo_responsavel = st.text_input(
                "Responsável", value=responsavel_atual if responsavel_atual else ""
            )
            novo_email = st.text_input(
                "E-mail", value=email_atual if email_atual else ""
            )

        novo_endereco = st.text_input(
            "Endereço Completo",
            value=endereco_atual if endereco_atual else "",
        )

        salvar = st.form_submit_button(
            "💾 Salvar Alterações", type="primary", use_container_width=True
        )

        if salvar:
            if not novo_nome.strip():
                st.warning("⚠️ A Razão Social é obrigatória.")
            else:
                try:
                    payload = {
                        "name": novo_nome.strip(),
                        "sigla": nova_unidade.strip() if nova_unidade else None,
                        "cnpj": novo_cnpj.strip() if novo_cnpj else None,
                        "full_address": novo_endereco.strip()
                        if novo_endereco
                        else None,
                        "responsavel": novo_responsavel.strip()
                        if novo_responsavel
                        else None,
                        "phone": novo_telefone.strip() if novo_telefone else None,
                        "email": novo_email.strip() if novo_email else None,
                        "grupo_id": mapa.get(grupo_label),
                    }
                    supabase.table("clients").update(payload).eq(
                        "id", empresa_id
                    ).execute()
                    st.success("✅ Empresa atualizada com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Erro ao atualizar empresa: {e}")
                    if "grupo_id" in str(e).lower():
                        st.info(
                            "Execute o SQL de grupos empresariais no Supabase "
                            "(coluna `grupo_id` em `clients`)."
                        )


grupos = carregar_grupos()
nomes_grupos = mapa_grupos(grupos)

# ==========================================
# ABA 1: LISTAGEM
# ==========================================
with tab_listar:
    st.subheader("Empresas e Clientes")

    col_b1, col_b2 = st.columns([3, 1])
    with col_b1:
        busca = st.text_input(
            "🔍 Buscar por nome, unidade, CNPJ ou grupo",
            placeholder="Ex: KION, Indaiatuba, 42365296...",
            key="busca_empresa",
        )
    with col_b2:
        filtro_grupo_labels = ["Todos os grupos"] + [
            g.get("nome") or "" for g in grupos
        ]
        filtro_grupo = st.selectbox(
            "Grupo",
            options=filtro_grupo_labels,
            key="filtro_grupo_lista",
        )

    try:
        response = supabase.table("clients").select("*").order("name").execute()

        if response and isinstance(response.data, list) and len(response.data) > 0:
            lista = response.data

            if filtro_grupo != "Todos os grupos":
                gid = next(
                    (g["id"] for g in grupos if g.get("nome") == filtro_grupo),
                    None,
                )
                lista = [e for e in lista if e.get("grupo_id") == gid]

            if busca.strip():
                q = busca.strip().lower()
                q_digits = "".join(ch for ch in q if ch.isdigit())
                filtradas = []
                for emp in lista:
                    nome = str(emp.get("name") or "").lower()
                    unidade = str(emp.get("sigla") or "").lower()
                    cnpj = str(emp.get("cnpj") or "")
                    cnpj_digits = "".join(ch for ch in cnpj if ch.isdigit())
                    gnome = str(
                        nomes_grupos.get(emp.get("grupo_id")) or ""
                    ).lower()
                    if (
                        q in nome
                        or q in unidade
                        or q in cnpj.lower()
                        or q in gnome
                        or (q_digits and q_digits in cnpj_digits)
                    ):
                        filtradas.append(emp)
                lista = filtradas

            if not lista:
                st.info("Nenhuma empresa encontrada com esse filtro.")
            else:
                st.caption(f"Exibindo **{len(lista)}** empresa(s).")
                for emp in lista:
                    eid = emp.get("id")
                    nome = emp.get("name", "Sem Nome")
                    unidade = emp.get("sigla", "") or ""
                    cnpj = emp.get("cnpj", "")
                    endereco = emp.get("full_address", "")
                    responsavel = emp.get("responsavel", "")
                    phone = emp.get("phone", "")
                    email = emp.get("email", "")
                    grupo_id = emp.get("grupo_id")
                    gnome = nomes_grupos.get(grupo_id) if grupo_id else None

                    unidade_display = f" · {unidade}" if unidade else ""

                    with st.container(border=True):
                        col_info, col_acoes = st.columns([5, 1])

                        with col_info:
                            st.markdown(f"**{nome}**{unidade_display}")

                            detalhes = []
                            if gnome:
                                detalhes.append(f"**Grupo:** {gnome}")
                            if cnpj:
                                detalhes.append(f"**CNPJ:** {cnpj}")
                            if unidade:
                                detalhes.append(f"**Unidade:** {unidade}")
                            if responsavel:
                                detalhes.append(f"**Resp.:** {responsavel}")
                            if phone:
                                detalhes.append(f"**Tel:** {phone}")
                            if email:
                                detalhes.append(f"**E-mail:** {email}")

                            if detalhes:
                                st.caption(" | ".join(detalhes))

                            if endereco:
                                st.caption(f"📍 {endereco}")

                        with col_acoes:
                            st.markdown(
                                "<div style='height: 10px;'></div>",
                                unsafe_allow_html=True,
                            )
                            if st.button(
                                "✏️",
                                key=f"edit_emp_{eid}",
                                help="Editar empresa",
                                use_container_width=True,
                            ):
                                modal_editar_empresa(
                                    eid,
                                    nome,
                                    unidade,
                                    cnpj,
                                    endereco,
                                    responsavel,
                                    phone,
                                    email,
                                    grupo_id,
                                    grupos,
                                )
        else:
            st.info("ℹ️ Nenhuma empresa cadastrada no momento.")

    except Exception as e:
        st.error(f"Erro ao carregar empresas: {e}")


# ==========================================
# ABA 2: NOVA EMPRESA
# ==========================================
with tab_cadastrar:
    st.subheader("Cadastrar Nova Empresa")

    labels, mapa = opcoes_grupo(grupos)

    with st.form("form_nova_empresa", clear_on_submit=True):
        nome_empresa = st.text_input("Razão Social*")

        grupo_label = st.selectbox(
            "Grupo empresarial",
            options=labels,
            help="Opcional. Une este CNPJ a outras unidades do mesmo cliente.",
        )

        col1, col2 = st.columns(2)
        with col1:
            unidade_empresa = st.text_input(
                "Unidade",
                help="Identificação livre da unidade (ex.: Indaiatuba, Planta 2).",
            )
            cnpj_empresa = st.text_input("CNPJ (Até 14 dígitos)", max_chars=14)
            phone_empresa = st.text_input("Telefone")
        with col2:
            responsavel_empresa = st.text_input("Responsável")
            email_empresa = st.text_input("E-mail")

        endereco_empresa = st.text_input("Endereço Completo")

        submit_btn = st.form_submit_button("Criar Empresa", type="primary")

        if submit_btn:
            if not nome_empresa.strip():
                st.warning("⚠️ A Razão Social é obrigatória.")
            else:
                try:
                    novo_payload = {
                        "name": nome_empresa.strip(),
                        "sigla": unidade_empresa.strip()
                        if unidade_empresa
                        else None,
                        "cnpj": cnpj_empresa.strip() if cnpj_empresa else None,
                        "full_address": endereco_empresa.strip()
                        if endereco_empresa
                        else None,
                        "responsavel": responsavel_empresa.strip()
                        if responsavel_empresa
                        else None,
                        "phone": phone_empresa.strip() if phone_empresa else None,
                        "email": email_empresa.strip() if email_empresa else None,
                        "grupo_id": mapa.get(grupo_label),
                    }
                    supabase.table("clients").insert(novo_payload).execute()
                    st.success(f"✅ Empresa '{nome_empresa}' cadastrada com sucesso!")
                    st.balloons()
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Erro ao cadastrar empresa: {e}")
                    if "grupo_id" in str(e).lower():
                        st.info(
                            "Execute o SQL de grupos empresariais no Supabase."
                        )


# ==========================================
# ABA 3: GRUPOS EMPRESARIAIS
# ==========================================
with tab_grupos:
    st.subheader("Grupos empresariais")
    st.caption(
        "Um grupo reúne várias empresas (CNPJs) do mesmo cliente — "
        "útil para pacotes de documentação do mês/ano."
    )

    with st.form("form_novo_grupo", clear_on_submit=True):
        col_g1, col_g2 = st.columns([3, 1])
        with col_g1:
            nome_grupo = st.text_input(
                "Nome do grupo*",
                placeholder="Ex.: KION / Dematic, Braskem, Grupo Pinheiros",
            )
        with col_g2:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            criar_grupo = st.form_submit_button(
                "➕ Criar grupo", type="primary", use_container_width=True
            )

        if criar_grupo:
            if not nome_grupo.strip():
                st.warning("Informe o nome do grupo.")
            else:
                try:
                    supabase.table("grupos_empresariais").insert(
                        {"nome": nome_grupo.strip()}
                    ).execute()
                    st.success(f"✅ Grupo **{nome_grupo.strip()}** criado.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao criar grupo: {e}")
                    st.code(
                        """
CREATE TABLE IF NOT EXISTS public.grupos_empresariais (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  nome text NOT NULL,
  created_at timestamptz DEFAULT now()
);

ALTER TABLE public.clients
  ADD COLUMN IF NOT EXISTS grupo_id uuid
  REFERENCES public.grupos_empresariais(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_clients_grupo_id ON public.clients(grupo_id);
                        """,
                        language="sql",
                    )

    st.markdown("---")

    if not grupos:
        st.info("Nenhum grupo cadastrado ainda.")
    else:
        # Contagem de empresas por grupo
        contagem: dict[str, int] = {}
        try:
            res_cli = supabase.table("clients").select("id, grupo_id").execute()
            for c in res_cli.data or []:
                gid = c.get("grupo_id")
                if gid:
                    contagem[gid] = contagem.get(gid, 0) + 1
        except Exception:
            pass

        for g in grupos:
            gid = g.get("id")
            nome = g.get("nome") or "Sem nome"
            n_emp = contagem.get(gid, 0)

            with st.container(border=True):
                c1, c2, c3 = st.columns([4, 1, 1])
                with c1:
                    st.markdown(f"**{nome}**")
                    st.caption(f"{n_emp} empresa(s) vinculada(s)")
                with c2:
                    if st.button(
                        "✏️",
                        key=f"edit_grp_{gid}",
                        help="Renomear",
                        use_container_width=True,
                    ):
                        st.session_state[f"rename_grp_{gid}"] = True
                with c3:
                    if st.button(
                        "🗑️",
                        key=f"del_grp_{gid}",
                        help="Excluir grupo",
                        use_container_width=True,
                    ):
                        try:
                            # desvincula empresas e remove grupo
                            supabase.table("clients").update(
                                {"grupo_id": None}
                            ).eq("grupo_id", gid).execute()
                            supabase.table("grupos_empresariais").delete().eq(
                                "id", gid
                            ).execute()
                            st.success("Grupo removido.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao excluir: {e}")

                if st.session_state.get(f"rename_grp_{gid}"):
                    with st.form(f"form_rename_{gid}"):
                        novo = st.text_input("Novo nome", value=nome)
                        if st.form_submit_button("Salvar nome"):
                            try:
                                supabase.table("grupos_empresariais").update(
                                    {"nome": novo.strip()}
                                ).eq("id", gid).execute()
                                st.session_state[f"rename_grp_{gid}"] = False
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro: {e}")
