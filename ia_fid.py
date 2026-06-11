from __future__ import annotations
import types
from ia_utils import chamar_api as _chamar_api

_MODELO_PADRAO = "claude-haiku-4-5-20251001"

FASES_PROCESSO: types.MappingProxyType[str, str] = types.MappingProxyType({
    "habilitacao":     "Fase de Habilitação",
    "proposta":        "Fase de Julgamento de Propostas",
    "pos_adjudicacao": "Pós-Adjudicação / Pré-Contratação",
})

RESULTADO_DILIGENCIA: types.MappingProxyType[str, str] = types.MappingProxyType({
    "SIM":          "SIM",
    "NÃO":          "NÃO",
    "PARCIALMENTE": "PARCIALMENTE",
})

_NORM_RESULTADO: dict[str, str] = {
    "NAO":             "NÃO",
    "NÃO NECESSITA":   "NÃO",
    "NAO NECESSITA":   "NÃO",
    "PARCIAL":         "PARCIALMENTE",
}

_SISTEMA = (
    "Você é um especialista em licitações e contratações públicas brasileiras, "
    "com profundo conhecimento na Lei 14.133/2021. Analise os dados do licitante e a "
    "situação descrita para identificar a necessidade de aplicação do Instituto da "
    "Diligência, conforme Art. 42 §2º (fase pré-contratual), Art. 59 §2º (julgamento de "
    "propostas) e Art. 64, incisos I e II (complementação de informações e verificação de "
    "declarações). Identifique documentos ausentes, vencidos, inconsistentes ou ilegíveis "
    "e redija a minuta do Ofício de Diligência, com linguagem formal, concisa e embasada "
    "na lei. "
    "Responda SOMENTE com JSON válido no formato especificado. Não inclua texto fora do JSON."
)

_ESTRUTURA_PARECER = """{
  "necessita_diligencia": "SIM|NÃO|PARCIALMENTE",
  "documentos_solicitados": [
    {
      "documento": "nome do documento ou informação solicitada",
      "situacao": "ausente|vencido|ilegível|inconsistente|pendente",
      "fundamento_legal": "artigo específico da Lei 14.133/2021",
      "prazo_dias": 5
    }
  ],
  "pontos_de_atencao": ["observação relevante 1"],
  "minuta_oficio": "OFÍCIO DE DILIGÊNCIA Nº _____\\n\\nAssunto: ...\\n\\nSenhor(a) Representante,\\n\\n...",
  "prazo_resposta_sugerido": 5,
  "conclusao": "parágrafo conclusivo com o fundamento da diligência",
  "base_legal": ["Art. 59, §2º, Lei 14.133/2021", "Art. 64, I e II, Lei 14.133/2021"]
}"""


def analisar(
    fase: str,
    dados_licitante: dict,
    descricao_situacao: str,
    texto_docs: str | None,
    api_key: str,
    modelo: str = _MODELO_PADRAO,
) -> dict:
    if fase not in FASES_PROCESSO:
        raise ValueError(
            f"Fase inválida: '{fase}'. Esperado: {list(FASES_PROCESSO)}"
        )

    partes = [
        f"Instituto da Diligência — {FASES_PROCESSO[fase]}\n",
        f"Licitante: {dados_licitante.get('razao_social') or 'não informado'}",
        f"CNPJ: {dados_licitante.get('cnpj') or 'não informado'}",
        f"Número do Edital/Processo: {dados_licitante.get('numero_edital') or 'não informado'}",
        f"Objeto: {dados_licitante.get('objeto') or 'não informado'}",
        f"Órgão: {dados_licitante.get('orgao') or 'não informado'}",
        "",
        f"Fase do processo licitatório: {FASES_PROCESSO[fase]}",
        "",
        "Situação identificada / dúvidas a esclarecer:",
        descricao_situacao or "Não informada.",
    ]

    if texto_docs:
        partes.append(f"\nDocumentos de habilitação fornecidos para análise:\n{texto_docs[:30000]}")
    else:
        partes.append(
            "\nNenhum documento físico anexado. Analise com base na situação descrita "
            "e sinalize os itens não verificáveis pela ausência de documentação."
        )

    partes.append(f"\nRetorne o parecer no formato JSON:\n{_ESTRUTURA_PARECER}")

    parecer = _chamar_api(
        "\n".join(partes), api_key, modelo, _SISTEMA, max_tokens=4000
    )

    _res = str(parecer.get("necessita_diligencia") or "PARCIALMENTE").strip().upper()
    _res = _NORM_RESULTADO.get(_res, _res)
    parecer["necessita_diligencia"] = _res if _res in RESULTADO_DILIGENCIA else "PARCIALMENTE"

    _prazo = parecer.get("prazo_resposta_sugerido")
    try:
        _prazo_int = 5 if (_prazo is None or isinstance(_prazo, bool)) else int(_prazo)
    except (ValueError, TypeError):
        _prazo_int = 5
    parecer["prazo_resposta_sugerido"] = max(1, min(30, _prazo_int))

    return parecer
