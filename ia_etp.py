from __future__ import annotations
from ia_utils import chamar_api as _chamar_api

_MODELO_PADRAO = "claude-haiku-4-5-20251001"
_ADEQ_VALIDOS = {"ADEQUADO", "ADEQUADO COM RESSALVAS", "INADEQUADO"}

_SISTEMA = (
    "Você é um auditor especialista em contratações públicas federais brasileiras. "
    "Analise o Estudo Técnico Preliminar (ETP) fornecido à luz da IN SEGES/MGI 58/2022 "
    "e do art. 18 da Lei 14.133/2021. Avalie cada uma das 8 dimensões obrigatórias do ETP. "
    "Responda SOMENTE com JSON válido no formato especificado. Não inclua texto fora do JSON."
)

_ESTRUTURA_PARECER = """{
  "adequacao_geral": "ADEQUADO | ADEQUADO COM RESSALVAS | INADEQUADO",
  "dimensoes": {
    "descricao_necessidade":       {"status": "ok|alerta|critico", "descricao": "..."},
    "alinhamento_estrategico":     {"status": "ok|alerta|critico", "descricao": "..."},
    "requisitos_contratacao":      {"status": "ok|alerta|critico", "descricao": "..."},
    "levantamento_mercado":        {"status": "ok|alerta|critico", "descricao": "..."},
    "estimativa_quantidade_valor": {"status": "ok|alerta|critico", "descricao": "..."},
    "sustentabilidade":            {"status": "ok|alerta|critico", "descricao": "..."},
    "parcelamento":                {"status": "ok|alerta|critico", "descricao": "..."},
    "posicionamento_conclusivo":   {"status": "ok|alerta|critico", "descricao": "..."}
  },
  "pontos_criticos": ["..."],
  "recomendacoes": ["..."],
  "base_legal": ["IN SEGES/MGI 58/2022", "Lei 14.133/2021, art. 18, I"]
}"""


def analisar_etp(texto: str, api_key: str, modelo: str = _MODELO_PADRAO) -> dict:
    if not texto or not texto.strip():
        raise ValueError("Texto do ETP está vazio — faça o upload de um arquivo com conteúdo.")
    prompt = (
        f"Analise o seguinte Estudo Técnico Preliminar (ETP) e documentos complementares:\n\n"
        f"{texto}\n\n"
        f"Retorne o parecer de auditoria no formato:\n{_ESTRUTURA_PARECER}"
    )
    parecer = _chamar_api(prompt, api_key, modelo, _SISTEMA, max_tokens=3000)
    _adeq = str(parecer.get("adequacao_geral") or "INADEQUADO").strip().upper()
    parecer["adequacao_geral"] = _adeq if _adeq in _ADEQ_VALIDOS else "INADEQUADO"
    return parecer
