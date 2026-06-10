from __future__ import annotations
import types

from ia_utils import (
    chamar_api as _chamar_api,
    safe_float as _safe_float,
    fmt_brl as _fmt_brl,
)

_MODELO_PADRAO = "claude-haiku-4-5-20251001"

TIPOS_SANCAO: frozenset = frozenset({"advertencia", "multa", "impedimento", "inidoneidade"})

NIVEIS_GRAVIDADE: frozenset = frozenset({"LEVE", "MÉDIO", "GRAVE"})

REINCIDENCIA_OPCOES: types.MappingProxyType[str, str] = types.MappingProxyType({
    "Sim":            "Sim",
    "Não":            "Não",
    "Não verificado": "Não verificado",
})

LABEL_SANCAO: types.MappingProxyType[str, str] = types.MappingProxyType({
    "advertencia":  "Advertência",
    "multa":        "Multa",
    "impedimento":  "Impedimento de Licitar e Contratar",
    "inidoneidade": "Declaração de Inidoneidade",
})

_SISTEMA_DOSIMETRIA = (
    "Você é um especialista em direito administrativo sancionador brasileiro, "
    "com amplo conhecimento dos Arts. 156 a 159 e 178 da Lei 14.133/2021. "
    "Analise os fatos apurados e aplique a dosimetria da sanção administrativa cabível, "
    "fundamentando juridicamente a escolha e o grau da penalidade. "
    "Avalie também se a conduta descrita pode configurar crime tipificado no Art. 178 "
    "da Lei 14.133/2021, indicando o artigo específico quando aplicável. "
    "Responda SOMENTE com JSON válido no formato especificado. Não inclua texto fora do JSON."
)

_SISTEMA_MINUTA = (
    "Você é especialista em redação de atos administrativos, portarias e decisões "
    "de processos administrativos sancionadores no âmbito da Lei 14.133/2021. "
    "Redija a minuta do ato administrativo de aplicação de sanção com linguagem formal, "
    "seguindo o padrão de atos oficiais da Administração Pública brasileira. "
    'Responda SOMENTE com JSON válido no formato {"minuta": "texto completo"}. '
    "Não inclua texto fora do JSON."
)

_ESTRUTURA_PARECER = """{
  "fatos_apurados": "resumo objetivo dos fatos extraídos do documento",
  "condutas_identificadas": ["inexecução parcial do contrato", "atraso injustificado"],
  "enquadramento": {
    "tipo_sancao": "advertencia | multa | impedimento | inidoneidade",
    "artigo": "Art. 156, II, Lei 14.133/2021",
    "justificativa": "fundamentação da escolha da sanção"
  },
  "dosimetria": {
    "percentual_multa": 10.0,
    "valor_multa_estimado": 15000.00,
    "prazo_sancao": null,
    "nivel_gravidade": "LEVE | MÉDIO | GRAVE",
    "agravantes": ["reincidência", "dano ao erário"],
    "atenuantes": ["colaboração com a apuração"]
  },
  "alerta_criminal": {
    "configura_crime": false,
    "artigo_178": null,
    "descricao_conduta": null,
    "recomendacao": null
  },
  "base_legal": [
    "Art. 156, II, Lei 14.133/2021",
    "Art. 157, Lei 14.133/2021",
    "Art. 158, §1º, Lei 14.133/2021"
  ]
}"""


def _normalizar(parecer: dict, valor_contrato: float) -> dict:
    enq = parecer.get("enquadramento") or {}
    _tipo = str(enq.get("tipo_sancao") or "multa").strip().lower()
    if _tipo not in TIPOS_SANCAO:
        _tipo = "multa"
    enq["tipo_sancao"] = _tipo

    dos = parecer.get("dosimetria") or {}
    _nivel = str(dos.get("nivel_gravidade") or "MÉDIO").strip().upper()
    if _nivel not in NIVEIS_GRAVIDADE:
        _nivel = "MÉDIO"
    dos["nivel_gravidade"] = _nivel

    if _tipo == "multa":
        _pct = _safe_float(dos.get("percentual_multa") or 0.5)
        dos["percentual_multa"] = max(0.5, min(30.0, _pct))
        if valor_contrato > 0:
            dos["valor_multa_estimado"] = round(
                valor_contrato * dos["percentual_multa"] / 100, 2
            )
        else:
            # Sem valor de contrato: zera estimativa para não exibir alucinação do LLM
            dos["valor_multa_estimado"] = 0.0
    else:
        dos.pop("valor_multa_estimado", None)

    alerta = parecer.get("alerta_criminal") or {}
    alerta["configura_crime"] = bool(alerta.get("configura_crime"))

    parecer["enquadramento"] = enq
    parecer["dosimetria"] = dos
    parecer["alerta_criminal"] = alerta
    return parecer


