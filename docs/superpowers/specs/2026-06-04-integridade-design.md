# Módulo ia_integridade.py — Diagnóstico do Programa de Integridade Pública
**IA-Licita / RM Vértice Digital**
**Data:** 2026-06-04

---

## Base Legal e Normativa

| Instrumento | Objeto |
|---|---|
| Decreto 11.129/2022 | Programa de Integridade para órgãos e entidades da Administração Pública federal |
| IN CGU 21/2021 | Estruturação, execução e monitoramento do Programa de Integridade |
| Lei 12.846/2013, art. 7º III | Programa de integridade como atenuante na responsabilização |
| Decreto 8.420/2015 | Parâmetros de avaliação do programa de integridade |

---

## 1. Objetivo

Criar o módulo `ia_integridade.py` para diagnóstico do Programa de Integridade Pública (PIP) de prefeituras municipais, cobrindo os itens I, II, III, XII, XIII e XV da proposta do Dr. Daysival (comentários introdutórios, compromisso da alta gestão, diretrizes, responsabilização, metodologia de gestão e as três linhas de defesa).

O módulo produz um parecer com nível de maturidade em escala de 4 estágios (INEXISTENTE → INICIAL → EM DESENVOLVIMENTO → CONSOLIDADO), com achados e recomendações por dimensão e um resumo executivo para apresentação ao prefeito.

---

## 2. Integração com o App Existente

- Abordagem: nova `aba4` no `st.tabs()` de `app.py`
- Tab 1: `📄 Auditoria de Edital` — sem alteração
- Tab 2: `🔍 Due Diligence de Integridade` — sem alteração
- Tab 3: `📋 Auditoria de ETP` — sem alteração
- Tab 4: `🏛️ Diagnóstico de Integridade` — novo módulo

> **Atenção (app.py):** a linha atual é `aba1, aba2, aba3 = st.tabs([...])`. Adicionar Tab 4 exige alterar **tanto a lista quanto o destructuring**: `aba1, aba2, aba3, aba4 = st.tabs([..., "🏛️ Diagnóstico de Integridade"])`. Atualizar só a lista sem atualizar o unpacking levanta `ValueError` na inicialização.

---

## 3. Arquivos Novos

| Arquivo | Responsabilidade |
|---|---|
| `ia_integridade.py` | Questionário → chamada Anthropic → parecer JSON com maturidade por 6 dimensões |
| `relatorio_integridade.py` | Gera PDF do diagnóstico com reportlab |

**Arquivo modificado:**
- `app.py` — adiciona `aba4` e imports dos novos módulos

---

## 4. Fluxo Completo

```
Usuário preenche questionário (12 perguntas, 6 dimensões)
+ upload opcional de documentos da prefeitura (PDF/docx)
      ↓
[app.py — Tab 4]
  → Coleta respostas do formulário
  → Resolve api_key (mesmo padrão do Tab 3 ETP: tenta os.environ, depois st.secrets)
  → Se arquivos foram enviados:
      texto_docs, avisos = etp_extrator.extrair_texto(arquivos)  # retorna tuple[str, list[str]]
    Caso contrário:
      texto_docs, avisos = None, []
    ⚠️ NÃO chamar extrair_texto com lista vazia — levanta ValueError
  → Lê parecer_ddi da sessão se disponível
      ↓
[ia_integridade.py]
  → Monta prompt com respostas + texto dos docs + resumo DDI
  → Chamada única à API Anthropic via `_chamar_anthropic` local (urllib)
    ⚠️ Candidato a refatoração futura: ia_ddi e ia_etp também têm cópias privadas.
       Promover para ia_utils quando houver 3+ módulos usando o mesmo wrapper.
  → Aplica lógica de piso de maturidade
  → Retorna parecer dict
      ↓
[app.py — Tab 4]
  → Exibe badge de maturidade geral
  → 6 dimensões em expanders com nível e achados
  → Lista de prioridades (top 3 ações imediatas)
  → Resumo executivo
  → Botão download PDF
      ↓
[relatorio_integridade.py]
  → PDF para download
```

