-- =============================================================================
-- DocFacil Conecta — Hardening Supabase (RLS + auditoria de importação)
-- Execute no SQL Editor do projeto. Revise políticas antes de produção.
-- =============================================================================

-- 1) Auditoria de uploads
CREATE TABLE IF NOT EXISTS public.import_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  origem text,
  arquivo text,
  sucesso boolean,
  alunos_processados int DEFAULT 0,
  matriculas_criadas int DEFAULT 0,
  mensagem text,
  user_id text,
  user_email text,
  created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_import_logs_created ON public.import_logs (created_at DESC);

-- 2) Habilitar RLS (ajuste fino conforme auth real do Supabase)
ALTER TABLE public.usuarios ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.alunos ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.matriculas ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.turmas ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.import_logs ENABLE ROW LEVEL SECURITY;

-- AVISO:
-- O app Streamlit atual autentica usuários na tabela `usuarios` (não no Auth JWT
-- do Supabase). Com chave **anon**, políticas RLS precisam refletir isso.
-- Opções:
--   A) Migrar login para Supabase Auth e usar auth.uid()
--   B) Manter app com service role em backend privado (NÃO no Streamlit público)
--   C) Políticas permissivas temporárias só para service role / backend
--
-- Abaixo: políticas de EXEMPLO para uso com service role desligado do client
-- e Edge Functions / backend autenticado. Adapte antes de aplicar em prod.

-- Exemplo: turmas legíveis apenas se ct_id do JWT claim bater (placeholder)
-- DROP POLICY IF EXISTS turmas_select_ct ON public.turmas;
-- CREATE POLICY turmas_select_ct ON public.turmas
--   FOR SELECT
--   USING (
--     ct_id::text = coalesce(auth.jwt() ->> 'ct_id', ct_id::text)
--     OR (auth.jwt() ->> 'role') = 'admin'
--   );

-- Enquanto o login for 100% na tabela usuarios + Streamlit, o controle de CT
-- continua no Python (ct_id_atual). RLS completo exige Auth JWT.

COMMENT ON TABLE public.import_logs IS
  'Log de importações de planilhas (subir listas / lote).';

-- 3) Checklist operacional
-- [ ] Secrets Streamlit: SUPABASE_URL + SUPABASE_ANON_KEY (nunca service_role)
-- [ ] AUTH_PEPPER forte e único
-- [ ] CHECKIN_SECRET forte e único
-- [ ] Rotacionar senhas após mudança de pepper (hashes antigos invalidam)
-- [ ] Revisar grants: revoke all from anon on sensitive tables se necessário
