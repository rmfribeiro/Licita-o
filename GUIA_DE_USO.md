# Guia de uso — IA-Licita (piloto)

Como rodar uma auditoria de edital e gerar o parecer, do zero. Não exige ser programador — é seguir os passos.

## 1. Preparar o ambiente (uma vez)

Precisa de **Python 3** instalado. No terminal, dentro da pasta `iautora_licita`:

```
pip install pdfplumber python-docx reportlab streamlit
```

Para a **análise automática por IA** (opcional, mas recomendada), crie uma conta na Anthropic, gere uma chave de API e configure-a:

```
export ANTHROPIC_API_KEY="sua-chave-aqui"
```

Sem a chave, tudo funciona em modo offline (camada de regras); a leitura semântica fica a cargo de quem opera.

## 2. Personalizar o timbre (uma vez)

Edite o arquivo **`branding.json`** com os dados da sua empresa:

```json
{
  "empresa": "Nome da sua empresa",
  "tagline": "Auditoria de Editais — Lei 14.133/2021",
  "contato": "email · telefone · site",
  "cor_primaria": "1F4E79",
  "logo": "logo.png"
}
```

Se preencher `logo` com o nome de um PNG na mesma pasta, ele aparece no topo do parecer.

## 3. Auditar um edital

```
python3 analisador.py CAMINHO/edital.pdf relatorio.html
```

Isso gera `relatorio.html` (abre no navegador) com o índice de risco, o nível de atenção e os apontamentos.

- Com IA ao vivo: acrescente `--ia` (usa a chave de API).
- PDF escaneado (sem texto) é detectado e avisado — aplique OCR antes.

## 4. Gerar o parecer em Word

Os pareceres de exemplo são gerados por `gerar_parecer.py` (edital municipal) e `gerar_parecer_trf3.py` (federal). Para um novo edital, copie um desses arquivos, ajuste os dados (identificação e achados) e rode:

```
python3 gerar_parecer.py
```

O Word sai com o seu timbre (do `branding.json`).

> Evolução natural: transformar isso num gerador único que lê os achados de um JSON — assim você não edita código a cada parecer.

## 5. Auditar vários editais de uma vez (lote)

```
python3 lote.py pasta_com_os_pdfs/
```

Gera `painel_lote.html` (dashboard com a estatística agregada) e `lote_resultado.json`.

## 6. Demonstração web (tela clicável)

```
streamlit run app.py
```

Abre uma página onde se sobe o PDF e se vê o relatório na hora. Para publicar online, veja **`DEPLOY.md`**.

## Mapa dos arquivos

| Arquivo | Para que serve |
|---|---|
| `analisador.py` | Motor: lê o PDF, aplica as regras, calcula risco, gera o relatório |
| `regras_14133.json` | As 30 regras de conformidade |
| `base_juridica.json` | Os 30 artigos da lei (base do RAG) |
| `rag.py` | Busca o artigo certo para cada apontamento |
| `ia_semantica.py` | Camada de IA (prompt blindado + validação); precisa da chave de API |
| `lote.py` | Auditoria em lote + painel |
| `gerar_parecer*.py` | Geram o parecer em Word com o timbre |
| `gerar_proposta_comercial.py` | Gera a proposta comercial de 1 página |
| `branding.json` / `branding.py` | Seu timbre (nome, contato, cor, logo) |
| `app.py` | Demo web (Streamlit) |

## Lembrete

Ferramenta de apoio — não substitui o parecer jurídico. Todo apontamento deve ser confirmado por profissional habilitado.
