# IA-Licita — Plano de Implantação no Streamlit Community Cloud

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publicar o IA-Licita em produção no Streamlit Community Cloud, com todos os módulos atuais, segredos configurados corretamente e documentação de operação atualizada.

**Architecture:** O repositório GitHub já existe (`github.com/rmfribeiro/Licita-o`) e o Streamlit Cloud lê diretamente dele. O fluxo é: preparar o repo localmente → commit + push para GitHub → Streamlit Cloud detecta a mudança e faz o redeploy automático. Segredos (chaves de API, senha de acesso) ficam no painel do Streamlit Cloud, nunca no código.

**Tech Stack:** Streamlit Community Cloud (free tier), GitHub, Python 3.11, `requirements.txt` sem ferramentas de dev.

---

## Arquivos Envolvidos

| Arquivo | Ação | Por quê |
|---|---|---|
| `requirements.txt` | Modificar | Remover `pytest` (dev-only); não pertence ao ambiente de produção |
| `requirements-dev.txt` | Criar | Isolar dependências de desenvolvimento |
| `.gitignore` | Modificar | Garantir que `secrets.toml` nunca seja commitado |
| `.streamlit/secrets.toml.example` | Criar | Documentar todas as variáveis de segredo necessárias |
| `DEPLOY.md` | Reescrever | Guia atual — lista de arquivos e módulos é de uma versão antiga |
| `README.md` | Modificar | Seção "Estrutura" lista apenas arquivos do MVP original |
| `.streamlit/config.toml` | Sem mudança | Já tem `maxUploadSize = 200` correto |

---

### Task 1: Separar dependências de produção das de desenvolvimento

**Files:**
- Modify: `requirements.txt`
- Create: `requirements-dev.txt`

- [ ] **Step 1: Remover pytest de requirements.txt**

Conteúdo final de `requirements.txt`:

```
streamlit>=1.30
pdfplumber>=0.10
python-docx>=1.1
reportlab>=4.0
requests>=2.31
```

- [ ] **Step 2: Criar requirements-dev.txt**

```
-r requirements.txt
pytest>=8.0
```

- [ ] **Step 3: Atualizar devcontainer.json para usar requirements-dev.txt**

No arquivo `.devcontainer/devcontainer.json`, localizar a linha:

```
"[ -f requirements.txt ] && pip3 install --user -r requirements.txt; pip3 install --user streamlit;
```

Substituir por:

```
"[ -f requirements-dev.txt ] && pip3 install --user -r requirements-dev.txt; pip3 install --user streamlit;
```

Isso garante que GitHub Codespaces instala pytest automaticamente.

- [ ] **Step 4: Verificar que a instalação de produção funciona**

```bash
pip install -r requirements.txt --dry-run 2>&1 | tail -5
```

Saída esperada: `Would install ...` sem erros. Se já tudo instalado, sem output de erro.

- [ ] **Step 5: Verificar que os testes ainda rodam com requirements-dev**

```bash
python3 -m pytest tests/ -q 2>&1 | tail -3
```

Saída esperada: `168 passed` (ou mais se novos testes forem adicionados).

- [ ] **Step 6: Commit**

```bash
git add requirements.txt requirements-dev.txt .devcontainer/devcontainer.json
git commit -m "chore: separar pytest em requirements-dev.txt"
```

---

### Task 2: Proteger secrets — .gitignore + template de configuração

**Files:**
- Modify: `.gitignore`
- Create: `.streamlit/secrets.toml.example`

- [ ] **Step 1: Adicionar secrets.toml ao .gitignore**

Adicionar ao final de `.gitignore`:

```
# Secrets locais (NUNCA commitar)
.streamlit/secrets.toml
secrets.toml
```

- [ ] **Step 2: Verificar que o arquivo de exemplo não é ignorado**

```bash
git check-ignore .streamlit/secrets.toml && echo "IGNORADO OK"
git check-ignore .streamlit/secrets.toml.example && echo "PROBLEMA: exemplo também ignorado"
```

Saída esperada:
```
.streamlit/secrets.toml
IGNORADO OK
```
(segunda linha não deve aparecer — o `.example` não deve ser ignorado)

- [ ] **Step 3: Criar .streamlit/secrets.toml.example**

Conteúdo completo:

