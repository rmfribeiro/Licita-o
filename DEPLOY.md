# Publicar o demo web (sem engenheiro)

Objetivo: deixar uma página online onde o cliente sobe um edital e vê a auditoria. Usa o **Streamlit Community Cloud** (gratuito). Leva ~30 minutos na primeira vez.

## Antes de começar
Você vai precisar de:
- Uma conta no **GitHub** (gratuita) — github.com
- Uma conta no **Streamlit Community Cloud** (gratuita) — share.streamlit.io (entra com o GitHub)
- (Opcional, recomendado) uma **chave de API da Anthropic** para a análise por IA — console.anthropic.com

## Passo a passo

### 1. Subir os arquivos para um repositório no GitHub
Crie um repositório novo (pode ser privado) e coloque nele **todos** estes arquivos da pasta `iautora_licita`:

```
app.py
analisador.py
rag.py
ia_semantica.py
regras_14133.json
base_juridica.json
branding.json
branding.py
requirements.txt
```

(Os demais arquivos — geradores de parecer, lote, etc. — não são necessários para o demo, mas não atrapalham.)

### 2. Conectar no Streamlit
1. Entre em **share.streamlit.io** com sua conta GitHub.
2. Clique em **"Create app"** / "New app".
3. Selecione o repositório, o branch (`main`) e, em "Main file path", escreva **`app.py`**.

### 3. Configurar a chave de API (opcional, para a IA)
1. Na tela do app, abra **"Advanced settings"** (ou depois em "Settings → Secrets").
2. Cole:
   ```
   ANTHROPIC_API_KEY = "sua-chave-aqui"
   ```
3. Salve.

> Sem a chave, o app funciona normalmente, mas só com a camada de regras (sem a leitura semântica por IA).

### 4. Publicar
Clique em **"Deploy"**. Em 1–2 minutos o app fica no ar, com um endereço público (algo como `https://seu-app.streamlit.app`) que você pode mandar ao cliente ou abrir na reunião.

## Atualizar o app depois
Qualquer mudança que você fizer nos arquivos do GitHub (por exemplo, editar `branding.json` com sua marca, ou ajustar regras) é publicada automaticamente em segundos.

## Custos
- GitHub e Streamlit Community Cloud: **gratuitos**.
- API de IA: paga por uso, **centavos por edital** (só quando a análise por IA é usada).

## Segurança e limites (importante)
- Este é um **demo de validação**, não um produto de produção. Não use com dados sigilosos sem revisão.
- Para virar produto de verdade (vários usuários, autenticação, escala, hospedagem dedicada, hardening), aí sim entra trabalho de engenharia — mas só vale a pena depois que o cliente disser "sim".
- Mantenha a ressalva visível: ferramenta de apoio, não substitui parecer jurídico.