---

## 5. Módulo IA (`ia_integridade.py`)

### Função pública

```python
def diagnosticar(
    respostas: dict,
    texto_docs: str | None,
    api_key: str,
    modelo: str = _MODELO_PADRAO,
    parecer_ddi: dict | None = None,
) -> dict
```

### Questionário — 12 perguntas, 6 dimensões

| # | Chave | Dimensão (item da proposta) | Pergunta |
|---|---|---|---|
| 1 | `q_ato_formal` | Compromisso Alta Gestão (II) | Existe ato formal do prefeito instituindo o PIP? |
| 2 | `q_responsavel_designado` | Compromisso Alta Gestão (II) | Há responsável formalmente designado pelo PIP? |
| 3 | `q_diretrizes_publicadas` | Diretrizes de Integridade (III) | As diretrizes de integridade foram publicadas? |
| 4 | `q_diretrizes_divulgadas` | Diretrizes de Integridade (III) | Foram divulgadas a todos os servidores? |
| 5 | `q_base_legal_conhecida` | Base Legal / Comentários Introdutórios (I) | A autoridade superior conhece o marco legal do PIP (Decreto 11.129/2022, IN CGU 21/2021)? |
| 6 | `q_mecanismos_responsabilizacao` | Responsabilização (XII) | Existem mecanismos formais de responsabilização de servidores? |
| 7 | `q_precedentes_punicao` | Responsabilização (XII) | Já houve apuração e punição por irregularidades nesta prefeitura? |
| 8 | `q_plano_gestao` | Metodologia de Gestão (XIII) | Existe plano formal de gestão e acompanhamento do PIP? |
| 9 | `q_indicadores` | Metodologia de Gestão (XIII) | Existem indicadores definidos para monitorar o PIP? |
| 10 | `q_primeira_linha` | 1ª Linha de Defesa (XV) | Gestores de linha conhecem e exercem seus controles de conformidade? |
| 11 | `q_segunda_linha` | 2ª Linha de Defesa (XV) | Controle interno está estruturado e ativo? |
| 12 | `q_terceira_linha` | 3ª Linha de Defesa (XV) | Auditoria interna existe e funciona de forma independente? |

Cada resposta aceita: `"Sim"` | `"Não"` | `"Parcialmente"`.

### Estrutura do parecer (JSON retornado pela IA)

```json
{
  "maturidade_geral": "INEXISTENTE|INICIAL|EM DESENVOLVIMENTO|CONSOLIDADO",
  "dimensoes": {
    "compromisso_alta_gestao": {
      "nivel": "INEXISTENTE|INICIAL|EM DESENVOLVIMENTO|CONSOLIDADO",
      "achados": ["..."],
      "recomendacoes": ["..."]
    },
    "diretrizes_integridade": {
      "nivel": "...",
      "achados": ["..."],
      "recomendacoes": ["..."]
    },
    "base_legal_normativa": {
      "nivel": "...",
      "achados": ["..."],
      "recomendacoes": ["..."]
    },
    "responsabilizacao": {
      "nivel": "...",
      "achados": ["..."],
      "recomendacoes": ["..."]
    },
    "metodologia_gestao": {
      "nivel": "...",
      "achados": ["..."],
      "recomendacoes": ["..."]
    },
    "tres_linhas_defesa": {
      "nivel": "...",
      "achados": ["..."],
      "recomendacoes": ["..."]
    }
  },
  "prioridades": ["ação imediata 1", "ação imediata 2", "ação imediata 3"],
  "resumo_executivo": "parágrafo para apresentar ao prefeito",
  "base_legal": ["Decreto 11.129/2022", "IN CGU 21/2021", "Lei 12.846/2013, art. 7 III", "Decreto 8.420/2015"]
}
```

### Lógica de piso de maturidade (aplicada após resposta da IA)

Regras aplicadas **nesta ordem** (a mais restritiva primeiro):

