# Configurar a página de acesso (Supabase) — RM IA-Licita

A autenticação agora usa banco **Supabase**: cadastro com aprovação do
administrador, login com usuário ou e-mail e "esqueci a senha" por código
enviado por e-mail. O `config.yaml` e o `streamlit-authenticator` não são
mais usados.

## 1. Criar o projeto no Supabase (~5 min)

1. Acesse https://supabase.com → **New project**
2. Nome: `ialicita` · Região: **South America (São Paulo)** · Anote a senha do banco
3. Aguarde o projeto ficar pronto

## 2. Criar a tabela e migrar os usuários

1. No projeto, abra **SQL Editor**
2. Cole e rode o conteúdo de `supabase_schema_ialicita.sql`
3. Depois cole e rode o `migracao_usuarios.sql` — isso recria os usuários
   `roberto` (administrador) e `daysival` **com as mesmas senhas de hoje**

## 3. Pegar as chaves

Em **Settings → API**:
- **Project URL** → vai em `SUPABASE_URL`
- **service_role key** (em "Project API keys") → vai em `SUPABASE_SERVICE_KEY`

⚠️ A service_role dá acesso total ao banco: só nos secrets, nunca no código/GitHub.

## 4. Preencher os secrets

**Local (Mac):** edite `.streamlit/secrets.toml` e acrescente:

```toml
SUPABASE_URL = "https://SEU-PROJETO.supabase.co"
SUPABASE_SERVICE_KEY = "eyJ..."
SMTP_USUARIO = "rmfribeiro@gmail.com"
SMTP_SENHA = "senha-de-app-do-gmail"
```

**Streamlit Cloud:** app → Settings → Secrets → acrescentar as mesmas 4 linhas.
(A chave antiga `auth_config` pode ser removida.)

## 5. Senha de app do Gmail (para o "esqueci a senha")

1. https://myaccount.google.com/apppasswords (exige verificação em 2 etapas ativa)
2. Crie uma senha de app "IA-Licita" → copie as 16 letras em `SMTP_SENHA`

Sem essas chaves o app funciona normalmente — só o envio do código por
e-mail fica desativado (o usuário é orientado a falar com o administrador).

## 6. Instalar as dependências novas e testar

```bash
cd ~/Documents/Daysival
pip3 install supabase bcrypt
python3 -m streamlit run app.py
```

Teste: entrar com `roberto` (mesma senha) → deve aparecer o painel
**Administração de usuários** na barra lateral. Crie uma conta de teste na
aba "Criar conta", veja-a aparecer como pendente, aprove e entre com ela.

## Como funciona a aprovação

- Quem se cadastra fica **pendente** e não consegue entrar
- O administrador (você) aprova ou recusa na barra lateral
- Aprovados podem ser suspensos (e reativados) a qualquer momento

## Fase 2 — cobrança por uso (já incluída)

O mesmo `supabase_schema_ialicita.sql` também cria a tabela
`uso_relatorios` e a coluna `plano` em `usuarios`. Se você já tinha rodado
uma versão anterior do schema, **pode rodar o arquivo inteiro de novo** —
os comandos são idempotentes (`if not exists`).

Como funciona:
- Cada análise concluída em qualquer módulo grava 1 registro de uso
  (módulo, nível, preço de referência da época).
- O usuário vê na barra lateral o próprio uso do mês e o plano.
- O admin define o plano de cada usuário (Avulso/Básico/Profissional/
  Ilimitado) em "Todos os usuários" e vê em "💰 Uso e cobrança do mês"
  a consolidação por usuário com a cobrança sugerida (base do Pix manual).
- Preços e planos são calibrados num único lugar: `precos.py`.

## Arquivos desta mudança

| Arquivo | Papel |
|---|---|
| `auth_db.py` | Toda a lógica de autenticação (novo) |
| `uso_db.py` | Registro e consolidação do uso (novo, Fase 2) |
| `precos.py` | Tabela de preços, níveis e planos (novo, Fase 2) |
| `supabase_schema_ialicita.sql` | Cria `usuarios`, `uso_relatorios` e coluna `plano` |
| `migracao_usuarios.sql` | Recria roberto/daysival com as senhas atuais |
| `app.py` | Página de acesso, painel admin, contador de uso |
| `requirements.txt` | + `supabase`, `bcrypt` (− `streamlit-authenticator`) |
