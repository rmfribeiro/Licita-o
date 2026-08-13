from __future__ import annotations
import ia_utils
from ia_utils import chamar_api as _chamar_api, normalizar_adequacao as _normalizar_adequacao

_MODELO_PADRAO = "claude-haiku-4-5-20251001"

# O sistema NOMEIA as 8 dimensões e pede descrição objetiva, espelhando o do
# módulo de TR — que, com essa formulação, produziu dois pareceres idênticos.
# A versão anterior dizia apenas "avalie as 8 dimensões obrigatórias", sem
# nomeá-las: instrução vaga, e o resultado foi o mesmo ETP saindo "ADEQUADO COM
# RESSALVAS" numa execução e "INADEQUADO" na seguinte, com 86 linhas de texto
# divergente.
_SISTEMA = (
    "Você é um auditor especialista em contratações públicas federais brasileiras. "
    "Analise o Estudo Técnico Preliminar (ETP) fornecido à luz da IN SEGES/MGI 58/2022 "
    "e do art. 18 da Lei 14.133/2021. Avalie as 8 dimensões obrigatórias: "
    "descricao_necessidade, alinhamento_estrategico, requisitos_contratacao, "
    "levantamento_mercado, estimativa_quantidade_valor, sustentabilidade, "
    "parcelamento, posicionamento_conclusivo. "
    "Para cada dimensão, atribua status ok/alerta/critico e uma descrição OBJETIVA "
    "de no máximo 3 frases, citando o item do documento quando possível. "
    "Use 'critico' apenas para falha que compromete a legalidade da contratação; "
    "'alerta' para lacuna que exige complementação; 'ok' quando a dimensão está "
    "atendida. Não emita juízo sobre a adequação geral: ela é calculada a partir "
    "dos status que você atribuir. "
    "Responda SOMENTE com JSON válido no formato especificado. Não inclua texto fora do JSON."
    + ia_utils.SUFIXO_SEGURANCA
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
    # O ETP vem isolado em bloco delimitado: ate 13/08/2026 o texto do usuario
    # entrava cru no prompt, sem protecao contra instrucoes escondidas no
    # documento — e sem limite de tamanho proprio.
    _bloco, _aviso_corte = ia_utils.bloco_documento(texto, rotulo="ETP", marca="ETP")
    prompt = (
        f"Analise o seguinte Estudo Técnico Preliminar (ETP) e documentos complementares.\n"
        f"{_aviso_corte}\n"
        f"{_bloco}\n\n"
        f"Retorne o parecer de auditoria no formato:\n{_ESTRUTURA_PARECER}"
    )
    # max_tokens 3.000 era apertado: sao 8 dimensoes com descricao, mais pontos
    # criticos, recomendacoes e base legal. JSON truncado vira parecer com
    # dimensoes faltando — e o reparo de JSON as descarta em silencio.
    parecer = _chamar_api(prompt, api_key, modelo, _SISTEMA, max_tokens=8000)
    _normalizar_adequacao(parecer, "ia_etp")
    return parecer
