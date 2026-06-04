# Módulo 10 — Auditoria do ETP (Estudo Técnico Preliminar)
**IA-Licita / RM Vértice Digital**
**Data:** 2026-06-04

---

## Base Legal e Normativa

| Instrumento | Objeto |
|---|---|
| Lei 14.133/2021, art. 18, I | Obrigatoriedade do ETP na fase preparatória |
| IN SEGES/MGI 58/2022 | Estrutura, conteúdo e requisitos do ETP |
| Decreto 7.746/2012 | Critérios de sustentabilidade nas contratações |
| IN SLTI 01/2010 | Sustentabilidade ambiental nas contratações públicas |

---

## 1. Objetivo

Adicionar ao IA-Licita o Módulo 10 — Auditoria de ETP como Tab 3 no `app.py`, permitindo que o usuário envie o ETP e documentos complementares (PDF ou Word), receba uma análise por IA das 8 dimensões da IN SEGES/MGI 58/2022 e faça download do parecer em PDF.

---

## 2. Integração com o App Existente

- Abordagem: adicionar `aba3` ao `st.tabs()` já existente
- Tab 1: `📄 Auditoria de Edital` — sem alteração
- Tab 2: `🔍 Due Diligence de Integridade` — sem alteração
- Tab 3: `📋 Auditoria de ETP` — novo módulo

```python
aba1, aba2, aba3 = st.tabs([
    "📄 Auditoria de Edital",
    "🔍 Due Diligence de Integridade",
    "📋 Auditoria de ETP"
])
```

---

## 3. Arquivos Novos

| Arquivo | Responsabilidade |
|---|---|
| `etp_extrator.py` | Extrai texto de PDF (pdfplumber) e Word (python-docx); concatena múltiplos arquivos |
| `ia_etp.py` | Chamada única à API Anthropic via urllib → parecer JSON por 8 dimensões |
| `relatorio_etp.py` | Gera PDF do parecer com reportlab |

**Arquivo modificado:**
- `app.py` — adiciona `aba3` e imports dos novos módulos

---

## 4. Fluxo Completo

```
Usuário faz upload de 1–N arquivos (PDF ou .docx)
      ↓
[etp_extrator.py]
  → Extrai texto de cada arquivo
  → Concatena com separadores [ARQUIVO: nome]
  → Trunca em 50k chars se necessário (aviso ao usuário)
      ↓
[ia_etp.py]
  → Chamada única à API Anthropic (urllib, mesmo padrão de ia_semantica.py)
  → Parecer JSON com 8 dimensões + adequação geral
      ↓
[app.py — Tab 3]
  → Exibe badge de adequação geral
  → 8 dimensões em expanders com ícone de status
  → Pontos críticos e recomendações
  → Botão download PDF
      ↓
[relatorio_etp.py]
  → PDF para download
```

---

## 5. Extração de Texto (`etp_extrator.py`)

### Função principal
```python
def extrair_texto(arquivos: list) -> tuple[str, list[str]]
# Retorna: (texto_concatenado, lista_de_avisos)
```

### Por formato

| Extensão | Biblioteca | Comportamento |
|---|---|---|
| `.pdf` | `pdfplumber` (existente) | Extrai página a página; ignora imagens e páginas sem texto |
| `.docx` | `python-docx` (existente) | Extrai parágrafos e conteúdo de tabelas |
| Outros | — | Aviso de formato não suportado; arquivo ignorado |

### Formato de concatenação
```
[ARQUIVO: nome_do_arquivo_1.pdf]
<texto extraído do arquivo 1>

[ARQUIVO: nome_do_arquivo_2.docx]
<texto extraído do arquivo 2>
```

### Limite de texto
- Máximo: 50.000 caracteres (mesmo limite de `ia_semantica.py`)
- Se ultrapassado: trunca e adiciona aviso na lista de avisos
- Aviso exibido ao usuário na tela antes de gerar o parecer

### Tratamento de erros
- Arquivo corrompido ou sem texto extraível → aviso + continua com os demais arquivos
- Todos os arquivos falharem → `ValueError` com mensagem clara (não chama a IA)

---

## 6. Camada de IA (`ia_etp.py`)

### Função principal
```python
def analisar_etp(texto: str, api_key: str, modelo: str) -> dict
```

### Padrão técnico
- Usa `urllib.request` diretamente (sem SDK anthropic) — mesmo padrão de `ia_semantica.py`
- Inclui `_extrair_json()` robusto (remove fences de código, localiza JSON balanceado)

### As 8 Dimensões (IN SEGES/MGI 58/2022)

| # | Dimensão | Referência |
|---|---|---|
| 1 | Descrição da Necessidade | art. 6º, I da IN 58/2022 |
| 2 | Alinhamento Estratégico | art. 6º, II — vinculação ao planejamento institucional |
| 3 | Requisitos da Contratação | art. 6º, III — especificações técnicas e qualitativas |
| 4 | Levantamento de Mercado | art. 6º, IV — pesquisa de alternativas e fornecedores |
| 5 | Estimativa de Quantidade e Valor | art. 6º, V e VI — metodologia e razoabilidade |
| 6 | Sustentabilidade | art. 6º, IX — Decreto 7.746/2012 + IN SLTI 01/2010 |
| 7 | Parcelamento do Objeto | art. 6º, X — justificativa para contratar integral ou parcelado |
| 8 | Posicionamento Conclusivo | art. 6º, XI — recomendação final fundamentada |

