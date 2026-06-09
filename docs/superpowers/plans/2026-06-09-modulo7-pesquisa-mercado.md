# Módulo 7 — Pesquisa de Mercado: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a market-price research tool (Art. 23, Lei 14.133/2021 + IN SEGES/MGI 65/2021) that accepts a TR PDF and supplier quote PDFs, computes item reference prices (median with outlier exclusion), and generates a Mapa de Preços and a Relatório de Pesquisa in PDF.

**Architecture:** Three new files (`ia_pesquisa_mercado.py`, `relatorio_pesquisa_mercado.py`, and their test files) plus a new aba10 in `app.py`. `ia_pesquisa_mercado.py` makes two API calls inside `analisar()`: one to extract and match quotes, one to generate the narrative parecer. `calcular_referencia()` is pure Python with no API dependency. `etp_extrator.extrair_texto()` is reused without modification.

**Tech Stack:** Python 3.9, Anthropic claude-haiku-4-5-20251001, ReportLab (PDF), pdfplumber (PDF tests), Streamlit, pytest + unittest.mock.

**Spec:** `docs/superpowers/specs/2026-06-09-modulo7-pesquisa-mercado-design.md`

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `ia_pesquisa_mercado.py` | Constants, `calcular_referencia()`, `extrair_itens_tr()`, `analisar()` |
| Create | `relatorio_pesquisa_mercado.py` | `gerar_mapa_precos()`, `gerar_relatorio_pesquisa()` |
| Create | `tests/test_ia_pesquisa_mercado.py` | ~19 unit tests for ia_pesquisa_mercado |
| Create | `tests/test_relatorio_pesquisa_mercado.py` | ~5 tests for PDF generators |
| Modify | `app.py` lines 35, 101–111, 1818 | Add imports + aba10 block |

---

## Task 1: Constants + `calcular_referencia()` (pure Python, no mock)

**Files:**
- Create: `ia_pesquisa_mercado.py`
- Create: `tests/test_ia_pesquisa_mercado.py`

---

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ia_pesquisa_mercado.py` with:

```python
from __future__ import annotations
import json
import pytest
import urllib.error
from unittest.mock import patch, MagicMock
import ia_pesquisa_mercado


class TestConstantes:
    def test_status_item_tem_chaves_esperadas(self):
        assert set(ia_pesquisa_mercado.STATUS_ITEM.keys()) == {
            "VALIDO", "INSUFICIENTE", "INEXEQUIVEL"
        }

    def test_status_pesquisa_tem_chaves_esperadas(self):
        assert set(ia_pesquisa_mercado.STATUS_PESQUISA.keys()) == {
            "VÁLIDA", "COM RESSALVAS", "INVÁLIDA"
        }

    def test_min_cotacoes_validas_e_3(self):
        assert ia_pesquisa_mercado.MIN_COTACOES_VALIDAS == 3

    def test_desvio_max_percentual_e_50_porcento(self):
        assert ia_pesquisa_mercado.DESVIO_MAX_PERCENTUAL == 0.50

    def test_constantes_sao_mapping_proxy(self):
        import types
        assert isinstance(ia_pesquisa_mercado.STATUS_ITEM, types.MappingProxyType)
        assert isinstance(ia_pesquisa_mercado.STATUS_PESQUISA, types.MappingProxyType)


class TestCalcularReferencia:
    def test_tres_cotacoes_validas_retorna_mediana_correta(self):
        # [120, 130, 135]: mediana=130
        r = ia_pesquisa_mercado.calcular_referencia([120.0, 130.0, 135.0])
        assert r["status"] == "VALIDO"
        assert r["preco_referencia"] == 130.0
        assert len(r["cotacoes_validas"]) == 3
        assert r["cotacoes_excluidas"] == []

    def test_cotacao_acima_desvio_excluida_tres_validas_restam(self):
        # [120, 130, 140, 310]: mediana_prov=135, limite=202.5, 310 excluída
        # validas=[120,130,140], mediana_final=130
        r = ia_pesquisa_mercado.calcular_referencia([120.0, 130.0, 140.0, 310.0])
        assert r["status"] == "VALIDO"
        assert r["preco_referencia"] == 130.0
        assert len(r["cotacoes_excluidas"]) == 1
        assert r["cotacoes_excluidas"][0]["preco"] == 310.0

    def test_apos_exclusao_menos_de_3_retorna_insuficiente(self):
        # [120, 135, 310]: mediana_prov=135, limite=202.5, 310 excluída → 2 válidas < 3
        r = ia_pesquisa_mercado.calcular_referencia([120.0, 135.0, 310.0])
        assert r["status"] == "INSUFICIENTE"
        assert r["preco_referencia"] is None

    def test_lista_vazia_retorna_insuficiente(self):
        r = ia_pesquisa_mercado.calcular_referencia([])
        assert r["status"] == "INSUFICIENTE"
        assert r["preco_referencia"] is None

    def test_menos_de_3_cotacoes_retorna_insuficiente(self):
        r = ia_pesquisa_mercado.calcular_referencia([100.0, 110.0])
        assert r["status"] == "INSUFICIENTE"
        assert r["preco_referencia"] is None

    def test_exatamente_3_cotacoes_iguais_retorna_valido(self):
        r = ia_pesquisa_mercado.calcular_referencia([100.0, 100.0, 100.0])
        assert r["status"] == "VALIDO"
        assert r["preco_referencia"] == 100.0
```

- [ ] **Step 2: Run to verify failure**

```bash
cd /Users/robertomauricioferreiraribeiro/Documents/Daysival
pytest tests/test_ia_pesquisa_mercado.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'ia_pesquisa_mercado'`

- [ ] **Step 3: Create `ia_pesquisa_mercado.py` with constants + `calcular_referencia()`**

```python
from __future__ import annotations
import statistics
import types
import urllib.error
from ia_utils import extrair_json as _extrair_json, chamar_anthropic as _chamar_anthropic

_MODELO_PADRAO = "claude-haiku-4-5-20251001"

STATUS_ITEM: types.MappingProxyType[str, str] = types.MappingProxyType({
    "VALIDO":       "VALIDO",
    "INSUFICIENTE": "INSUFICIENTE",
    "INEXEQUIVEL":  "INEXEQUIVEL",
})