```toml
# secrets.toml.example — copie para .streamlit/secrets.toml e preencha
# NUNCA commitar o secrets.toml com valores reais

# Chave da API Anthropic (obrigatória para análise por IA)
# Obter em: https://console.anthropic.com/settings/keys
ANTHROPIC_API_KEY = "sk-ant-api03-..."

# Senha de acesso ao app (opcional — se ausente, app fica aberto)
APP_PASSWORD = "sua-senha-aqui"

# Chave da API do Portal da Transparência / CGU (opcional)
# Usada no módulo DDI para consultar CEIS, CNEP e situação cadastral
# Obter em: https://portaldatransparencia.gov.br/api-de-dados
CGU_API_KEY = "sua-chave-cgu-aqui"
```

- [ ] **Step 4: Criar .streamlit/secrets.toml local para dev (se ainda não existir)**

```bash
[ -f .streamlit/secrets.toml ] && echo "já existe" || cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Edite `.streamlit/secrets.toml` com os valores reais (NÃO commitar).

- [ ] **Step 5: Confirmar que secrets.toml não aparece no git status**

```bash
git status --short | grep secrets
```

Saída esperada: nenhuma linha com `secrets.toml` (apenas `secrets.toml.example` pode aparecer como novo arquivo).

- [ ] **Step 6: Commit**

```bash
git add .gitignore .streamlit/secrets.toml.example
git commit -m "chore: proteger secrets.toml e criar template de configuração"
```

---

### Task 3: Reescrever DEPLOY.md com guia atual completo

**Files:**
- Modify: `DEPLOY.md`

- [ ] **Step 1: Substituir DEPLOY.md pelo guia atualizado**

Conteúdo completo de `DEPLOY.md`:

```markdown
# Publicar o IA-Licita no Streamlit Community Cloud

Publicação gratuita com atualizações automáticas a cada push no GitHub.
Leva ~5 minutos na primeira vez; atualizações subsequentes são automáticas.

## Pré-requisitos

| Recurso | Gratuito? | Onde obter |
|---|---|---|
| Conta GitHub | ✓ | github.com |
| Conta Streamlit Community Cloud | ✓ | share.streamlit.io (login com GitHub) |
| Chave Anthropic API | Paga por uso | console.anthropic.com/settings/keys |
| Chave CGU API (opcional) | ✓ | portaldatransparencia.gov.br/api-de-dados |

## 1. Fazer push do código para GitHub

No terminal, na raiz do projeto:

```bash
git -c credential.helper= push origin main
```

Verifique em `https://github.com/rmfribeiro/Licita-o` que os commits chegaram.

## 2. Conectar ou atualizar no Streamlit Community Cloud

### Se for o primeiro deploy:

1. Acesse **share.streamlit.io** e faça login com GitHub.
2. Clique em **"Create app"**.
3. Selecione:
   - **Repository:** `rmfribeiro/Licita-o`
   - **Branch:** `main`
   - **Main file path:** `app.py`
   - **Python version:** `3.11`
4. Abra **"Advanced settings"** antes de clicar em Deploy.
5. No campo **Secrets**, cole o conteúdo abaixo (substituindo com seus valores reais):

```toml
ANTHROPIC_API_KEY = "sk-ant-api03-..."
APP_PASSWORD = "senha-de-acesso"
CGU_API_KEY = "chave-do-portal-da-transparencia"
```

6. Clique em **"Deploy"**. Em 1–3 minutos o app estará em `https://seu-app.streamlit.app`.

### Se o app já estava no ar (atualização):

O Streamlit Cloud detecta o push automaticamente e faz o redeploy em ~1 minuto.
Se precisar adicionar ou alterar segredos:

1. Acesse seu app no Streamlit Cloud.
2. Clique nos três pontos (⋮) no canto superior direito → **"Settings"**.
3. Seção **"Secrets"** — edite e salve.
4. O app reinicia automaticamente.

## 3. Variáveis de segredo (Secrets)

| Segredo | Obrigatório? | Efeito se ausente |
|---|---|---|
| `ANTHROPIC_API_KEY` | Para análise por IA | App abre mas análise IA desabilitada |
| `APP_PASSWORD` | Não | App fica público (sem senha de acesso) |
| `CGU_API_KEY` | Para DDI completo | Consultas CGU ficam desabilitadas |

## 4. Configuração de upload

