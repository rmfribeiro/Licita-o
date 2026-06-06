# Módulo 4a — Monitor de Recebimento Contratual Design

## Objetivo

Adicionar a sub-aba "Recebimento Contratual" ao Monitor de Contratos (aba 6) do IA-Licita, permitindo que o gestor público descreva uma entrega e receba um parecer da IA sobre a aptidão para o recebimento provisório e definitivo, com checklist de condições e relatório PDF — tudo nos termos do Art. 140 da Lei 14.133/2021.

---

## Contexto no Projeto

A aba 6 ("Alterações Contratuais", M4b) é reorganizada para "Monitor de Contratos" com dois `st.tabs` internos:

- **Alterações Contratuais** — código M4b existente (sem alteração funcional)
- **Recebimento Contratual** — código M4a novo

Nenhum arquivo existente é deletado. O bloco `with aba6:` do `app.py` recebe um `st.tabs(["Alterações Contratuais", "Recebimento Contratual"])` no topo, e o conteúdo atual é movido para a primeira sub-aba.

---

## Arquitetura

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `ia_recebimento.py` | Criar | Constantes, `_chamar_anthropic()`, `analisar()` |
| `relatorio_recebimento.py` | Criar | `gerar_pdf()` — PDF com ReportLab |
| `tests/test_ia_recebimento.py` | Criar | Testes unitários (constantes + `analisar()`) |
| `tests/test_relatorio_recebimento.py` | Criar | Smoke tests do PDF |
| `app.py` | Modificar | Aba 6 → "Monitor de Contratos" com sub-abas |

Padrão idêntico ao M4b (`ia_contratos.py` / `relatorio_contratos.py`).

---

## `ia_recebimento.py`

### Constantes públicas (todas `types.MappingProxyType`)

```python
TIPOS_OBJETO = {
    "servico": "Serviço",
    "bem":     "Fornecimento de Bem",
    "obra":    "Obra",
}

PARECER_OPTIONS = {
    "APTO":               "APTO",
    "APTO COM RESSALVAS": "APTO COM RESSALVAS",
    "INAPTO":             "INAPTO",
}

STATUS_CONDICAO = {
    "ATENDIDA": "ATENDIDA",
    "PARCIAL":  "PARCIAL",
    "AUSENTE":  "AUSENTE",
}
```

### Função pública

```python
def analisar(
    tipo_objeto: str,           # "servico" | "bem" | "obra"
    dados_entrega: dict,        # campos do formulário
    texto_docs: str | None,     # texto extraído do upload (ou None)
    api_key: str,
    modelo: str = "claude-haiku-4-5-20251001",
) -> dict
```

Faz **uma única chamada** à API Anthropic e retorna:

```python
{**qualitativo, "tipo_objeto": tipo_objeto, "dados_entrega": dados_entrega}
```

Os valores locais (`tipo_objeto`, `dados_entrega`) sempre sobrescrevem os da IA. Lança `ValueError` para tipo inválido, `RuntimeError` para erros de API ou resposta não-JSON.

`dados_entrega` contém as chaves:
- `numero_contrato` (str, opcional)
- `objeto` (str)
- `data_entrega` (str, opcional)
- `descricao_entrega` (str)
- `nao_conformidades` (str, opcional)
- `valor_contrato` (float, opcional)

### Estrutura JSON esperada da IA

```json
{
  "tipo_objeto": "servico|bem|obra",
  "recebimento_provisorio": {
    "parecer": "APTO|APTO COM RESSALVAS|INAPTO",
    "condicoes": [
      {
        "descricao": "Descrição da condição verificada",
        "status": "ATENDIDA|PARCIAL|AUSENTE",
        "observacao": "Observação explicativa (pode ser vazio)"
      }
    ],
    "pendencias": ["Pendência identificada para o recebimento provisório"],
    "sintese": "Parágrafo conclusivo sobre o recebimento provisório."
  },
  "recebimento_definitivo": {
    "parecer": "APTO|APTO COM RESSALVAS|INAPTO",
    "condicoes": [
      {
        "descricao": "Descrição da condição verificada",
        "status": "ATENDIDA|PARCIAL|AUSENTE",
        "observacao": "Observação explicativa (pode ser vazio)"
      }
    ],
    "pendencias": ["Pendência identificada para o recebimento definitivo"],
    "sintese": "Parágrafo conclusivo sobre o recebimento definitivo."
  },
  "recomendacoes_gerais": ["Recomendação ao gestor"],
  "base_legal": ["Art. 140, I, Lei 14.133/2021"]
}
```

