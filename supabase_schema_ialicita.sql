-- ==========================================================================
-- RM IA-Licita — schema de usuários (rodar no SQL Editor do Supabase)
-- ==========================================================================
create table if not exists usuarios (
  id            bigint generated always as identity primary key,
  usuario       text unique not null,
  email         text unique not null,
  nome          text not null,
  senha_hash    text not null,
  status        text not null default 'pendente',   -- pendente | aprovado | suspenso
  is_admin      boolean not null default false,
  criado_em     timestamptz not null default now(),
  reset_codigo  text,
  reset_expira  timestamptz
);

-- Segurança: liga o RLS. O app usa a chave service_role (que ignora RLS);
-- sem políticas criadas, a chave pública (anon) não enxerga nada.
alter table usuarios enable row level security;

-- Permissões para a chave secreta (service_role) — necessário nas chaves novas
grant usage on schema public to service_role;
grant select, insert, update, delete on all tables in schema public to service_role;
grant usage, select on all sequences in schema public to service_role;

-- ==========================================================================
-- Fase 2 — cobrança por uso
-- ==========================================================================
-- Plano comercial do usuário: avulso | basico | profissional | ilimitado
alter table usuarios add column if not exists
  plano text not null default 'avulso';

-- Cada linha = 1 relatório gerado (com preço de referência da época)
create table if not exists uso_relatorios (
  id         bigint generated always as identity primary key,
  usuario    text not null references usuarios (usuario),
  modulo     text not null,
  nivel      text not null,             -- Simples | Médio | Alto
  valor_ref  numeric(10,2) not null,    -- preço avulso na data
  criado_em  timestamptz not null default now()
);

create index if not exists idx_uso_usuario_data
  on uso_relatorios (usuario, criado_em);

alter table uso_relatorios enable row level security;

grant select, insert, update, delete on uso_relatorios to service_role;
