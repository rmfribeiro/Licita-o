from __future__ import annotations
import types
import logging
try:
    import streamlit as st
    _HAS_ST = True
except ImportError:
    _HAS_ST = False
from ia_utils import chamar_api as _chamar_api

_MODELO_PADRAO = "claude-haiku-4-5-20251001"
_MATURIDADE_ORDEM = ["INEXISTENTE", "INICIAL", "EM DESENVOLVIMENTO", "CONSOLIDADO"]


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

_ROTULOS_QUESTIONARIO: types.MappingProxyType[str, str] = types.MappingProxyType({
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
})

LABEL_DIMENSAO = {
    "compromisso_alta_gestao": "Compromisso da Alta Gestão",
    "diretrizes_integridade":  "Diretrizes de Integridade",
    "base_legal_normativa":    "Base Legal e Normativa",
    "responsabilizacao":       "Responsabilização",
    "metodologia_gestao":      "Metodologia de Gestão",
    "tres_linhas_defesa":      "Três Linhas de Defesa",
}

ICONE_MATURIDADE = {
    "CONSOLIDADO":        "🟢",
    "EM DESENVOLVIMENTO": "🔵",
    "INICIAL":            "🟡",
    "INEXISTENTE":        "🔴",
}

COR_MATURIDADE_HEX: types.MappingProxyType[str, str] = types.MappingProxyType({
    "CONSOLIDADO":        "#27AE60",
    "EM DESENVOLVIMENTO": "#2980B9",
    "INICIAL":            "#F39C12",
    "INEXISTENTE":        "#C0392B",
})

QUESTOES_PIP: tuple[tuple[str, str], ...] = tuple(_ROTULOS_QUESTIONARIO.items())

_CHAVE_ATO_FORMAL        = "q_ato_formal"
_CHAVE_RESPONSAVEL       = "q_responsavel_designado"

_chaves_pip = {k for k, _ in QUESTOES_PIP}
_ausentes = {_CHAVE_ATO_FORMAL, _CHAVE_RESPONSAVEL} - _chaves_pip
if _ausentes:
    raise RuntimeError(
        f"Chaves críticas ausentes em QUESTOES_PIP: "
        f"{', '.join(repr(c) for c in sorted(_ausentes))}"
    )


def _aplicar_piso(respostas: dict, maturidade_ia: str) -> str:
    valores = [str(respostas.get(k) or "Não").strip() for k, _ in QUESTOES_PIP]

    # Regra 1 (mais restritiva) — todos Não → INEXISTENTE
    if all(v == "Não" for v in valores):
        return "INEXISTENTE"

    # Regra 2 — campos críticos ausentes/parciais → cap INICIAL
    ato = str(respostas.get(_CHAVE_ATO_FORMAL) or "Não").strip()
    resp = str(respostas.get(_CHAVE_RESPONSAVEL) or "Não").strip()
    if ato in {"Não", "Parcialmente"} and resp in {"Não", "Parcialmente"}:
        idx_ia = _MATURIDADE_ORDEM.index(maturidade_ia) if maturidade_ia in _MATURIDADE_ORDEM else 0
        if idx_ia > _MATURIDADE_ORDEM.index("INICIAL"):
            return "INICIAL"

    return maturidade_ia


def diagnosticar(
    respostas: dict,
    texto_docs: str | None,
    api_key: str,
    modelo: str = _MODELO_PADRAO,
    parecer_ddi: dict | None = None,
) -> dict:
    partes = ["Questionário sobre o Programa de Integridade Pública da prefeitura:\n"]
    for chave, pergunta in QUESTOES_PIP:
        partes.append(f"- {pergunta} Resposta: {respostas.get(chave, 'Não informado')}")

    if texto_docs:
        partes.append(f"\nDocumentos da prefeitura fornecidos:\n{texto_docs[:30000]}")

    if parecer_ddi:
        pi = parecer_ddi.get("dimensoes", {}).get("programa_integridade", {})
        if pi:
            partes.append(
                f"\nContexto DDI (Due Diligence de fornecedor relacionado):\n"
                f"- Status do programa de integridade: {pi.get('status', '-')}\n"
                f"- Descrição: {pi.get('descricao', '-')}\n"
                f"- Programa obrigatório: {pi.get('obrigatorio', '-')}\n"
                f"- Empresa Pró-Ética: {pi.get('pro_etica', '-')}"
            )

    partes.append(f"\nRetorne o diagnóstico no formato:\n{_ESTRUTURA_PARECER}")

    parecer = _chamar_api(
        "\n".join(partes), api_key, modelo, _SISTEMA, max_tokens=3000
    )

    _mat = str(parecer.get("maturidade_geral") or "INEXISTENTE").strip().upper()
    if _mat not in _MATURIDADE_ORDEM:
        logging.warning(
            "ia_integridade: maturidade_geral inesperada da IA: %r — normalizado para INEXISTENTE", _mat
        )
        _mat = "INEXISTENTE"
    parecer["maturidade_geral"] = _aplicar_piso(respostas, _mat)

    return parecer
