# Módulo 7 — Pesquisa de Mercado: Design Spec

**Data:** 2026-06-09
**Status:** Aprovado

---

## Objetivo

Ferramenta de pesquisa de preços de mercado para múltiplos itens, fundamentada no Art. 23 da Lei 14.133/2021 e IN SEGES/MGI 65/2021. O usuário fornece o TR em PDF (para extração dos itens) e os orçamentos de fornecedores em PDF; o sistema calcula o preço de referência por item (mediana com exclusão de desvios) e gera dois documentos: Mapa de Preços e Relatório de Pesquisa.

---

## Abordagem — Fluxo 3 etapas em aba única

Fluxo linear: extração de itens do TR → upload de orçamentos → resultado + PDFs.

---

## Arquitetura

### Novos arquivos

| Arquivo | Responsabilidade |
|---------|-----------------|
| `ia_pesquisa_mercado.py` | Constantes, extração de itens do TR, extração e cruzamento de cotações, cálculo de preço de referência, parecer IA |
| `relatorio_pesquisa_mercado.py` | Dois geradores de PDF: Mapa de Preços + Relatório de Pesquisa |
| `tests/test_ia_pesquisa_mercado.py` | Testes unitários do módulo de análise |
| `tests/test_relatorio_pesquisa_mercado.py` | Testes dos geradores de PDF |

### Arquivo modificado

| Arquivo | Mudança |
|---------|---------|
| `app.py` | Nova aba10 "🔍 Pesquisa de Mercado" |

### Reuso sem modificação

| Arquivo | Como reutilizado |
|---------|-----------------|
| `etp_extrator.py` | Upload e extração de texto do TR e dos PDFs de orçamentos |

### Fluxo de dados

```
PDF do TR → etp_extrator.extrair_texto()
          → ia_pesquisa_mercado.extrair_itens_tr()  [IA]
          → lista de itens editável pelo usuário
              → PDFs de orçamentos → etp_extrator.extrair_texto()
                                   → ia_pesquisa_mercado.analisar()
                                       → IA extrai cotações e cruza com itens_tr
                                       → calcular_referencia() por item  [Python puro]
                                       → IA gera parecer narrativo
                                           → relatorio_pesquisa_mercado.gerar_mapa_precos()
                                           → relatorio_pesquisa_mercado.gerar_relatorio_pesquisa()
```

---

## Base Legal

- **Art. 23, Lei 14.133/2021** — obrigatoriedade de pesquisa de preços para estimar o valor da contratação
- **IN SEGES/MGI 65/2021** — metodologia de pesquisa de preços: fontes, número mínimo de cotações, critérios de aceitabilidade

---

## UI — Etapas da Aba

### Etapa 1 — Extração de itens do TR

```
Objeto da pesquisa (descrição curta):
[_________________________________]  ex.: "Contratação de consultoria em TI"

Upload do TR (PDF):
[_________________________________]  [Extrair Itens →]

─── Itens identificados ───────────────────────────────────────
  #  | Descrição                        | Unidade | Qtd Est.
  1  | Serviço de consultoria em TI     | hora    | 500
  2  | Licença de software de segurança | un      | 10
  [+ Adicionar item]   [✏ Editar]   [🗑 Remover]

[Confirmar Itens e Avançar →]
```

### Etapa 2 — Upload de orçamentos

```
Orçamentos dos fornecedores (PDF, múltiplos arquivos):
[_____________________________________________]

[Analisar Pesquisa de Mercado →]
```

### Etapa 3 — Resultado

```
┌────────────────────────────────────────┐
│  PESQUISA VÁLIDA                       │  (badge verde/amarelo/vermelho)
└────────────────────────────────────────┘

Item 1 — Serviço de consultoria em TI (hora) — Qtd: 500
  Fornecedor A  (CNPJ: 00.000.000/0001-00): R$ 120,00  ✅
  Fornecedor B  (CNPJ: 11.111.111/0001-11): R$ 135,00  ✅
  Fornecedor C  (CNPJ: 22.222.222/0001-22): R$ 310,00  ❌ (excluído: 143% acima da mediana)
  Preço de referência: R$ 127,50/hora
  Subtotal estimado:   R$ 63.750,00

Item 2 — Licença de software de segurança (un) — Qtd: 10
  ⚠ Apenas 2 cotações válidas — insuficiente (mínimo: 3)

Valor total estimado: R$ XX.XXX,XX

Parecer: [texto gerado pela IA — justifica exclusões, aponta itens insuficientes]

Base legal: Art. 23, Lei 14.133/2021 + IN SEGES/MGI 65/2021

[⬇ Mapa de Preços (PDF)]    [⬇ Relatório de Pesquisa (PDF)]
```