STATUS_PESQUISA: types.MappingProxyType[str, str] = types.MappingProxyType({
    "VÁLIDA":        "VÁLIDA",
    "COM RESSALVAS": "COM RESSALVAS",
    "INVÁLIDA":      "INVÁLIDA",
})

MIN_COTACOES_VALIDAS: int    = 3
DESVIO_MAX_PERCENTUAL: float = 0.50


def calcular_referencia(cotacoes: list[float]) -> dict:
    if len(cotacoes) < MIN_COTACOES_VALIDAS:
        return {
            "preco_referencia":  None,
            "cotacoes_validas":  list(cotacoes),
            "cotacoes_excluidas": [],
            "status":            "INSUFICIENTE",
        }

    mediana_prov = statistics.median(cotacoes)
    limite = mediana_prov * (1 + DESVIO_MAX_PERCENTUAL)

    validas: list[float]    = []
    excluidas: list[dict]   = []
    for c in cotacoes:
        if c > limite:
            pct = (c - mediana_prov) / mediana_prov * 100
            excluidas.append({
                "preco":  c,
                "motivo": f"R$ {c:.2f} — {pct:.0f}% acima da mediana provisória",
            })
        else:
            validas.append(c)

    if len(validas) < MIN_COTACOES_VALIDAS:
        return {
            "preco_referencia":  None,
            "cotacoes_validas":  validas,
            "cotacoes_excluidas": excluidas,
            "status":            "INSUFICIENTE",
        }

    return {
        "preco_referencia":  statistics.median(validas),
        "cotacoes_validas":  validas,
        "cotacoes_excluidas": excluidas,
        "status":            "VALIDO",
    }
```

- [ ] **Step 4: Run tests — must pass**

```bash
pytest tests/test_ia_pesquisa_mercado.py -v 2>&1 | tail -15
```

Expected: `11 passed`

- [ ] **Step 5: Commit**

```bash
git add ia_pesquisa_mercado.py tests/test_ia_pesquisa_mercado.py
git commit -m "feat(pm): add ia_pesquisa_mercado constants and calcular_referencia"
```

---

## Task 2: `extrair_itens_tr()` + `analisar()`

**Files:**
- Modify: `ia_pesquisa_mercado.py` (append)
- Modify: `tests/test_ia_pesquisa_mercado.py` (append)

---

- [ ] **Step 1: Append new tests to `tests/test_ia_pesquisa_mercado.py`**

Append after the last existing class (after `TestCalcularReferencia`):

```python

def _mock_urlopen(payload: dict):
    data = json.dumps({"content": [{"text": json.dumps(payload)}]}).encode("utf-8")
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=data)))
    cm.__exit__ = MagicMock(return_value=False)
    return cm


class TestExtrairItensTR:
    def test_retorna_lista_com_campos_esperados(self):
        payload = {"itens": [
            {"id": 1, "descricao": "Consultoria TI", "unidade": "hora",
             "quantidade_estimada": 500.0},
            {"id": 2, "descricao": "Licença SW", "unidade": "un",
             "quantidade_estimada": 10.0},
        ]}
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(payload)):
            result = ia_pesquisa_mercado.extrair_itens_tr("texto do TR", "key")
        assert len(result) == 2
        assert result[0]["descricao"] == "Consultoria TI"
        assert result[1]["unidade"] == "un"

    def test_json_malformado_levanta_runtime_error(self):
        data = json.dumps({"content": [{"text": "não é json"}]}).encode("utf-8")
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=data)))
        cm.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=cm):
            with pytest.raises(RuntimeError, match="JSON válido"):
                ia_pesquisa_mercado.extrair_itens_tr("texto", "key")

    def test_http_error_levanta_runtime_error_com_codigo(self):
        err = urllib.error.HTTPError(
            url="https://api.anthropic.com/v1/messages",
            code=401, msg="Unauthorized", hdrs=None,
            fp=MagicMock(read=MagicMock(return_value=b'{"error":"invalid"}')),
        )
        with patch("urllib.request.urlopen", side_effect=err):
            with pytest.raises(RuntimeError, match="HTTP 401"):
                ia_pesquisa_mercado.extrair_itens_tr("texto", "key")


_ITENS_TR = [
    {"id": 1, "descricao": "Consultoria TI", "unidade": "hora",
     "quantidade_estimada": 100.0},
    {"id": 2, "descricao": "Licença SW", "unidade": "un",
     "quantidade_estimada": 5.0},
]

_COTACOES_VALIDAS = {
    "fornecedores": [
        {"nome": "Empresa A", "cnpj": "11.111.111/0001-11"},
        {"nome": "Empresa B", "cnpj": "22.222.222/0001-22"},
        {"nome": "Empresa C", "cnpj": "33.333.333/0001-33"},
    ],
    "itens_cotados": [
        {"item_id": 1, "descricao_no_orcamento": "Consultoria",
         "cotacoes": [
             {"fornecedor": "Empresa A", "preco_unitario": 120.0},
             {"fornecedor": "Empresa B", "preco_unitario": 130.0},
             {"fornecedor": "Empresa C", "preco_unitario": 125.0},
         ]},
        {"item_id": 2, "descricao_no_orcamento": "Licença",
         "cotacoes": [
             {"fornecedor": "Empresa A", "preco_unitario": 500.0},
             {"fornecedor": "Empresa B", "preco_unitario": 480.0},
             {"fornecedor": "Empresa C", "preco_unitario": 490.0},
         ]},
    ],
}

_PARECER = {"parecer_narrativo": "Pesquisa válida. Cotações atendem os critérios."}