### Condições verificadas por tipo de objeto

**Serviço — Provisório:**
1. Serviço prestado conforme especificações do Termo de Referência
2. Medição elaborada pelo fiscal do contrato
3. Prazo contratual de execução respeitado
4. Documentação fiscal (NF/fatura) apresentada

**Serviço — Definitivo:**
1. Qualidade do serviço confirmada após período de verificação
2. Pendências do recebimento provisório sanadas
3. Autoridade competente habilitada para emitir o ateste final

**Bem — Provisório:**
1. Quantidade conferida conforme ordem de fornecimento
2. Qualidade aparente sem avarias visíveis
3. Nota fiscal e documentos de entrega presentes
4. Entrega realizada no local e prazo contratados

**Bem — Definitivo:**
1. Inspeção técnica concluída com laudo
2. Conformidade com especificações do TR confirmada
3. Garantia do fabricante registrada (se aplicável)

**Obra — Provisório:**
1. Obra concluída fisicamente conforme projeto
2. ART/RRT de conclusão anotada pelo responsável técnico
3. Medição final elaborada pela fiscalização
4. Vistoria realizada pela comissão de recebimento

**Obra — Definitivo:**
1. Período de observação decorrido sem defeitos aparentes
2. Ausência de vícios ocultos identificados
3. As-built entregue pelo contratado
4. Responsabilidade técnica do contratado formalmente encerrada

### Base legal

- Art. 140, I — recebimento provisório
- Art. 140, II — recebimento definitivo
- Art. 140, §1º — prazo de até 15 dias úteis para bens e serviços
- Art. 140, §2º — dispensa de comissão para contratos ≤ R$ 80.000,00
- Art. 140, §3º — obras e serviços de engenharia

---

## `relatorio_recebimento.py`

Função pública:

```python
def gerar_pdf(dados_entrega: dict, tipo_objeto: str, parecer: dict) -> bytes
```

Estrutura do PDF:
1. Cabeçalho IA-Licita — RM Vértice Digital
2. Identificação do contrato (tabela com os dados do formulário)
3. **Badge — Recebimento Provisório** (verde/amarelo/vermelho)
4. Síntese do provisório + checklist de condições + pendências
5. **Badge — Recebimento Definitivo** (verde/amarelo/vermelho)
6. Síntese do definitivo + checklist de condições + pendências
7. Recomendações gerais
8. Base legal
9. Rodapé padrão

Prefixo dos estilos ReportLab: `"recv_"` (evita conflito com `"cont_"` de `relatorio_contratos.py`).

---

## Interface — app.py

### Aba 6 reorganizada

```python
with aba6:
    st.subheader("Monitor de Contratos")
    _sub_aba_alt, _sub_aba_recv = st.tabs([
        "⚖️ Alterações Contratuais",
        "📦 Recebimento Contratual",
    ])

    with _sub_aba_alt:
        # bloco M4b existente — sem alteração funcional

    with _sub_aba_recv:
        # bloco M4a novo
```

### Sub-aba Recebimento Contratual

**Formulário:**
- Select "Tipo de objeto contratual" (Serviço / Fornecimento de Bem / Obra)
- Text input "Número do contrato" (placeholder: 001/2024)
- Text input "Objeto do contrato (resumido)"
- Text input "Data de entrega/conclusão" (placeholder: DD/MM/AAAA)
- Text area "Descrição do que foi entregue/executado"
- Text area "Não conformidades ou pendências identificadas (opcional)"
- Number input "Valor do contrato (R$)" (min 0.0)
- File uploader "Documentos de suporte (opcional — PDF ou DOCX)"
- Botão "Analisar Recebimento"

