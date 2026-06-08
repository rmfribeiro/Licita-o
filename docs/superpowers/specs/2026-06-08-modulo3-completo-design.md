# Módulo 3 Completo — Avaliação de PI: Administração Pública e OSCs

**Base legal:** Decreto 12.304/2024, Art. 1º, I-III, Parágrafo Único; Lei 13.019/2014
**Produto:** IA-Licita — RM Vértice Digital
**Data:** 2026-06-08

---

## Visão Geral

Extensão da aba5 ("🏢 Avaliação de PI") para cobrir os três tipos de entidade previstos
no Decreto 12.304/2024, Art. 1º:

| Inciso | Tipo | Estado |
|--------|------|--------|
| I | Empresa Privada | ✅ implementado |
| II | Administração Pública | ⬜ este módulo |
| III | Organização da Sociedade Civil (OSC) | ⬜ este módulo |

O questionário de 17 parâmetros é o mesmo para todos os tipos. O que muda é:
o system prompt (contexto jurídico da entidade), as hipóteses legais disponíveis
e o label no PDF.

---

## Usuário e Caso de Uso

**Usuário:** gestor público, controlador interno, pregoeiro.

**Situações de uso novas:**
- Avaliar se um órgão/entidade da Administração Pública tem PI adequado antes de
  firmar convênio ou contratação de grande vulto.
- Avaliar se uma OSC tem PI estruturado antes de formalizar termo de fomento,
  colaboração ou acordo de cooperação (Lei 13.019/2014).

---

## Novas Constantes em `ia_pi_empresas.py`

### `TIPOS_ENTIDADE`

```python
TIPOS_ENTIDADE = MappingProxyType({
    "empresa_privada":       "Empresa Privada",
    "administracao_publica": "Administração Pública",
    "osc":                   "Organização da Sociedade Civil (OSC)",
})
```

### `HIPOTESES_POR_TIPO`

Substitui `HIPOTESES` (que era somente para empresa privada).

```
empresa_privada:
  grande_vulto  → "Grande Vulto (Decreto 12.304/2024, Art. 4º)"
  desempate     → "Desempate por PI (Lei 14.133/2021, Art. 60, IV)"
  reabilitacao  → "Reabilitação de Fornecedor (Lei 14.133/2021, Art. 163, Par. Único)"

administracao_publica:
  grande_vulto  → "Contratação de Grande Vulto (Decreto 12.304/2024, Art. 4º)"
  convenio      → "Convênio ou Transferência Voluntária"
  cooperacao    → "Cooperação Técnica Internacional"

osc:
  termo_fomento     → "Termo de Fomento (Lei 13.019/2014, Art. 16)"
  termo_colaboracao → "Termo de Colaboração (Lei 13.019/2014, Art. 16)"
  acordo_cooperacao → "Acordo de Cooperação (Lei 13.019/2014, Art. 16)"
```

`HIPOTESES` existente é removido — app.py passa a usar `HIPOTESES_POR_TIPO`.

### `SISTEMA_POR_TIPO`

System prompts distintos por tipo de entidade, todos referenciando o Decreto 12.304/2024.

- **empresa_privada:** texto atual (empresa privada que contrata com a Administração Pública)
- **administracao_publica:** órgão ou entidade da Administração Pública; avalia PI
  conforme Decreto 12.304/2024, Art. 1º, II
- **osc:** Organização da Sociedade Civil nos termos da Lei 13.019/2014; avalia PI
  conforme Decreto 12.304/2024, Art. 1º, III

---

## Alterações em `avaliar()`

**Assinatura nova:**
```python
def avaliar(
    respostas: dict,
    hipotese: str,
    texto_docs: str | None,
    api_key: str,
    modelo: str = _MODELO_PADRAO,
    tipo_entidade: str = "empresa_privada",
) -> dict
```

- `tipo_entidade` seleciona o system prompt via `SISTEMA_POR_TIPO[tipo_entidade]`.
- Retorno: inclui `tipo_entidade` no dict resultado (além de `scores` e `hipotese`).
- Default `"empresa_privada"` preserva comportamento atual para testes existentes.

---

## Fluxo de 3 Etapas — Alterações na aba5 do `app.py`

### Etapa 1 — Identificação (modificada)

Ordem dos campos:

1. CNPJ da entidade
2. **[novo]** Seletor "Tipo de Entidade": radio com Empresa Privada | Administração Pública | OSC
3. Seletor "Hipótese legal": opções filtradas por tipo via `HIPOTESES_POR_TIPO[tipo]`
4. Consulta à Receita Federal (sem mudança — funciona para CNPJ de qualquer entidade)

Session state key nova: `pi_tipo_entidade`.

### Etapa 2 — Questionário

Sem alteração. Os 17 parâmetros são os mesmos para todos os tipos.

### Etapa 3 — Resultado

Adicionar label "Tipo de Entidade: ..." abaixo da hipótese, acima do score geral.
Passar `tipo_entidade` para `gerar_pdf()`.

---

## Alterações em `relatorio_pi_empresas.py`

**Assinatura nova de `gerar_pdf()`:**
```python
def gerar_pdf(
    cnpj: str,
    razao_social: str,
    tipo_entidade: str,
    hipotese: str,
    parecer: dict,
) -> bytes
```

**No PDF:** linha "Tipo de Entidade: Administração Pública" na seção de identificação,
entre "Razão Social" e "Hipótese Legal". Usar `TIPOS_ENTIDADE` para traduzir a chave.

---

## Testes

### `tests/test_ia_pi_empresas.py` — testes novos

- `HIPOTESES_POR_TIPO` contém as 3 chaves; cada tipo tem pelo menos 3 hipóteses.
- `avaliar()` com `tipo_entidade="administracao_publica"` via mock → system prompt
  contém "Administração Pública".
- `avaliar()` com `tipo_entidade="osc"` via mock → system prompt contém "OSC".
- Testes existentes de `empresa_privada` continuam passando (parâmetro default).

### `tests/test_relatorio_pi_empresas.py` — testes novos

- `gerar_pdf()` com `tipo_entidade="administracao_publica"` → bytes não-vazios.
- `gerar_pdf()` com `tipo_entidade="osc"` → bytes não-vazios.
- `gerar_pdf()` com `tipo_entidade="empresa_privada"` (chamada antiga com novo parâmetro)
  → bytes não-vazios.

---

## Tratamento de Erros

- `tipo_entidade` desconhecido em `avaliar()`: `KeyError` em `SISTEMA_POR_TIPO` expõe
  o problema imediatamente (fail-fast). Sem fallback silencioso.
- `tipo_entidade` desconhecido em `gerar_pdf()`: mesmo comportamento via `TIPOS_ENTIDADE`.
- Demais erros (API, JSON, Receita Federal): sem mudança no tratamento existente.

---

## Fora de Escopo

- Questionários distintos por tipo de entidade (os 17 parâmetros são universais).
- Módulos 6, 7 e 8 (Reabilitação, Desempate, Empresa Pró-Ética) — abas separadas no roadmap.
- Consulta automática a bases de dados de OSCs além do CNPJ na Receita Federal.