class TestAnalisar:
    def test_todos_itens_validos_retorna_pesquisa_valida(self):
        side_effects = [_mock_urlopen(_COTACOES_VALIDAS), _mock_urlopen(_PARECER)]
        with patch("urllib.request.urlopen", side_effect=side_effects):
            r = ia_pesquisa_mercado.analisar(_ITENS_TR, "texto orçamentos", "key")
        assert r["status_geral"] == "VÁLIDA"
        assert len(r["itens_avaliados"]) == 2
        assert r["itens_avaliados"][0]["status"] == "VALIDO"
        assert r["parecer_narrativo"] == "Pesquisa válida. Cotações atendem os critérios."

    def test_item_insuficiente_gera_com_ressalvas(self):
        cotacoes_insuf = {
            **_COTACOES_VALIDAS,
            "itens_cotados": [
                # item 1: só 2 cotações → INSUFICIENTE
                {"item_id": 1, "descricao_no_orcamento": "Consultoria",
                 "cotacoes": [
                     {"fornecedor": "Empresa A", "preco_unitario": 120.0},
                     {"fornecedor": "Empresa B", "preco_unitario": 130.0},
                 ]},
                _COTACOES_VALIDAS["itens_cotados"][1],  # item 2 válido
            ],
        }
        side_effects = [_mock_urlopen(cotacoes_insuf), _mock_urlopen(_PARECER)]
        with patch("urllib.request.urlopen", side_effect=side_effects):
            r = ia_pesquisa_mercado.analisar(_ITENS_TR, "texto", "key")
        assert r["status_geral"] == "COM RESSALVAS"
        assert r["itens_avaliados"][0]["status"] == "INSUFICIENTE"

    def test_maioria_insuficiente_gera_invalida(self):
        cotacoes_insuf = {
            **_COTACOES_VALIDAS,
            "itens_cotados": [
                {"item_id": 1, "descricao_no_orcamento": "Consultoria",
                 "cotacoes": [{"fornecedor": "Empresa A", "preco_unitario": 120.0}]},
                {"item_id": 2, "descricao_no_orcamento": "Licença",
                 "cotacoes": [{"fornecedor": "Empresa B", "preco_unitario": 480.0}]},
            ],
        }
        side_effects = [_mock_urlopen(cotacoes_insuf), _mock_urlopen(_PARECER)]
        with patch("urllib.request.urlopen", side_effect=side_effects):
            r = ia_pesquisa_mercado.analisar(_ITENS_TR, "texto", "key")
        assert r["status_geral"] == "INVÁLIDA"

    def test_json_malformado_levanta_runtime_error(self):
        data = json.dumps({"content": [{"text": "não é json"}]}).encode("utf-8")
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=data)))
        cm.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=cm):
            with pytest.raises(RuntimeError, match="JSON válido"):
                ia_pesquisa_mercado.analisar(_ITENS_TR, "texto", "key")

    def test_url_error_levanta_runtime_error(self):
        err = urllib.error.URLError("Connection refused")
        with patch("urllib.request.urlopen", side_effect=err):
            with pytest.raises(RuntimeError):
                ia_pesquisa_mercado.analisar(_ITENS_TR, "texto", "key")
```

- [ ] **Step 2: Run new tests to verify they fail**

```bash
pytest tests/test_ia_pesquisa_mercado.py -v -k "TestExtrairItensTR or TestAnalisar" 2>&1 | head -20
```

Expected: `AttributeError: module 'ia_pesquisa_mercado' has no attribute 'extrair_itens_tr'`

- [ ] **Step 3: Append `extrair_itens_tr()` and `analisar()` to `ia_pesquisa_mercado.py`**

Append after `calcular_referencia()`:

```python

_SISTEMA_EXTRACAO = (
    "Você é um assistente especialista em licitações públicas brasileiras. "
    "Extraia os itens a serem contratados do Termo de Referência fornecido. "
    "Para cada item identifique: descrição, unidade de medida e quantidade estimada. "
    "Responda SOMENTE com JSON válido no formato especificado. Não inclua texto fora do JSON."
)

_ESTRUTURA_ITENS = """{
  "itens": [
    {
      "id": 1,
      "descricao": "Descrição do item",
      "unidade": "hora|un|m²|kg",
      "quantidade_estimada": 100.0
    }
  ]
}"""


def extrair_itens_tr(
    texto_tr: str,
    api_key: str,
    modelo: str = _MODELO_PADRAO,
) -> list[dict]:
    prompt = (
        f"Extraia os itens a contratar do seguinte Termo de Referência:\n\n"
        f"{texto_tr[:30000]}\n\n"
        f"Retorne no formato JSON:\n{_ESTRUTURA_ITENS}"
    )
    try:
        bruto = _chamar_anthropic(prompt, api_key, modelo, _SISTEMA_EXTRACAO)
    except urllib.error.HTTPError as exc:
        _body = ""
        try:
            _body = exc.read().decode("utf-8", errors="replace")
        except (OSError, IOError):
            pass
        raise RuntimeError(
            f"Falha na API Anthropic: HTTP {exc.code} {exc.reason} — {_body}"
        ) from exc
    except (urllib.error.URLError, OSError) as exc:
        raise RuntimeError(f"Falha na API Anthropic: {exc}") from exc

    try:
        resultado = _extrair_json(bruto)
    except ValueError as exc:
        raise RuntimeError(f"Resposta da API não contém JSON válido: {exc}") from exc

    if not isinstance(resultado, dict):
        raise RuntimeError(
            f"Resposta inesperada da API: objeto JSON esperado, "
            f"recebeu {type(resultado).__name__}"
        )

    itens = resultado.get("itens") or []
    for i, item in enumerate(itens, start=1):
        if "id" not in item:
            item["id"] = i
    return itens


_SISTEMA_COTACOES = (
    "Você é um especialista em pesquisa de preços para licitações públicas brasileiras. "
    "Analise os orçamentos fornecidos e identifique os preços unitários ofertados por cada "
    "fornecedor para cada item da lista. Use correspondência semântica para relacionar "
    "os itens dos orçamentos com os itens da lista de referência. "
    "Responda SOMENTE com JSON válido no formato especificado. Não inclua texto fora do JSON."
)

_ESTRUTURA_COTACOES = """{
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
}"""

_SISTEMA_PARECER = (
    "Você é um especialista em pesquisa de preços para licitações públicas brasileiras. "
    "Com base nos resultados da análise, elabore um parecer técnico fundamentado no "
    "Art. 23 da Lei 14.133/2021 e IN SEGES/MGI 65/2021, justificando as exclusões de "
    "cotações e o status de cada item. "
    "Responda SOMENTE com JSON válido no formato especificado. Não inclua texto fora do JSON."
)

_ESTRUTURA_PARECER = '{"parecer_narrativo": "Texto do parecer técnico."}'


