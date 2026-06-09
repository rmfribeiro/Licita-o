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
