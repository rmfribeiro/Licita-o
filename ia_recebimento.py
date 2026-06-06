from __future__ import annotations
import json
import types
import urllib.error
import urllib.request

from ia_utils import extrair_json as _extrair_json

_MODELO_PADRAO = "claude-haiku-4-5-20251001"

TIPOS_OBJETO: types.MappingProxyType[str, str] = types.MappingProxyType({
    "servico": "Serviço",
    "bem":     "Fornecimento de Bem",
    "obra":    "Obra",
})

PARECER_OPTIONS: types.MappingProxyType[str, str] = types.MappingProxyType({
    "APTO":               "APTO",
    "APTO COM RESSALVAS": "APTO COM RESSALVAS",
    "INAPTO":             "INAPTO",
})

STATUS_CONDICAO: types.MappingProxyType[str, str] = types.MappingProxyType({
    "ATENDIDA": "ATENDIDA",
    "PARCIAL":  "PARCIAL",
    "AUSENTE":  "AUSENTE",
})