def _chamar_api(prompt: str, api_key: str, modelo: str, sistema: str) -> dict:
    try:
        bruto = _chamar_anthropic(prompt, api_key, modelo, sistema)
    except urllib.error.HTTPError as exc:
        _body = ""
        try:
            _body = exc.read().decode("utf-8", errors="replace")
        except (OSError, IOError):
            pass
        raise RuntimeError(
            f"Falha na API Anthropic: HTTP {exc.code} {exc.reason} — {_body}"
        ) from exc
    except (urllib.error.URLError, OSError) as exc:
        raise RuntimeError(f"Falha na API Anthropic: {exc}") from exc

    try:
        resultado = _extrair_json(bruto)
    except ValueError as exc:
        raise RuntimeError(f"Resposta da API não contém JSON válido: {exc}") from exc

    if not isinstance(resultado, dict):
        raise RuntimeError(
            f"Resposta inesperada da API: objeto JSON esperado, "
            f"recebeu {type(resultado).__name__}"
        )
    return resultado


def analisar(
    itens_tr: list[dict],
    texto_orcamentos: str,
    api_key: str,
    modelo: str = _MODELO_PADRAO,
) -> dict:
    _itens_texto = "\n".join(
        f"{i['id']}. {i['descricao']} ({i.get('unidade', 'un')}) "
        f"— qtd: {i.get('quantidade_estimada', 'não informada')}"
        for i in itens_tr
    )
    prompt_cotacoes = (
        f"Lista de itens da pesquisa:\n{_itens_texto}\n\n"
        f"Orçamentos recebidos:\n{texto_orcamentos[:30000]}\n\n"
        f"Retorne no formato JSON:\n{_ESTRUTURA_COTACOES}"
    )
    dados_cotacoes = _chamar_api(prompt_cotacoes, api_key, modelo, _SISTEMA_COTACOES)

    fornecedores = dados_cotacoes.get("fornecedores") or []
    itens_cotados = {
        item["item_id"]: item
        for item in (dados_cotacoes.get("itens_cotados") or [])
    }

    itens_avaliados: list[dict] = []
    for item_tr in itens_tr:
        item_id = item_tr["id"]
        item_cotado = itens_cotados.get(item_id, {})
        cotacoes_raw = [
            c["preco_unitario"]
            for c in (item_cotado.get("cotacoes") or [])
            if c.get("preco_unitario") is not None
        ]
        ref = calcular_referencia(cotacoes_raw)
        qtd = item_tr.get("quantidade_estimada")
        subtotal = (
            ref["preco_referencia"] * qtd
            if ref["preco_referencia"] is not None and qtd
            else None
        )
        itens_avaliados.append({
            "item_id":            item_id,
            "descricao":          item_tr["descricao"],
            "unidade":            item_tr.get("unidade", "un"),
            "quantidade_estimada": qtd,
            "cotacoes_detalhadas": item_cotado.get("cotacoes") or [],
            "preco_referencia":   ref["preco_referencia"],
            "cotacoes_validas":   ref["cotacoes_validas"],
            "cotacoes_excluidas": ref["cotacoes_excluidas"],
            "status":             ref["status"],
            "subtotal_estimado":  subtotal,
        })

    n_total = len(itens_avaliados)
    n_insuf = sum(1 for i in itens_avaliados if i["status"] == "INSUFICIENTE")
    if n_insuf == 0:
        status_geral = "VÁLIDA"
    elif n_insuf > n_total / 2:
        status_geral = "INVÁLIDA"
    else:
        status_geral = "COM RESSALVAS"

    subtotals = [i["subtotal_estimado"] for i in itens_avaliados if i["subtotal_estimado"]]
    valor_total = sum(subtotals) if subtotals else None

    resumo_parts = []
    for i in itens_avaliados:
        if i["preco_referencia"] is not None:
            resumo_parts.append(
                f"Item {i['item_id']} ({i['descricao']}): {i['status']}, "
                f"ref R$ {i['preco_referencia']:.2f}/{i['unidade']}"
            )
        else:
            resumo_parts.append(
                f"Item {i['item_id']} ({i['descricao']}): INSUFICIENTE"
            )

    excluidas_parts = [
        f"  Item {i['item_id']}: {e['motivo']}"
        for i in itens_avaliados
        for e in i["cotacoes_excluidas"]
    ]

    prompt_parecer = (
        f"Status da pesquisa: {status_geral}\n"
        f"Resultados por item:\n" + "\n".join(resumo_parts) + "\n"
        f"Cotações excluídas:\n" + ("\n".join(excluidas_parts) or "Nenhuma") + "\n\n"
        f"Retorne no formato JSON:\n{_ESTRUTURA_PARECER}"
    )
    dados_parecer = _chamar_api(prompt_parecer, api_key, modelo, _SISTEMA_PARECER)

    return {
        "status_geral":          status_geral,
        "itens_avaliados":       itens_avaliados,
        "fornecedores":          fornecedores,
        "valor_total_estimado":  valor_total,
        "parecer_narrativo":     dados_parecer.get("parecer_narrativo") or "",
        "base_legal": [
            "Art. 23, Lei 14.133/2021",
            "IN SEGES/MGI 65/2021",
        ],
    }
```

- [ ] **Step 4: Run all tests — must pass**

```bash
pytest tests/test_ia_pesquisa_mercado.py -v 2>&1 | tail -25
```

Expected: `19 passed`

- [ ] **Step 5: Commit**

```bash
git add ia_pesquisa_mercado.py tests/test_ia_pesquisa_mercado.py
git commit -m "feat(pm): add extrair_itens_tr and analisar to ia_pesquisa_mercado"
```

---

## Task 3: `relatorio_pesquisa_mercado.py` (PDF generators)

**Files:**
- Create: `relatorio_pesquisa_mercado.py`
- Create: `tests/test_relatorio_pesquisa_mercado.py`

---

- [ ] **Step 1: Write the failing tests**

Create `tests/test_relatorio_pesquisa_mercado.py`:

```python
from __future__ import annotations
import io
import pdfplumber
import relatorio_pesquisa_mercado

_OBJETO = "Contratação de consultoria em TI"

_ITENS = [
    {
        "item_id":             1,
        "descricao":           "Consultoria TI",
        "unidade":             "hora",
        "quantidade_estimada": 100.0,
        "cotacoes_detalhadas": [
            {"fornecedor": "Empresa A", "preco_unitario": 120.0},
            {"fornecedor": "Empresa B", "preco_unitario": 125.0},
            {"fornecedor": "Empresa C", "preco_unitario": 130.0},
        ],
        "preco_referencia":   125.0,
        "cotacoes_validas":   [120.0, 125.0, 130.0],
        "cotacoes_excluidas": [],
        "status":             "VALIDO",
        "subtotal_estimado":  12500.0,
    },
    {
        "item_id":             2,
        "descricao":           "Licença SW",
        "unidade":             "un",
        "quantidade_estimada": 5.0,
        "cotacoes_detalhadas": [
            {"fornecedor": "Empresa A", "preco_unitario": 500.0},
        ],
        "preco_referencia":   None,
        "cotacoes_validas":   [500.0],
        "cotacoes_excluidas": [],
        "status":             "INSUFICIENTE",
        "subtotal_estimado":  None,
    },
]