O arquivo `.streamlit/config.toml` já define `maxUploadSize = 200` (200 MB).
Nenhuma configuração extra é necessária para editais grandes.

## 5. Atualizar o app depois

```bash
# Edite os arquivos, então:
git add -p   # ou: git add <arquivos>
git commit -m "descrição da mudança"
git -c credential.helper= push origin main
```

O Streamlit Cloud detecta o push e faz redeploy automático em ~1 minuto.

## 6. Custos estimados

| Item | Custo |
|---|---|
| GitHub + Streamlit Community Cloud | Gratuito |
| Análise IA por edital (Claude Haiku) | ~R$ 0,01–0,05 por edital |
| DDI com consultas CGU | Gratuito (API pública) |

## Aviso de uso

Ferramenta de apoio à decisão — não substitui parecer jurídico.
Os apontamentos devem ser confirmados por profissional habilitado.
```

- [ ] **Step 2: Commit**

```bash
git add DEPLOY.md
git commit -m "docs: reescrever DEPLOY.md com guia completo e módulos atuais"
```

---

### Task 4: Atualizar README.md — seção de estrutura

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Substituir a seção "Estrutura" no README.md**

Localizar a seção `## Estrutura` e o bloco de código que a segue (termina antes do próximo `---`).
Substituir pela seção abaixo (copiar exatamente, incluindo o bloco de código):

    ## Estrutura

    ```
    app.py                    — Interface Streamlit (6 abas)
    analisador.py             — Motor de regras e cálculo de risco de edital
    ia_semantica.py           — Análise semântica de edital (Claude)
    ia_utils.py               — Utilitários compartilhados: API Anthropic, helpers
    ia_integridade.py         — Diagnóstico de integridade do processo licitatório
    ia_etp.py                 — Análise do Estudo Técnico Preliminar (ETP)
    ia_ddi.py                 — Due Diligence de Integridade do licitante
    ia_contratos.py           — Análise de alterações contratuais (reajuste/repactuação/reequilíbrio)
    ia_recebimento.py         — Monitor de Recebimento Contratual (Art. 140 Lei 14.133/2021)
    ia_pi_empresas.py         — Avaliação de Programa de Integridade
    ddi_consultas.py          — Consultas CGU: CEIS, CNEP, Pro-Ética, CNPJ
    etp_extrator.py           — Extração de texto de ETP em PDF/DOCX
    rag.py                    — Busca semântica nos artigos da lei
    branding.py               — Logo e identidade visual
    relatorio_contratos.py    — PDF de alterações contratuais
    relatorio_ddi.py          — PDF de Due Diligence de Integridade
    relatorio_etp.py          — PDF de análise de ETP
    relatorio_integridade.py  — PDF de diagnóstico de integridade
    relatorio_pi_empresas.py  — PDF de avaliação de PI
    relatorio_recebimento.py  — PDF de recebimento contratual
    regras_14133.json         — Checklist de regras da Lei 14.133/2021
    base_juridica.json        — Artigos da lei para fundamentos legais
    branding.json             — Configuração de marca (nome, logo, cores)
    requirements.txt          — Dependências de produção
    requirements-dev.txt      — Dependências de desenvolvimento (pytest)
    DEPLOY.md                 — Guia de publicação no Streamlit Community Cloud
    ```

- [ ] **Step 2: Também atualizar a seção "Como rodar localmente" para usar requirements-dev.txt**

Localizar o bloco `### Instalação` com `pip install -r requirements.txt` e substituir por:

    ### Instalação

    ```bash
    git clone https://github.com/rmfribeiro/Licita-o.git
    cd Licita-o
    pip install -r requirements-dev.txt   # inclui pytest para rodar os testes
    ```

    ### Rodar os testes

    ```bash
    python3 -m pytest tests/ -v
    ```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: atualizar README com estrutura completa e requirements-dev"
```

---

### Task 5: Push de todos os commits para GitHub

**Files:** nenhum (operação git)

- [ ] **Step 1: Verificar commits pendentes**

```bash
git log origin/main..HEAD --oneline
```

Saída esperada: lista de commits locais que ainda não estão no GitHub (os 5+ commits do refactor de M4a + os commits desta task).

- [ ] **Step 2: Push**

```bash
git -c credential.helper= push origin main
```

Saída esperada: `To https://github.com/rmfribeiro/Licita-o.git` seguido de `main -> main`.

