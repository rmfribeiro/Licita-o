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

6. Clique em **"Deploy"**. Em 1–3 minutos o app estará disponível em `https://seu-app.streamlit.app`.

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

Veja `.streamlit/secrets.toml.example` para o template completo.

## 4. Configuração de upload

O arquivo `.streamlit/config.toml` já define `maxUploadSize = 200` (200 MB).
Nenhuma configuração extra é necessária para editais grandes.

## 5. Atualizar o app depois

```bash
# Edite os arquivos, então:
git add <arquivos>
git commit -m "descrição da mudança"
git -c credential.helper= push origin main
```

O Streamlit Cloud detecta o push e faz redeploy automático em ~1 minuto.

## 6. Rodar localmente (desenvolvimento)

```bash
pip install -r requirements-dev.txt

# Crie .streamlit/secrets.toml a partir do template:
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edite .streamlit/secrets.toml com suas chaves reais

streamlit run app.py
```

Acesse `http://localhost:8501`.

## 7. Custos estimados

| Item | Custo |
|---|---|
| GitHub + Streamlit Community Cloud | Gratuito |
| Análise IA por edital (Claude Haiku) | ~R$ 0,01–0,05 por edital |
| DDI com consultas CGU | Gratuito (API pública) |

## Aviso de uso

Ferramenta de apoio à decisão — não substitui parecer jurídico.
Os apontamentos devem ser confirmados por profissional habilitado.