_FORNECEDORES = [
    {"nome": "Empresa A", "cnpj": "11.111.111/0001-11"},
    {"nome": "Empresa B", "cnpj": "22.222.222/0001-22"},
    {"nome": "Empresa C", "cnpj": "33.333.333/0001-33"},
]


class TestGerarMapaPrecos:
    def test_retorna_bytes_pdf(self):
        pdf = relatorio_pesquisa_mercado.gerar_mapa_precos(
            _OBJETO, _ITENS, _FORNECEDORES, 12500.0
        )
        assert isinstance(pdf, bytes)
        assert pdf[:4] == b"%PDF"

    def test_inclui_nome_do_fornecedor(self):
        pdf = relatorio_pesquisa_mercado.gerar_mapa_precos(
            _OBJETO, _ITENS, _FORNECEDORES, 12500.0
        )
        with pdfplumber.open(io.BytesIO(pdf)) as doc:
            texto = "\n".join(pg.extract_text() or "" for pg in doc.pages)
        assert "Empresa A" in texto

    def test_item_insuficiente_aparece_como_insuf(self):
        pdf = relatorio_pesquisa_mercado.gerar_mapa_precos(
            _OBJETO, _ITENS, _FORNECEDORES, 12500.0
        )
        with pdfplumber.open(io.BytesIO(pdf)) as doc:
            texto = "\n".join(pg.extract_text() or "" for pg in doc.pages)
        assert "INSUF" in texto

    def test_caracteres_especiais_nao_quebram_pdf(self):
        itens_xss = [{**_ITENS[0], "descricao": "Item <Teste> & \"Especial\""}]
        pdf = relatorio_pesquisa_mercado.gerar_mapa_precos(
            "Objeto <com> &amp; especiais", itens_xss, _FORNECEDORES, 1000.0
        )
        assert isinstance(pdf, bytes)
        assert pdf[:4] == b"%PDF"


class TestGerarRelatorioPesquisa:
    def test_retorna_bytes_pdf(self):
        pdf = relatorio_pesquisa_mercado.gerar_relatorio_pesquisa(
            _OBJETO, _ITENS, _FORNECEDORES, "Parecer aprovado.", "VÁLIDA", 12500.0
        )
        assert isinstance(pdf, bytes)
        assert pdf[:4] == b"%PDF"

    def test_status_valida_aparece_no_relatorio(self):
        pdf = relatorio_pesquisa_mercado.gerar_relatorio_pesquisa(
            _OBJETO, _ITENS, _FORNECEDORES, "Parecer aprovado.", "VÁLIDA", 12500.0
        )
        with pdfplumber.open(io.BytesIO(pdf)) as doc:
            texto = "\n".join(pg.extract_text() or "" for pg in doc.pages)
        assert "VÁLIDA" in texto
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_relatorio_pesquisa_mercado.py -v 2>&1 | head -15
```

Expected: `ModuleNotFoundError: No module named 'relatorio_pesquisa_mercado'`

- [ ] **Step 3: Create `relatorio_pesquisa_mercado.py`**

```python
from __future__ import annotations
import html
import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)
from ia_utils import COR_STATUS_HEX as _COR_STATUS

_COR_PESQUISA = {
    "VÁLIDA":        colors.HexColor(_COR_STATUS["ok"]),
    "COM RESSALVAS": colors.HexColor(_COR_STATUS["alerta"]),
    "INVÁLIDA":      colors.HexColor(_COR_STATUS["critico"]),
}

_estilos = getSampleStyleSheet()
_TITULO  = ParagraphStyle("pm_titulo", parent=_estilos["Title"],   fontSize=16, spaceAfter=4)
_H1      = ParagraphStyle("pm_h1",     parent=_estilos["Heading1"])
_H2      = ParagraphStyle("pm_h2",     parent=_estilos["Heading2"], fontSize=12, spaceAfter=3)
_CORPO   = ParagraphStyle("pm_corpo",  parent=_estilos["Normal"],   fontSize=10, spaceAfter=3)
_PEQUENO = ParagraphStyle("pm_peq",    parent=_estilos["Normal"],   fontSize=8,  textColor=colors.grey)
_BADGE   = ParagraphStyle("pm_badge",  parent=_estilos["Normal"],   fontSize=14, textColor=colors.white, alignment=1)


