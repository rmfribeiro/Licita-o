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