---

## `ia_pesquisa_mercado.py`

### Constantes

```python
STATUS_ITEM: MappingProxyType[str, str]
# {"VALIDO": "VALIDO", "INSUFICIENTE": "INSUFICIENTE", "INEXEQUIVEL": "INEXEQUIVEL"}

STATUS_PESQUISA: MappingProxyType[str, str]
# {"VÁLIDA": "VÁLIDA", "COM RESSALVAS": "COM RESSALVAS", "INVÁLIDA": "INVÁLIDA"}

MIN_COTACOES_VALIDAS: int = 3       # mínimo de cotações válidas por item
DESVIO_MAX_PERCENTUAL: float = 0.50 # exclui cotações > 50% acima da mediana provisória
```

### Funções

```python
def extrair_itens_tr(
    texto_tr: str,
    api_key: str,
    modelo: str = _MODELO_PADRAO,
) -> list[dict]:
    """
    Extrai lista de itens do texto do TR via IA.
    Retorna: [{"id": 1, "descricao": str, "unidade": str, "quantidade_estimada": float|None}]
    Raises: RuntimeError se JSON inválido ou HTTPError/URLError.
    """

def calcular_referencia(cotacoes: list[float]) -> dict:
    """
    Python puro — sem IA. Determinístico e testável sem mock.
    1. Calcula mediana provisória de todas as cotações.
    2. Exclui cotações > mediana * (1 + DESVIO_MAX_PERCENTUAL).
    3. Recalcula mediana final com cotações válidas.
    Retorna: {
        "preco_referencia": float | None,
        "cotacoes_validas": list[float],
        "cotacoes_excluidas": list[dict],  # [{"preco": float, "motivo": str}]
        "status": "VALIDO" | "INSUFICIENTE",
    }
    Retorna status INSUFICIENTE se cotacoes_validas < MIN_COTACOES_VALIDAS.
    """

def analisar(
    itens_tr: list[dict],
    texto_orcamentos: str,
    api_key: str,
    modelo: str = _MODELO_PADRAO,
) -> dict:
    """
    1. IA extrai cotações dos orçamentos e cruza com itens_tr (matching semântico).
    2. Chama calcular_referencia() para cada item (sem IA).
    3. IA gera parecer narrativo com base nos resultados calculados.
    Retorna: {
        "status_geral": "VÁLIDA" | "COM RESSALVAS" | "INVÁLIDA",
        "itens_avaliados": [...],
        "fornecedores": [{"nome": str, "cnpj": str}],
        "valor_total_estimado": float | None,
        "parecer_narrativo": str,
        "base_legal": [str],
    }
    """
```

### Estrutura JSON — extração de cotações pela IA

```json
{
  "fornecedores": [
    {"nome": "Empresa A Ltda", "cnpj": "00.000.000/0001-00"}
  ],
  "itens_cotados": [
    {
      "item_id": 1,
      "descricao_no_orcamento": "Consultoria de TI",
      "cotacoes": [
        {"fornecedor": "Empresa A Ltda", "preco_unitario": 120.00},
        {"fornecedor": "Empresa B SA",   "preco_unitario": 135.00}
      ]
    }
  ]
}
```

### Lógica de status_geral

| Condição | Status |
|----------|--------|
| Todos os itens com status VALIDO | VÁLIDA |
| Algum item INSUFICIENTE, nenhum INEXEQUIVEL | COM RESSALVAS |
| Maioria dos itens INSUFICIENTE (> 50%) | INVÁLIDA |

### Lógica de calcular_referencia

```
cotacoes = [120.0, 135.0, 310.0]
mediana_provisoria = 135.0
limite_superior = 135.0 * 1.50 = 202.5
excluidas = [310.0]  → motivo: "R$ 310,00 — 130% acima da mediana provisória"
cotacoes_validas = [120.0, 135.0]
→ apenas 2 válidas < MIN_COTACOES_VALIDAS(3) → status INSUFICIENTE

cotacoes = [120.0, 135.0, 130.0]
mediana_provisoria = 130.0
limite_superior = 195.0
cotacoes_validas = [120.0, 135.0, 130.0]
mediana_final = 130.0
→ status VALIDO, preco_referencia = 130.0
```