def _fmt_brl(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def gerar_mapa_precos(
    objeto: str,
    itens_avaliados: list[dict],
    fornecedores: list[dict],
    valor_total_estimado: float | None,
) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm, topMargin=2*cm, bottomMargin=2*cm,
    )
    story: list = []

    story.append(Paragraph("IA-Licita — RM Vértice Digital", _TITULO))
    story.append(Paragraph("Mapa de Preços", _H1))
    story.append(Paragraph(html.escape(objeto), _H2))
    story.append(Paragraph(
        f"Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}", _PEQUENO
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.grey, spaceAfter=8))

    nomes_forn = [
        html.escape(f.get("nome") or f"Fornecedor {i + 1}")
        for i, f in enumerate(fornecedores)
    ]
    header = ["#", "Descrição", "Un", "Qtd"] + nomes_forn + ["Ref (mediana)", "Subtotal"]
    linhas: list[list] = [header]
    notas: list[str] = []
    nota_num = 1

    for item in itens_avaliados:
        cots_dict: dict = {
            c.get("fornecedor"): c.get("preco_unitario")
            for c in (item.get("cotacoes_detalhadas") or [])
        }
        excluidas_precos: set = {
            e["preco"] for e in (item.get("cotacoes_excluidas") or [])
        }
        excluidas_motivos: dict = {
            e["preco"]: e.get("motivo", "excluída")
            for e in (item.get("cotacoes_excluidas") or [])
        }

        celulas_forn: list[str] = []
        for forn in fornecedores:
            nome = forn.get("nome") or ""
            preco = cots_dict.get(nome)
            if preco is None:
                celulas_forn.append("—")
            elif preco in excluidas_precos:
                tag = f"[{nota_num}]"
                notas.append(
                    f"[{nota_num}] {html.escape(excluidas_motivos.get(preco, 'excluída'))}"
                )
                nota_num += 1
                celulas_forn.append(f"EXC.{tag}")
            else:
                celulas_forn.append(_fmt_brl(preco))

        ref_str = _fmt_brl(item["preco_referencia"]) if item.get("preco_referencia") is not None else "INSUF."
        sub_str = _fmt_brl(item["subtotal_estimado"]) if item.get("subtotal_estimado") is not None else "—"
        qtd_str = str(item.get("quantidade_estimada") or "—")

        linhas.append([
            str(item["item_id"]),
            html.escape(str(item.get("descricao") or "")),
            html.escape(str(item.get("unidade") or "un")),
            qtd_str,
        ] + celulas_forn + [ref_str, sub_str])

    total_str = _fmt_brl(valor_total_estimado) if valor_total_estimado is not None else "—"
    linhas.append(
        ["", "VALOR TOTAL ESTIMADO", "", ""] + [""] * len(fornecedores) + ["", total_str]
    )

    col_w = [0.7*cm, 4.5*cm, 1*cm, 1.2*cm]
    col_w += [2.5*cm] * len(fornecedores)
    col_w += [3*cm, 2.5*cm]

    t = Table(linhas, colWidths=col_w)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTSIZE",   (0, 0), (-1, -1), 8),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.grey),
        ("PADDING",    (0, 0), (-1, -1), 3),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F2F2F2")),
        ("FONTNAME",   (0, -1), (-1, -1), "Helvetica-Bold"),
    ]))
    story.append(t)

    if notas:
        story.append(Spacer(1, 0.4*cm))
        story.append(Paragraph("Notas (cotações excluídas):", _H2))
        for nota in notas:
            story.append(Paragraph(nota, _PEQUENO))

    story.append(Spacer(1, 0.5*cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Paragraph(
        "Sujeito a verificação humana. Não substitui aprovação do ordenador.", _PEQUENO
    ))

    doc.build(story)
    return buf.getvalue()


def gerar_relatorio_pesquisa(
    objeto: str,
    itens_avaliados: list[dict],
    fornecedores: list[dict],
    parecer_narrativo: str,
    status_geral: str,
    valor_total_estimado: float | None,
) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm,
    )
    story: list = []

    story.append(Paragraph("IA-Licita — RM Vértice Digital", _TITULO))
    story.append(Paragraph("Relatório de Pesquisa de Preços de Mercado", _H1))
    story.append(Paragraph("Art. 23, Lei 14.133/2021 + IN SEGES/MGI 65/2021", _PEQUENO))
    story.append(Paragraph(
        f"Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}", _PEQUENO
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.grey, spaceAfter=8))

    story.append(Paragraph("1. Identificação do Objeto", _H2))
    story.append(Paragraph(html.escape(objeto), _CORPO))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("2. Metodologia", _H2))
    story.append(Paragraph(
        "A pesquisa de preços foi realizada em conformidade com o Art. 23 da Lei n.º 14.133/2021 "
        "e a IN SEGES/MGI 65/2021. O preço de referência por item foi calculado como a mediana "
        "das cotações válidas. Cotações com valor superior a 50% acima da mediana provisória "
        "foram excluídas por configurarem preço inexequível ou especulativo.",
        _CORPO,
    ))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("3. Fornecedores Consultados", _H2))
    for forn in fornecedores:
        nome = html.escape(str(forn.get("nome") or "não identificado"))
        cnpj = html.escape(str(forn.get("cnpj") or "não informado"))
        story.append(Paragraph(f"- {nome} — CNPJ: {cnpj}", _CORPO))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("4. Análise por Item", _H2))
    for item in itens_avaliados:
        desc = html.escape(str(item.get("descricao") or ""))
        un   = html.escape(str(item.get("unidade") or "un"))
        story.append(Paragraph(f"<b>Item {item['item_id']}: {desc}</b> ({un})", _CORPO))
        if item.get("preco_referencia") is not None:
            story.append(Paragraph(
                f"Preço de referência: {_fmt_brl(item['preco_referencia'])}/{un} — "
                f"{len(item.get('cotacoes_validas', []))} cotação(ões) válida(s)",
                _CORPO,
            ))
        else:
            story.append(Paragraph(
                f"Status: INSUFICIENTE — apenas {len(item.get('cotacoes_validas', []))} "
                f"cotação(ões) válida(s) (mínimo: 3)",
                _CORPO,
            ))
        for exc in (item.get("cotacoes_excluidas") or []):
            story.append(Paragraph(
                f"  Excluída: {html.escape(str(exc.get('motivo', '')))}",
                _PEQUENO,
            ))
    story.append(Spacer(1, 0.3*cm))

    _cor_badge = _COR_PESQUISA.get(status_geral, colors.grey)
    t_badge = Table(
        [[Paragraph(f"<b>{html.escape(status_geral)}</b>", _BADGE)]],
        colWidths=[17*cm],
    )
    t_badge.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _cor_badge),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("PADDING",    (0, 0), (-1, -1), 8),
    ]))
    story.append(t_badge)
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("5. Parecer", _H2))
    story.append(Paragraph(html.escape(parecer_narrativo or "-"), _CORPO))
    story.append(Spacer(1, 0.3*cm))

    if valor_total_estimado is not None:
        story.append(Paragraph("6. Valor Total Estimado", _H2))
        story.append(Paragraph(f"<b>{_fmt_brl(valor_total_estimado)}</b>", _CORPO))
        story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph(
        "Base Legal: Art. 23, Lei n.º 14.133/2021 — IN SEGES/MGI 65/2021", _PEQUENO
    ))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Paragraph(
        "Gerado por IA-Licita - RM Vertice Digital. Revisar antes de anexar ao processo.",
        _PEQUENO,
    ))

    doc.build(story)
    return buf.getvalue()