def analisar_dosimetria(
    dados_formulario: dict,
    texto_docs: str | None,
    api_key: str,
    modelo: str = _MODELO_PADRAO,
) -> dict:
    cnpj = str(dados_formulario.get("cnpj") or "")
    numero_contrato = str(dados_formulario.get("numero_contrato") or "não informado")
    valor_contrato = _safe_float(dados_formulario.get("valor_contrato"))
    reincidencia = str(dados_formulario.get("reincidencia") or "Não verificado")

    partes = [
        "Análise de Dosimetria de Sanção Administrativa — Lei 14.133/2021\n",
        f"CNPJ do Fornecedor: {cnpj}",
        f"Número do Contrato: {numero_contrato}",
        f"Valor do Contrato: {_fmt_brl(valor_contrato)}",
        f"Reincidência do Fornecedor: {reincidencia}",
    ]
    if reincidencia == "Sim":
        partes.append(
            "ATENÇÃO: Fornecedor reincidente — considere agravante do Art. 157, III, "
            "Lei 14.133/2021."
        )

    if texto_docs:
        partes.append(
            f"\nDocumento de apuração dos fatos (relatório / termo de ocorrência):\n"
            f"{texto_docs[:30000]}"
        )
    else:
        partes.append(
            "\nNenhum documento adicional fornecido. Analise com base nas informações "
            "acima e sinalize que a fundamentação está limitada pela ausência de documentação."
        )

    partes.append(f"\nRetorne a análise no formato JSON:\n{_ESTRUTURA_PARECER}")

    resultado = _chamar_api("\n".join(partes), api_key, modelo, _SISTEMA_DOSIMETRIA)
    return _normalizar(resultado, valor_contrato)


def gerar_minuta(
    parecer: dict,
    dados_formulario: dict,
    api_key: str,
    modelo: str = _MODELO_PADRAO,
) -> str:
    enq = parecer.get("enquadramento") or {}
    dos = parecer.get("dosimetria") or {}
    tipo = str(enq.get("tipo_sancao") or "multa")
    label_sancao = LABEL_SANCAO.get(tipo, tipo.title())

    autoridade = str(dados_formulario.get("autoridade") or "Autoridade Competente")
    orgao = str(dados_formulario.get("orgao") or "Órgão/Entidade")
    cnpj = str(dados_formulario.get("cnpj") or "")
    numero_contrato = str(dados_formulario.get("numero_contrato") or "não informado")
    valor_contrato = _safe_float(dados_formulario.get("valor_contrato"))

    partes = [
        "Redija a MINUTA DO ATO ADMINISTRATIVO de aplicação de sanção, "
        "com base no parecer abaixo.\n",
        f"Órgão/Entidade: {orgao}",
        f"Autoridade competente: {autoridade}",
        f"CNPJ do Fornecedor Apenado: {cnpj}",
        f"Número do Contrato: {numero_contrato}",
        f"Valor do Contrato: {_fmt_brl(valor_contrato)}",
        f"\nSanção aplicada: {label_sancao}",
        f"Artigo de enquadramento: {enq.get('artigo') or 'Art. 156, Lei 14.133/2021'}",
        f"Justificativa: {enq.get('justificativa') or ''}",
        f"\nFatos apurados: {parecer.get('fatos_apurados') or ''}",
    ]

    if tipo == "multa":
        _pct_m = dos.get("percentual_multa") or 0.5
        _val_est = _safe_float(dos.get("valor_multa_estimado") or 0)
        _linha_multa = f"Percentual da multa: {_pct_m}%"
        if _val_est > 0:
            _linha_multa += f" ({_fmt_brl(_val_est)} estimado)"
        partes.append(_linha_multa)
    elif tipo in ("impedimento", "inidoneidade"):
        _prazo = dos.get("prazo_sancao")
        if _prazo:
            partes.append(f"Prazo da sanção: {_prazo} ano(s)")

    _agravantes = [str(a) for a in (dos.get("agravantes") or []) if a]
    _atenuantes = [str(a) for a in (dos.get("atenuantes") or []) if a]
    if _agravantes:
        partes.append(f"Agravantes: {', '.join(_agravantes)}")
    if _atenuantes:
        partes.append(f"Atenuantes: {', '.join(_atenuantes)}")

    _bl = [str(b) for b in (parecer.get("base_legal") or []) if b]
    if _bl:
        partes.append(f"\nBase legal: {'; '.join(_bl)}")

    partes.append(
        "\nIncluir na minuta: cabeçalho (órgão, número do ato, data), "
        "considerandos com os fatos apurados e o enquadramento legal, "
        "dispositivo com a sanção aplicada e prazo de recurso de 15 dias úteis "
        "(Art. 157, §4º, Lei 14.133/2021), e local para assinatura da autoridade."
    )
    partes.append('\nRetorne SOMENTE: {"minuta": "texto completo do ato"}')

    resultado = _chamar_api("\n".join(partes), api_key, modelo, _SISTEMA_MINUTA)
    return str(resultado.get("minuta") or "")