**Resultado:**

Dois badges lado a lado com `st.columns(2)`:

```
┌──────────────────────────┐  ┌──────────────────────────────┐
│ RECEBIMENTO PROVISÓRIO   │  │ RECEBIMENTO DEFINITIVO       │
│    🟢 APTO               │  │    🟡 APTO COM RESSALVAS     │
└──────────────────────────┘  └──────────────────────────────┘
```

Abaixo de cada badge:
- Síntese em `st.info()` com `_safe_md()`
- Checklist de condições: ✅ ATENDIDA / ⚠️ PARCIAL / ❌ AUSENTE + observação (via `st.markdown`)
- Pendências em `st.warning()` com `_safe_md()`

Seção comum ao final:
- Expander "Recomendações ao Gestor" com `st.info()` por item
- Expander "Base Legal" com `st.write()` por item
- Botão "⬇️ Baixar Relatório PDF"

Todos os campos LLM passam por `_safe_md()`. Campos em blocos `unsafe_allow_html=True` (badges) passam por `html.escape()`.

---

## Tratamento de Erros

Idêntico ao M4b:
- `HTTPError` → `RuntimeError("Falha na API Anthropic: HTTP {code} ...")`
- `URLError`/`OSError` → `RuntimeError("Falha na API Anthropic: ...")`
- Resposta não-JSON → `RuntimeError("Resposta da API não contém JSON válido: ...")`
- Resposta não-dict → `RuntimeError("Resposta inesperada da API: objeto JSON esperado, recebeu ...")`
- Tipo inválido → `ValueError("Tipo de objeto inválido: ...")`

Erros exibidos via `st.error(str(_e))` na interface.

---

## Testes

### `tests/test_ia_recebimento.py` (~15 testes)

**Constantes:**
- `TIPOS_OBJETO` tem 3 entradas (servico, bem, obra)
- `PARECER_OPTIONS` tem 3 entradas
- `STATUS_CONDICAO` tem 3 entradas (ATENDIDA, PARCIAL, AUSENTE)
- Todas as constantes são `MappingProxyType`

**`analisar()`:**
- Tipo inválido → `ValueError`
- Retorno tem `recebimento_provisorio` e `recebimento_definitivo`
- Cada bloco tem `parecer`, `condicoes`, `pendencias`, `sintese`
- `tipo_objeto` local sempre prevalece sobre o valor da IA
- `dados_entrega` preservados no retorno
- `HTTPError` → `RuntimeError` com "HTTP 401"
- `URLError` → `RuntimeError`
- Resposta não-JSON no envelope → `RuntimeError` com "não é JSON válido"
- Resposta não-dict → `RuntimeError` com "objeto JSON esperado"
- `content: null` na resposta → não levanta exceção (guard `or []`)
- Item não-dict em `content` → ignorado (guard `isinstance`)

### `tests/test_relatorio_recebimento.py` (~5 testes)

- PDF retorna bytes não vazios com magic bytes `%PDF`
- Todos os pareceres possíveis (APTO, APTO COM RESSALVAS, INAPTO) não quebram
- Listas nulas (`pendencias: null`, `recomendacoes_gerais: null`) não quebram
- Condição não-dict em `condicoes` é ignorada

---

## Critérios de Aceitação

1. Sub-aba "Recebimento Contratual" visível em produção dentro de "Monitor de Contratos"
2. Formulário com todos os campos renderiza sem erros
3. Análise retorna dois pareceres distintos (provisório + definitivo) com checklist de condições
4. PDF gerado contém os dois badges e as respectivas checklists
5. Todos os campos LLM passam por `_safe_md()` ou `html.escape()`
6. Guard `(dados.get("content") or []) + isinstance(b, dict)` presente no `_chamar_anthropic()`
7. Todos os testes passam (baseline atual: 141)