```

- [ ] **Step 4: Run all tests — must pass**

```bash
pytest tests/test_relatorio_pesquisa_mercado.py tests/test_ia_pesquisa_mercado.py -v 2>&1 | tail -20
```

Expected: `25 passed` (19 + 6 new)

- [ ] **Step 5: Commit**

```bash
git add relatorio_pesquisa_mercado.py tests/test_relatorio_pesquisa_mercado.py
git commit -m "feat(pm): add relatorio_pesquisa_mercado with gerar_mapa_precos and gerar_relatorio_pesquisa"
```

---

## Task 4: `app.py` aba10 integration

**Files:**
- Modify: `app.py` (3 locations: imports at line 35, st.tabs at lines 101–111, append after line 1818)

---

- [ ] **Step 1: Add imports after line 35**

In `app.py`, after `import relatorio_reabilitacao`, add:

```python
import ia_pesquisa_mercado
import relatorio_pesquisa_mercado
```

Result at lines 34–37:

```python
import ia_reabilitacao
import relatorio_reabilitacao
import ia_pesquisa_mercado
import relatorio_pesquisa_mercado
```

- [ ] **Step 2: Expand `st.tabs()` to 10 tabs**

Replace lines 101–111 with:

```python
aba1, aba2, aba3, aba4, aba5, aba6, aba7, aba8, aba9, aba10 = st.tabs([
    "📄 Auditoria de Edital",
    "🔍 Due Diligence de Integridade",
    "📋 Auditoria de ETP",
    "🏛️ Diagnóstico de Integridade",
    "🏢 Avaliação de PI",
    "⚖️ Alterações Contratuais",
    "📝 Auditoria de TR",
    "⚖️ Dosimetria de Sanções",
    "🔄 Reabilitação de Fornecedor",
    "💰 Pesquisa de Mercado",
])
```

- [ ] **Step 3: Append the aba10 block at the end of `app.py`**

After the closing line of the aba9 block (current end of file), append:

```python

with aba10:
    st.subheader("Pesquisa de Preços de Mercado")
    st.caption("Art. 23, Lei 14.133/2021 + IN SEGES/MGI 65/2021")

    _api_key_pm = _get_api_key()

    _objeto_pm = st.text_input(
        "Objeto da pesquisa (descrição curta)",
        placeholder="ex.: Contratação de serviços de consultoria em tecnologia da informação",
        key="pm_objeto_input",
    )
    _tr_pm = st.file_uploader(
        "Termo de Referência (PDF ou DOCX)",
        type=["pdf", "docx"],
        key="pm_tr_arquivo",
    )

    if st.button(
        "Extrair Itens →",
        type="primary",
        key="btn_pm_extrair",
        disabled=not (_objeto_pm and _tr_pm),
    ):
        for _k in ("pm_etapa", "pm_objeto", "pm_itens_tr",
                   "pm_resultado", "pm_pdf_mapa", "pm_pdf_relatorio"):
            st.session_state.pop(_k, None)
        if not _api_key_pm:
            st.error("ANTHROPIC_API_KEY não configurada. Configure a variável de ambiente.")
        else:
            try:
                with st.spinner("Extraindo texto do TR..."):
                    _texto_tr_pm, _avisos_tr_pm = etp_extrator.extrair_texto([_tr_pm])
                for _av in _avisos_tr_pm:
                    st.warning(_safe_md(_av))
                with st.spinner("Identificando itens com IA..."):
                    _itens_pm = ia_pesquisa_mercado.extrair_itens_tr(
                        _texto_tr_pm, _api_key_pm
                    )
                st.session_state["pm_objeto"]   = _objeto_pm
                st.session_state["pm_itens_tr"] = _itens_pm
                st.session_state["pm_etapa"]    = 1
            except Exception as _e_pm:
                _msg_pm = str(_e_pm)
                if isinstance(_e_pm, ValueError):
                    _msg_pm += " Verifique se o arquivo não é uma imagem sem OCR."
                st.error(_msg_pm)

    if st.session_state.get("pm_etapa", 0) >= 1:
        st.divider()
        st.markdown("#### Itens identificados no TR")
        _itens_extr = st.session_state.get("pm_itens_tr") or []
        if _itens_extr:
            _tbl_header = "| # | Descrição | Unidade | Qtd estimada |\n|---|-----------|---------|-------------|\n"
            _tbl_rows   = "\n".join(
                f"| {i.get('id', idx + 1)} | {_safe_md(i.get('descricao', ''))} "
                f"| {_safe_md(i.get('unidade', 'un'))} "
                f"| {i.get('quantidade_estimada', '—')} |"
                for idx, i in enumerate(_itens_extr)
            )
            st.markdown(_tbl_header + _tbl_rows)
        else:
            st.warning("Nenhum item identificado. Verifique se o TR contém lista de itens.")

        _orcamentos_pm = st.file_uploader(
            "Orçamentos dos fornecedores (PDF ou DOCX, múltiplos arquivos)",
            type=["pdf", "docx"],
            accept_multiple_files=True,
            key="pm_orcamentos",
        )

        if st.button(
            "Analisar Pesquisa de Mercado →",
            type="primary",
            key="btn_pm_analisar",
            disabled=not _orcamentos_pm,
        ):
            if not _api_key_pm:
                st.error("ANTHROPIC_API_KEY não configurada. Configure a variável de ambiente.")
            else:
                try:
                    with st.spinner("Extraindo texto dos orçamentos..."):
                        _texto_orc_pm, _avisos_orc_pm = etp_extrator.extrair_texto(
                            _orcamentos_pm
                        )
                    for _av in _avisos_orc_pm:
                        st.warning(_safe_md(_av))
                    with st.spinner("Analisando pesquisa de mercado com IA..."):
                        _resultado_pm = ia_pesquisa_mercado.analisar(
                            st.session_state["pm_itens_tr"],
                            _texto_orc_pm,
                            _api_key_pm,
                        )
                    st.session_state["pm_resultado"] = _resultado_pm
                    st.session_state["pm_etapa"]     = 3
                    try:
                        st.session_state["pm_pdf_mapa"] = (
                            relatorio_pesquisa_mercado.gerar_mapa_precos(
                                st.session_state["pm_objeto"],
                                _resultado_pm["itens_avaliados"],
                                _resultado_pm["fornecedores"],
                                _resultado_pm["valor_total_estimado"],
                            )
                        )
                    except Exception as _e_mapa:
                        st.session_state.pop("pm_pdf_mapa", None)
                        st.warning(f"Mapa de Preços indisponível: {_e_mapa}")
                    try:
                        st.session_state["pm_pdf_relatorio"] = (
                            relatorio_pesquisa_mercado.gerar_relatorio_pesquisa(
                                st.session_state["pm_objeto"],
                                _resultado_pm["itens_avaliados"],
                                _resultado_pm["fornecedores"],
                                _resultado_pm["parecer_narrativo"],
                                _resultado_pm["status_geral"],
                                _resultado_pm["valor_total_estimado"],
                            )
                        )
                    except Exception as _e_rel:
                        st.session_state.pop("pm_pdf_relatorio", None)
                        st.warning(f"Relatório de Pesquisa indisponível: {_e_rel}")
                except Exception as _e_pm2:
                    _msg_pm2 = str(_e_pm2)
                    if isinstance(_e_pm2, ValueError):
                        _msg_pm2 += " Verifique se o arquivo não é uma imagem sem OCR."
                    st.error(_msg_pm2)

    if st.session_state.get("pm_etapa", 0) >= 3:
        _res_pm = st.session_state.get("pm_resultado") or {}
        if _res_pm:
            st.divider()
            st.markdown("### Resultado da Pesquisa de Mercado")

            _status_pm = str(_res_pm.get("status_geral") or "").strip().upper()
            _icone_pm = {
                "VÁLIDA":        "🟢",
                "COM RESSALVAS": "🟡",
                "INVÁLIDA":      "🔴",
            }
            st.subheader(
                f"{_icone_pm.get(_status_pm, '⚪')} {_safe_md(_status_pm)}"
            )

            for _item_pm in (_res_pm.get("itens_avaliados") or []):
                _desc_i = _safe_md(_item_pm.get("descricao") or "")
                _un_i   = _safe_md(_item_pm.get("unidade") or "un")
                _qtd_i  = _item_pm.get("quantidade_estimada")
                _qtd_str = f" — Qtd: {_qtd_i}" if _qtd_i else ""
                st.markdown(f"**Item {_item_pm['item_id']} — {_desc_i}** ({_un_i}){_qtd_str}")

                if _item_pm.get("preco_referencia") is not None:
                    st.markdown(
                        f"Preço de referência: **{_fmt_brl(_item_pm['preco_referencia'])}/{_un_i}**"
                    )
                    if _item_pm.get("subtotal_estimado"):
                        st.caption(
                            f"Subtotal estimado: {_fmt_brl(_item_pm['subtotal_estimado'])}"
                        )
                else:
                    st.warning(
                        f"⚠ Apenas {len(_item_pm.get('cotacoes_validas', []))} cotação(ões) "
                        "válida(s) — insuficiente (mínimo: 3)"
                    )

                for _exc_pm in (_item_pm.get("cotacoes_excluidas") or []):
                    st.caption(f"❌ Excluída: {_safe_md(_exc_pm.get('motivo', ''))}")

            if _res_pm.get("valor_total_estimado") is not None:
                st.metric(
                    "Valor Total Estimado",
                    _fmt_brl(_res_pm["valor_total_estimado"]),
                )

            if _res_pm.get("parecer_narrativo"):
                st.info(_safe_md(_res_pm["parecer_narrativo"]))

            _col_pm1, _col_pm2 = st.columns(2)
            with _col_pm1:
                if "pm_pdf_mapa" in st.session_state:
                    st.download_button(
                        label="⬇ Mapa de Preços (PDF)",
                        data=st.session_state["pm_pdf_mapa"],
                        file_name="pesquisa_mercado_mapa_precos.pdf",
                        mime="application/pdf",
                        key="pm_dl_mapa",
                    )
            with _col_pm2:
                if "pm_pdf_relatorio" in st.session_state:
                    st.download_button(
                        label="⬇ Relatório de Pesquisa (PDF)",
                        data=st.session_state["pm_pdf_relatorio"],
                        file_name="pesquisa_mercado_relatorio.pdf",
                        mime="application/pdf",
                        key="pm_dl_relatorio",
                    )
