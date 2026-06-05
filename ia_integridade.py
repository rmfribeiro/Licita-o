from __future__ import annotations
import json
import os
import urllib.request
import urllib.error
try:
    import streamlit as st
    _HAS_ST = True
except ImportError:
    _HAS_ST = False
from ia_utils import extrair_json as _extrair_json

_MODELO_PADRAO = "claude-haiku-4-5-20251001"
_MATURIDADE_ORDEM = ["INEXISTENTE", "INICIAL", "EM DESENVOLVIMENTO", "CONSOLIDADO"]

_CHAVES_QUESTIONARIO = [
    "q_ato_formal", "q_responsavel_designado",
    "q_diretrizes_publicadas", "q_diretrizes_divulgadas",
    "q_base_legal_conhecida",
    "q_mecanismos_responsabilizacao", "q_precedentes_punicao",
    "q_plano_gestao", "q_indicadores",
    "q_primeira_linha", "q_segunda_linha", "q_terceira_linha",
]

_SISTEMA = (
    "Você é um consultor sênior especialista em Programas de Integridade Pública (PIP) "
    "para a Administração Pública municipal brasileira. "
    "Avalie o estágio de maturidade do Programa de Integridade da prefeitura com base nas "
    "respostas do questionário e nos documentos fornecidos, à luz do Decreto 11.129/2022, "
    "da IN CGU 21/2021, da Lei 12.846/2013 (art. 7º, III) e do Decreto 8.420/2015. "
    "Responda SOMENTE com JSON válido no formato especificado. Não inclua texto fora do JSON."
)

_ESTRUTURA_PARECER = """{
  "maturidade_geral": "INEXISTENTE|INICIAL|EM DESENVOLVIMENTO|CONSOLIDADO",
  "dimensoes": {
    "compromisso_alta_gestao": {"nivel": "...", "achados": ["..."], "recomendacoes": ["..."]},
    "diretrizes_integridade":  {"nivel": "...", "achados": ["..."], "recomendacoes": ["..."]},
    "base_legal_normativa":    {"nivel": "...", "achados": ["..."], "recomendacoes": ["..."]},
    "responsabilizacao":       {"nivel": "...", "achados": ["..."], "recomendacoes": ["..."]},
    "metodologia_gestao":      {"nivel": "...", "achados": ["..."], "recomendacoes": ["..."]},
    "tres_linhas_defesa":      {"nivel": "...", "achados": ["..."], "recomendacoes": ["..."]}
  },
  "prioridades": ["ação imediata 1", "ação imediata 2", "ação imediata 3"],
  "resumo_executivo": "parágrafo para apresentar ao prefeito",
  "base_legal": ["Decreto 11.129/2022", "IN CGU 21/2021", "Lei 12.846/2013, art. 7 III", "Decreto 8.420/2015"]
}"""

_ROTULOS_QUESTIONARIO = {
    "q_ato_formal":                  "Existe ato formal do prefeito instituindo o PIP?",
    "q_responsavel_designado":       "Há responsável formalmente designado pelo PIP?",
    "q_diretrizes_publicadas":       "As diretrizes de integridade foram publicadas?",
    "q_diretrizes_divulgadas":       "As diretrizes foram divulgadas a todos os servidores?",
    "q_base_legal_conhecida":        "A autoridade superior conhece o marco legal do PIP (Decreto 11.129/2022, IN CGU 21/2021)?",
    "q_mecanismos_responsabilizacao":"Existem mecanismos formais de responsabilização de servidores?",
    "q_precedentes_punicao":         "Já houve apuração e punição por irregularidades nesta prefeitura?",
    "q_plano_gestao":                "Existe plano formal de gestão e acompanhamento do PIP?",
    "q_indicadores":                 "Existem indicadores definidos para monitorar o PIP?",
    "q_primeira_linha":              "Gestores de linha conhecem e exercem seus controles de conformidade?",
    "q_segunda_linha":               "Controle interno está estruturado e ativo?",
    "q_terceira_linha":              "Auditoria interna existe e funciona de forma independente?",
}


def _aplicar_piso(respostas: dict, maturidade_ia: str) -> str:
    valores = [str(respostas.get(k) or "Não").strip() for k in _CHAVES_QUESTIONARIO]

    # Regra 1 (mais restritiva) — todos Não → INEXISTENTE
    if all(v == "Não" for v in valores):
        return "INEXISTENTE"

    # Regra 2 — campos críticos ausentes/parciais → cap INICIAL
    ato = str(respostas.get("q_ato_formal") or "Não").strip()
    resp = str(respostas.get("q_responsavel_designado") or "Não").strip()
    if ato in {"Não", "Parcialmente"} and resp in {"Não", "Parcialmente"}:
        idx_ia = _MATURIDADE_ORDEM.index(maturidade_ia) if maturidade_ia in _MATURIDADE_ORDEM else 3
        if idx_ia > _MATURIDADE_ORDEM.index("INICIAL"):
            return "INICIAL"

    return maturidade_ia