- [ ] **Step 3: Confirmar no GitHub**

```bash
git -c credential.helper= ls-remote origin HEAD
git rev-parse HEAD
```

As duas hashes devem ser idênticas.

---

### Task 6: Deploy / verificação no Streamlit Community Cloud

**Files:** nenhum (operação no painel web)

Esta task é executada no navegador em **share.streamlit.io**.

- [ ] **Step 1: Se o app ainda não existe — criar**

1. Acesse share.streamlit.io com login GitHub.
2. "Create app" → selecione `rmfribeiro/Licita-o`, branch `main`, main file `app.py`, Python `3.11`.
3. Abra "Advanced settings" → cole os secrets (ver Task 2 / DEPLOY.md seção 2).
4. Clique "Deploy".
5. Aguarde o banner verde "Your app is live!".

- [ ] **Step 2: Se o app já existe — verificar redeploy automático**

Após o push da Task 5, o Streamlit Cloud inicia redeploy automaticamente.
Abra o painel do app e aguarde o status voltar a "Running" (≤ 2 minutos).

- [ ] **Step 3: Verificar secrets no painel**

No painel do app → ⋮ → Settings → Secrets.
Confirme que as três variáveis estão presentes:
- `ANTHROPIC_API_KEY`
- `APP_PASSWORD`
- `CGU_API_KEY`

Se alguma estiver faltando, adicione-a agora e salve (app reinicia automaticamente).

---

### Task 7: Smoke test do app em produção

**Files:** nenhum (teste manual no navegador)

- [ ] **Step 1: Testar acesso e autenticação**

Abra a URL pública do app (ex: `https://rmfribeiro-licita-o-app-XXXX.streamlit.app`).
- Se `APP_PASSWORD` foi configurado: deve aparecer a tela de login.
- Digite a senha. O app deve abrir.
- Se não configurou senha: deve abrir direto.

- [ ] **Step 2: Testar aba "Auditoria de Edital" (Tab 1)**

1. Na aba "📄 Auditoria de Edital", marque "Usar IA".
2. Faça upload de qualquer PDF pequeno de edital.
3. Aguarde a análise completar (≤ 60s para editais ≤ 2 MB).
4. Verifique: índice de risco aparece, apontamentos listados, botão de download funciona.

Critério de aceite: sem erro `StreamlitAPIException` na tela; resultado aparece.

- [ ] **Step 3: Testar aba "Due Diligence de Integridade" (Tab 2)**

1. Na aba "🔍 Due Diligence de Integridade", insira o CNPJ `33.000.167/0001-01` (Petrobrás — dados públicos).
2. Clique em "Consultar".
3. Verifique: dados cadastrais aparecem, sem erro de API.

Critério de aceite: razão social "PETRÓLEO BRASILEIRO S A PETROBRAS" aparece.

- [ ] **Step 4: Testar aba "Auditoria de ETP" (Tab 3)**

1. Na aba "📋 Auditoria de ETP", cole qualquer texto curto no campo de ETP.
2. Clique em analisar.
3. Verifique: parecer de auditoria aparece com as 8 dimensões.

Critério de aceite: JSON de resposta renderizado com "adequacao_geral" visível.

- [ ] **Step 5: Confirmar que PDF de relatório faz download**

Em qualquer aba que gere PDF (DDI, ETP, Recebimento), após análise:
- Clique no botão "Baixar PDF".
- O arquivo deve abrir corretamente no PDF viewer do navegador.

Critério de aceite: PDF abre sem mensagem de "arquivo corrompido".

- [ ] **Step 6: Registrar URL pública**

Anotar a URL pública do app para compartilhar com clientes.
Formato: `https://[nome-do-app].streamlit.app`

---

## Checklist pós-implantação

- [ ] `git log origin/main..HEAD` retorna vazio (tudo sincronizado)
- [ ] App acessível na URL pública
- [ ] Login com APP_PASSWORD funciona
- [ ] Análise de edital com IA funciona (não exibe "ANTHROPIC_API_KEY ausente")
- [ ] Consulta DDI por CNPJ retorna dados da Receita Federal
- [ ] Download de PDF funciona em pelo menos uma aba
- [ ] `DEPLOY.md` no repo descreve o estado atual