1. Se **todos os 12 campos** == `"Não"` → força `maturidade_geral = "INEXISTENTE"`
2. Se `q_ato_formal` in `{"Não", "Parcialmente"}` **E** `q_responsavel_designado` in `{"Não", "Parcialmente"}` → `maturidade_geral` limitada ao máximo `"INICIAL"` (cobre tanto respostas "Não" quanto "Parcialmente" nos dois campos críticos)
3. Caso contrário: `maturidade_geral` retornada pela IA é aceita

> **Importante:** a Regra 1 deve ser verificada antes da Regra 2. Implementar como if/elif/else nessa ordem. Se invertidas, o caso all-Não será capturado pela Regra 2 (cap INICIAL) e a Regra 1 nunca emitirá INEXISTENTE.

### Integração com parecer DDI

Se `parecer_ddi` for fornecido, o prompt inclui o sub-dict do DDI acessado pelo caminho exato:

```python
pi = parecer_ddi.get("dimensoes", {}).get("programa_integridade", {})
# Campos disponíveis: pi["status"], pi["descricao"], pi["obrigatorio"], pi["pro_etica"]
```

Todos os quatro campos devem ser incluídos no contexto enviado à IA — `obrigatorio=True` + `pro_etica=False` é a combinação de maior risco legal e deve ser transmitida integralmente. Não altera a lógica de piso.

### Modelo

`claude-haiku-4-5-20251001` — configurável via `IA_LICITA_MODELO`.

---

## 6. Relatório PDF (`relatorio_integridade.py`)

### Função principal

```python
def gerar_pdf(municipio: str, respostas: dict, parecer: dict) -> bytes
```

### Estrutura do documento

1. **Cabeçalho:** logo RM Vértice Digital + data/hora + nome do município
2. **Nível de Maturidade Geral:** badge colorido
   - CONSOLIDADO → verde (#27AE60)
   - EM DESENVOLVIMENTO → azul (#2980B9)
   - INICIAL → amarelo (#F39C12)
   - INEXISTENTE → vermelho (#C0392B)
3. **Resumo Executivo:** parágrafo gerado pela IA
4. **Análise por Dimensão:** 6 seções com nível e achados
5. **Recomendações por Dimensão:** ações específicas por cada uma das 6 áreas
6. **Prioridades Imediatas:** top 3 ações em destaque
7. **Base Legal:** instrumentos normativos referenciados
8. **Rodapé:** `"Gerado por IA-Licita — RM Vértice Digital. Sujeito à verificação humana. Não substitui parecer jurídico."`

---

## 7. UI — Mudanças no `app.py`

### Tab 4 — fluxo em 2 etapas

**Etapa 1 — Questionário + documentos**
- 12 perguntas exibidas com `st.selectbox` ("Sim" / "Não" / "Parcialmente")
- Campo texto para nome do município
- `st.file_uploader` com `accept_multiple_files=True` para documentos de suporte — reutiliza `etp_extrator.extrair_texto`; retorna lista vazia quando nenhum arquivo é enviado (não chamar `extrair_texto` nesse caso)
- `api_key` resolvida localmente no início do bloco `with aba4:`, seguindo o mesmo padrão do Tab 3 ETP (tenta `os.environ["ANTHROPIC_API_KEY"]`, depois `st.secrets.get("ANTHROPIC_API_KEY")`)
- Botão "Gerar Diagnóstico"

**Etapa 2 — Resultado**
- Badge de maturidade geral
- 6 dimensões em `st.expander` com nível + achados + recomendações
- Prioridades em destaque (`st.info`)
- Resumo executivo
- Botão download PDF

---

## 8. Fora de Escopo (nesta versão)

- Itens IV–XI, XIV, XVI–XIX da proposta (cobertos por módulos futuros)
- Comparação entre diagnósticos de múltiplos municípios
- Histórico de diagnósticos anteriores por município
- Geração automática do Manual ou Plano de Integridade