```

Note: `_fmt_brl` used in the aba10 block is a module-level helper. Add it after the `_safe_md` function definition at line 47 in `app.py`:

```python
def _fmt_brl(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
```

- [ ] **Step 4: Verify syntax**

```bash
cd /Users/robertomauricioferreiraribeiro/Documents/Daysival
python -c "import app" 2>&1
```

Expected: no output (clean import)

- [ ] **Step 5: Run full test suite**

```bash
pytest tests/ -v 2>&1 | tail -30
```

Expected: all tests pass (no regression from app.py edits — app.py has no unit tests but the import check above verifies wiring).

- [ ] **Step 6: Commit**

```bash
git add app.py
git commit -m "feat(pm): add aba10 Pesquisa de Mercado to app.py"
```

---

## Self-Review Against Spec

**Spec coverage checklist:**

| Spec requirement | Covered by |
|-----------------|-----------|
| `STATUS_ITEM`, `STATUS_PESQUISA`, `MIN_COTACOES_VALIDAS`, `DESVIO_MAX_PERCENTUAL` as MappingProxyType | Task 1 |
| `calcular_referencia()` — mediana provisória, exclusão >50%, mediana final, VALIDO/INSUFICIENTE | Task 1 |
| `extrair_itens_tr()` — IA, returns `[{id, descricao, unidade, quantidade_estimada}]` | Task 2 |
| `analisar()` — IA cotações + pure Python ref + IA parecer, returns `{status_geral, itens_avaliados, fornecedores, valor_total_estimado, parecer_narrativo, base_legal}` | Task 2 |
| `gerar_mapa_precos()` — tabular PDF, EXC. mark, notes, total | Task 3 |
| `gerar_relatorio_pesquisa()` — narrative PDF, badge, sections 1–6 | Task 3 |
| Etapa 1: objeto input + TR upload + "Extrair Itens" + items display | Task 4 |
| Etapa 2: orçamentos upload + "Analisar" button | Task 4 |
| Etapa 3: status badge, per-item results, total, parecer, download buttons | Task 4 |
| `html.escape()` on all dynamic PDF strings | Task 3 |
| RuntimeError on JSON invalid / HTTPError / URLError | Tasks 2 & 3 |
| base_legal: `["Art. 23, Lei 14.133/2021", "IN SEGES/MGI 65/2021"]` | Task 2 |

**No placeholders found.**

**Type consistency confirmed:** `calcular_referencia()` returns `dict` with keys `preco_referencia`, `cotacoes_validas`, `cotacoes_excluidas`, `status` — all consumed correctly in `analisar()`.
