from __future__ import annotations
import statistics
import types
from ia_utils import chamar_api as _chamar_api, fmt_brl as _fmt_brl

_MODELO_PADRAO = "claude-haiku-4-5-20251001"

STATUS_ITEM: types.MappingProxyType[str, str] = types.MappingProxyType({
    "VALIDO":       "VALIDO",
    "INSUFICIENTE": "INSUFICIENTE",
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
            "status":            STATUS_ITEM["INSUFICIENTE"],
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
                "motivo": f"{_fmt_brl(c)} — {pct:.0f}% acima da mediana provisória",
            })
        else:
            validas.append(c)

    if len(validas) < MIN_COTACOES_VALIDAS:
        return {
            "preco_referencia":  None,
            "cotacoes_validas":  validas,
            "cotacoes_excluidas": excluidas,
            "status":            STATUS_ITEM["INSUFICIENTE"],
        }

    return {
        "preco_referencia":  statistics.median(validas),
        "cotacoes_validas":  validas,
        "cotacoes_excluidas": excluidas,
        "status":            STATUS_ITEM["VALIDO"],
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
    resultado = _chamar_api(prompt, api_key, modelo, _SISTEMA_EXTRACAO)
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


def analisar(
    itens_tr: list[dict],
    texto_orcamentos: str,
    api_key: str,
    modelo: str = _MODELO_PADRAO,
) -> dict:
    if not itens_tr:
        return {
            "status_geral":         STATUS_PESQUISA["INVÁLIDA"],
            "itens_avaliados":      [],
            "fornecedores":         [],
            "valor_total_estimado": None,
            "parecer_narrativo":    "Nenhum item identificado no Termo de Referência.",
            "base_legal": [
                "Art. 23, Lei 14.133/2021",
                "IN SEGES/MGI 65/2021",
            ],
        }

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
    itens_cotados: dict = {}
    for _ic in (dados_cotacoes.get("itens_cotados") or []):
        if _ic.get("item_id") is None:
            continue
        try:
            itens_cotados[int(float(_ic["item_id"]))] = _ic
        except (ValueError, TypeError):
            pass

    itens_avaliados: list[dict] = []
    for item_tr in itens_tr:
        item_id = item_tr["id"]
        item_cotado = itens_cotados.get(item_id, {})
        cotacoes_raw: list[float] = []
        for _c in (item_cotado.get("cotacoes") or []):
            _p = _c.get("preco_unitario")
            if _p is not None:
                try:
                    cotacoes_raw.append(float(_p))
                except (ValueError, TypeError):
                    pass
        ref = calcular_referencia(cotacoes_raw)
        _qtd_raw = item_tr.get("quantidade_estimada")
        try:
            qtd = float(_qtd_raw) if _qtd_raw is not None else None
        except (ValueError, TypeError):
            qtd = None
        subtotal = (
            ref["preco_referencia"] * qtd
            if ref["preco_referencia"] is not None and qtd is not None
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
    n_insuf = sum(1 for i in itens_avaliados if i["status"] == STATUS_ITEM["INSUFICIENTE"])
    if n_insuf == 0:
        status_geral = STATUS_PESQUISA["VÁLIDA"]
    elif n_insuf > n_total / 2:
        status_geral = STATUS_PESQUISA["INVÁLIDA"]
    else:
        status_geral = STATUS_PESQUISA["COM RESSALVAS"]

    subtotals = [i["subtotal_estimado"] for i in itens_avaliados if i["subtotal_estimado"] is not None]
    valor_total = sum(subtotals) if subtotals else None

    resumo_parts = []
    for i in itens_avaliados:
        if i["preco_referencia"] is not None:
            resumo_parts.append(
                f"Item {i['item_id']} ({i['descricao']}): {i['status']}, "
                f"ref {_fmt_brl(i['preco_referencia'])}/{i['unidade']}"
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