### Estrutura do parecer (JSON retornado pela IA)
```json
{
  "adequacao_geral": "ADEQUADO | ADEQUADO COM RESSALVAS | INADEQUADO",
  "dimensoes": {
    "descricao_necessidade":      {"status": "ok|alerta|critico", "descricao": "..."},
    "alinhamento_estrategico":    {"status": "ok|alerta|critico", "descricao": "..."},
    "requisitos_contratacao":     {"status": "ok|alerta|critico", "descricao": "..."},
    "levantamento_mercado":       {"status": "ok|alerta|critico", "descricao": "..."},
    "estimativa_quantidade_valor":{"status": "ok|alerta|critico", "descricao": "..."},
    "sustentabilidade":           {"status": "ok|alerta|critico", "descricao": "..."},
    "parcelamento":               {"status": "ok|alerta|critico", "descricao": "..."},
    "posicionamento_conclusivo":  {"status": "ok|alerta|critico", "descricao": "..."}
  },
  "pontos_criticos": ["...", "..."],
  "recomendacoes": ["...", "..."],
  "base_legal": [
    "IN SEGES/MGI 58/2022",
    "Lei 14.133/2021, art. 18, I",
    "Decreto 7.746/2012"
  ]
}
```

### Adequação geral
Determinada pela IA com base no conjunto das 8 dimensões — sem regra de piso automática (diferente do DDI onde sanções forçam risco mínimo).

### Modelo
`claude-haiku-4-5-20251001` — configurável via variável de ambiente `IA_LICITA_MODELO`.

---

## 7. Relatório PDF (`relatorio_etp.py`)

### Função principal
```python
def gerar_pdf(nomes_arquivos: list[str], avisos: list[str], parecer: dict) -> bytes
```

### Estrutura do documento
1. **Cabeçalho:** logo RM Vértice Digital + data/hora
2. **Documentos analisados:** lista dos arquivos enviados
3. **Avisos de extração:** lista de avisos (truncagem, arquivos ignorados), se houver
4. **Adequação Geral:** badge colorido
   - ADEQUADO → verde (#27AE60)
   - ADEQUADO COM RESSALVAS → amarelo (#F39C12)
   - INADEQUADO → vermelho (#C0392B)
5. **Análise por Dimensão:** 8 seções com status (✓/⚠/✗) e descrição da IA
6. **Pontos Críticos:** lista numerada
7. **Recomendações:** lista numerada com orientações ao gestor
8. **Base Legal:** instrumentos normativos referenciados
9. **Rodapé:** `"Gerado por IA-Licita — RM Vértice Digital. Sujeito à verificação humana. Não substitui parecer jurídico."`

Usa `reportlab` (já presente em `requirements.txt`). Retorna `bytes` para `st.download_button`.

---

## 8. UI — Mudanças no `app.py`

### Imports adicionados
```python
import etp_extrator
import ia_etp
import relatorio_etp
```

### Tab 3 — fluxo em 2 etapas

**Etapa 1 — Upload e análise**
```python
with aba3:
    st.subheader("Auditoria de ETP — Estudo Técnico Preliminar")
    st.caption("IN SEGES/MGI 58/2022 · Lei 14.133/2021, art. 18, I")

    arquivos = st.file_uploader(
        "ETP e documentos complementares (PDF ou Word)",
        type=["pdf", "docx"],
        accept_multiple_files=True,
        key="etp_arquivos"
    )

    if st.button("Analisar ETP", type="primary", key="btn_etp"):
        with st.spinner("Extraindo texto e analisando com IA..."):
            texto, avisos = etp_extrator.extrair_texto(arquivos)
            parecer = ia_etp.analisar_etp(texto, api_key, modelo)
        st.session_state["etp_parecer"] = parecer
        st.session_state["etp_avisos"] = avisos
        st.session_state["etp_nomes"] = [f.name for f in arquivos]
```

**Etapa 2 — Resultado**
```python
    if "etp_parecer" in st.session_state:
        parecer = st.session_state["etp_parecer"]
        # badge de adequação geral
        # 8 dimensões em expanders
        # pontos críticos e recomendações
        pdf = relatorio_etp.gerar_pdf(nomes, avisos, parecer)
        st.download_button("Baixar Relatório PDF", pdf, "ETP_auditoria.pdf", "application/pdf")
```

---

## 9. Configuração

Nenhuma nova variável de ambiente. Usa `ANTHROPIC_API_KEY` já existente.

---

## 10. Fora de Escopo (nesta versão)

- Análise comparativa entre ETP e edital (cruzamento entre Módulo 1 e Módulo 10)
- Extração automática de valores monetários para validação de estimativas
- Verificação de pesquisa de preços (Módulo 12 futuro)
- Análise do DFD — Documento de Formalização de Demandas (futuro)