---

## `relatorio_pesquisa_mercado.py`

```python
def gerar_mapa_precos(
    objeto: str,
    itens_avaliados: list[dict],
    fornecedores: list[dict],
    valor_total_estimado: float | None,
) -> bytes:
    """
    PDF tabular oficial para instrução do processo.
    Seções:
    1. Cabeçalho IA-Licita + data geração
    2. Identificação do objeto da pesquisa
    3. Tabela: item × fornecedor com preços unitários, marcação EXC. para excluídas,
       coluna Preço de Referência e Subtotal estimado
    4. Linha de total estimado
    5. Notas de rodapé: motivos de exclusão numerados
    6. Rodapé: "Sujeito a verificação humana. Não substitui aprovação do ordenador."
    """

def gerar_relatorio_pesquisa(
    objeto: str,
    itens_avaliados: list[dict],
    fornecedores: list[dict],
    parecer_narrativo: str,
    status_geral: str,
    valor_total_estimado: float | None,
) -> bytes:
    """
    PDF narrativo para instrução do processo.
    Seções:
    1. Cabeçalho IA-Licita + data geração
    2. Identificação do objeto
    3. Metodologia (Art. 23 Lei 14.133/2021 + IN SEGES/MGI 65/2021)
    4. Fornecedores consultados (lista com CNPJ)
    5. Análise por item: preços recebidos, exclusões justificadas, preço de referência
    6. Badge de status geral (VÁLIDA / COM RESSALVAS / INVÁLIDA)
    7. Parecer narrativo gerado pela IA
    8. Valor total estimado
    9. Rodapé: "Gerado por IA-Licita - RM Vertice Digital. Revisar antes de anexar ao processo."
    """
```

**Segurança de strings:** todos os campos dinâmicos passam por `html.escape()` antes de entrar em `Paragraph()` ou células de tabela.

---

## Testes

### `tests/test_ia_pesquisa_mercado.py`

**`TestConstantes`** (5 testes):
- `STATUS_ITEM`, `STATUS_PESQUISA`, `MIN_COTACOES_VALIDAS`, `DESVIO_MAX_PERCENTUAL` são MappingProxyType ou valores esperados
- `MIN_COTACOES_VALIDAS == 3`
- `DESVIO_MAX_PERCENTUAL == 0.50`

**`TestCalcularReferencia`** (6 testes, sem mock):
- 3 cotações válidas → mediana correta, status VALIDO
- Cotação acima do desvio máximo → excluída, mediana recalculada, status VALIDO (se restam ≥ 3)
- Após exclusão ficam < 3 cotações → status INSUFICIENTE
- Lista vazia → status INSUFICIENTE
- Todas excluídas → status INSUFICIENTE
- Exatamente 3 válidas no limite → status VALIDO

**`TestExtrairItensTR`** (3 testes, mock da API):
- Retorna lista de dicts com `descricao`, `unidade`, `quantidade_estimada`
- JSON malformado → `RuntimeError`
- `HTTPError` → `RuntimeError` com código HTTP

**`TestAnalisar`** (5 testes, mock da API):
- Todos itens válidos → `status_geral == "VÁLIDA"`
- Item sem cotações suficientes → item com `status == "INSUFICIENTE"`, pesquisa `"COM RESSALVAS"`
- Maioria dos itens insuficiente → `status_geral == "INVÁLIDA"`
- JSON malformado → `RuntimeError`
- `URLError` → `RuntimeError`

**Total: ~19 testes**

### `tests/test_relatorio_pesquisa_mercado.py`

- `gerar_mapa_precos()` retorna bytes com magic bytes PDF (`%PDF`)
- Conteúdo inclui nome do fornecedor
- Item INSUFICIENTE aparece no conteúdo
- `gerar_relatorio_pesquisa()` retorna bytes com magic bytes PDF
- Status VÁLIDA aparece no relatório narrativo

**Total: ~5 testes**

---

## Restrições

- `ANTHROPIC_API_KEY` nunca exposta em chat — somente via variável de ambiente
- `CGU_API_KEY` idem
- Tokens GitHub (`ghp_*`) idem
- `calcular_referencia()` é Python puro: nunca chama a API, resultado determinístico
