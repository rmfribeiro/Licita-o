from __future__ import annotations
import types
import ia_utils

from ia_utils import (
    chamar_api as _chamar_api,
    safe_float as _safe_float,
    fmt_brl as _fmt_brl,
    fmt_brl_opcional as _fmt_brl_opcional,
    optional_float as _optional_float,
)

_MODELO_PADRAO = "claude-haiku-4-5-20251001"

TIPOS_SANCAO: frozenset = frozenset({"advertencia", "multa", "impedimento", "inidoneidade"})

NIVEIS_GRAVIDADE: frozenset = frozenset({"LEVE", "MÉDIO", "GRAVE"})

# Estados de "sem base para afirmar". Este modulo produz uma MINUTA DE ATO que
# aplica penalidade e, no caso da multa, um VALOR EM DINHEIRO. Preencher lacuna
# com valor plausivel aqui nao e imprecisao: e inventar sancao.
SANCAO_NAO_DETERMINADA = "nao_determinada"
GRAVIDADE_NAO_AVALIADA = "NÃO AVALIADO"

# Art. 156, §3º: a multa nao pode superar 30% do valor do contrato. Nao ha, na
# lei, percentual MINIMO — o piso de 0,5% que existia aqui era invencao nossa.
TETO_MULTA_PCT = 30.0

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
    "Ao propor multa, identifique no documento a CLÁUSULA CONTRATUAL de penalidades e "
    "informe em 'base_calculo_multa' sobre QUAL base o percentual incide (valor total do "
    "contrato, valor da parcela inadimplida ou outra). A base muda o valor devido e é "
    "definida pelo contrato, não pelo analista. "
    "Responda SOMENTE com JSON válido no formato especificado. Não inclua texto fora do JSON."
)

# Referencias corretas, dadas ao modelo em vez de deixa-lo inventar.
# MEDIDO no teste 1 da Dosimetria (15/08/2026): a minuta assegurou recurso
# "conforme art. 157, §4º, da Lei 14.133/2021". O prazo (15 dias uteis) estava
# certo, mas o dispositivo esta ERRADO e o paragrafo nao existe: o art. 157
# trata da DEFESA PREVIA na multa; o RECURSO e o art. 166. Citacao errada numa
# peca levada a assinatura da autoridade e defeito grave.
_ANDAIME_LEGAL_MINUTA = (
    "Use EXATAMENTE estes dispositivos ao redigir, sem inventar parágrafos:\n"
    "- Defesa prévia na multa: art. 157 da Lei 14.133/2021 — 15 (quinze) dias úteis "
    "contados da intimação. O art. 157 NÃO tem parágrafos; não cite '§' dele.\n"
    "- Recurso contra advertência, multa e impedimento: art. 166 da Lei 14.133/2021 — "
    "15 (quinze) dias úteis contados da intimação.\n"
    "- Declaração de inidoneidade: cabe PEDIDO DE RECONSIDERAÇÃO (art. 167), não recurso.\n"
    "- Processo de responsabilização: art. 158.\n"
    "NÃO invente prazo de recolhimento da multa, número de portaria, data nem qualquer "
    "outro dado que não esteja acima: onde faltar informação, deixe lacuna sublinhada "
    "(ex.: 'no prazo de ____ dias, conforme previsto no contrato'). Um número inventado "
    "num ato administrativo vira obrigação para a empresa."
)

_SISTEMA_MINUTA = (
    "Você é especialista em redação de atos administrativos, portarias e decisões "
    "de processos administrativos sancionadores no âmbito da Lei 14.133/2021. "
    "Redija a minuta do ato administrativo de aplicação de sanção com linguagem formal, "
    "seguindo o padrão de atos oficiais da Administração Pública brasileira. "
    "Revise a ortografia antes de responder: o texto vai à assinatura de autoridade. "
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
    "base_calculo_multa": "valor total do contrato | valor da parcela inadimplida | outra (descrever)",
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


def _normalizar(parecer: dict, valor_contrato: float | None) -> dict:
    """Normaliza o parecer SEM preencher lacuna com valor plausivel.

    A versao anterior fazia, nesta ordem:
        tipo_sancao      or "multa"
        nivel_gravidade  or "MÉDIO"
        percentual_multa or 0.5      -> e depois max(0.5, ...)
    Ou seja: quando o modelo nao devolvia o campo, o CODIGO escolhia a sancao,
    escolhia a gravidade e escolhia um percentual — que em seguida multiplicava
    o valor do contrato e virava um VALOR EM REAIS na minuta do ato. Um numero
    inventado num documento que aplica penalidade a uma empresa. E o mesmo
    padrao do "0.0" da Pesquisa de Mercado e do 'or "Não"' do Integridade, no
    modulo onde ele custa mais caro.
    """
    for _k in ("_tipo_sancao_ia", "_gravidade_ia", "_percentual_ia", "_base_nao_calculavel"):
        parecer.pop(_k, None)

    enq = parecer.get("enquadramento") or {}
    _tipo_bruto = str(enq.get("tipo_sancao") or "").strip().lower()
    if _tipo_bruto in TIPOS_SANCAO:
        _tipo = _tipo_bruto
    else:
        _tipo = SANCAO_NAO_DETERMINADA
        if _tipo_bruto:                      # veio algo, mas irreconhecivel
            parecer["_tipo_sancao_ia"] = _tipo_bruto
    enq["tipo_sancao"] = _tipo

    dos = parecer.get("dosimetria") or {}
    _nivel_bruto = str(dos.get("nivel_gravidade") or "").strip().upper()
    if _nivel_bruto in NIVEIS_GRAVIDADE:
        _nivel = _nivel_bruto
    else:
        _nivel = GRAVIDADE_NAO_AVALIADA
        if _nivel_bruto:
            parecer["_gravidade_ia"] = _nivel_bruto
    dos["nivel_gravidade"] = _nivel

    if _tipo == "multa":
        _bruto = dos.get("percentual_multa")
        _pct = _safe_float(_bruto) if _bruto is not None else None
        if _pct is None or _pct <= 0:
            # Sem percentual, NAO ha multa a estimar. O percentual aplicavel vem
            # do edital/contrato; o sistema nao pode arbitra-lo.
            dos["percentual_multa"] = None
            dos["valor_multa_estimado"] = None
        else:
            if _pct > TETO_MULTA_PCT:
                # Nao silenciar: o teto legal foi aplicado, e o gestor precisa
                # saber que a IA propos acima dele.
                parecer["_percentual_ia"] = _pct
                _pct = TETO_MULTA_PCT
            dos["percentual_multa"] = _pct
            # A estimativa em reais so faz sentido se a base for o VALOR TOTAL do
            # contrato — que e o unico numero que temos. Quando o contrato manda
            # incidir sobre a parcela inadimplida (caso comum na multa moratoria),
            # calcular sobre o total infla a divida. Medido no teste 1 (15/08):
            # clausula limitava a 10% da parcela inadimplida (R$ 52.000), e o
            # sistema apresentou 10% de R$ 240.000 = R$ 24.000, 4,6x mais.
            _base = str(dos.get("base_calculo_multa") or "").strip().lower()
            _base_e_total = (not _base) or ("total" in _base) or ("contrato" in _base and "parcela" not in _base)
            if valor_contrato is not None and _base_e_total:
                dos["valor_multa_estimado"] = round(valor_contrato * _pct / 100, 2)
            else:
                dos["valor_multa_estimado"] = None
                if valor_contrato is not None and not _base_e_total:
                    parecer["_base_nao_calculavel"] = dos.get("base_calculo_multa")
    else:
        dos.pop("valor_multa_estimado", None)
        dos.pop("percentual_multa", None)

    alerta = parecer.get("alerta_criminal") or {}
    _crime = alerta.get("configura_crime")
    # None nao e "nao configura crime": e "nao avaliado". bool(None) dizia ao
    # leitor que a conduta foi analisada e descartada como crime.
    alerta["configura_crime"] = bool(_crime) if isinstance(_crime, bool) else None

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
    valor_contrato = _optional_float(dados_formulario.get("valor_contrato"))
    reincidencia = str(dados_formulario.get("reincidencia") or "Não verificado")

    partes = [
        "Análise de Dosimetria de Sanção Administrativa — Lei 14.133/2021\n",
        f"CNPJ do Fornecedor: {cnpj}",
        f"Número do Contrato: {numero_contrato}",
        "Valor do Contrato: " + _fmt_brl_opcional(valor_contrato, default='não informado'),
        f"Reincidência do Fornecedor: {reincidencia}",
    ]
    if reincidencia == "Sim":
        partes.append(
            "ATENÇÃO: Fornecedor reincidente — considere agravante do Art. 157, III, "
            "Lei 14.133/2021."
        )

    if texto_docs:
        # Isolamento anti-injecao: o documento de apuracao costuma vir com a
        # DEFESA da empresa apenada anexada. Parte interessada escrevendo dentro
        # do texto que o modelo le — o pior caso possivel para prompt cru.
        _bloco, _aviso_corte = ia_utils.bloco_documento(
            texto_docs, rotulo="documento de apuração", marca="DOCS_APURACAO"
        )
        partes.append(
            f"\nDocumento de apuração dos fatos (relatório / termo de ocorrência):\n{_bloco}"
        )
        if _aviso_corte:
            partes.append(_aviso_corte)
    else:
        partes.append(
            "\nNenhum documento adicional fornecido. Analise com base nas informações "
            "acima e sinalize que a fundamentação está limitada pela ausência de documentação."
        )

    partes.append(f"\nRetorne a análise no formato JSON:\n{_ESTRUTURA_PARECER}")

    resultado = _chamar_api(
        "\n".join(partes), api_key, modelo,
        _SISTEMA_DOSIMETRIA + ia_utils.SUFIXO_SEGURANCA,
        max_tokens=8000,
    )
    return _normalizar(resultado, valor_contrato)


def gerar_minuta(
    parecer: dict,
    dados_formulario: dict,
    api_key: str,
    modelo: str = _MODELO_PADRAO,
) -> str:
    enq = parecer.get("enquadramento") or {}
    dos = parecer.get("dosimetria") or {}
    tipo = str(enq.get("tipo_sancao") or SANCAO_NAO_DETERMINADA)
    if tipo == SANCAO_NAO_DETERMINADA or tipo not in TIPOS_SANCAO:
        # Nao se redige ato que aplica penalidade sem saber QUAL penalidade.
        raise ValueError(
            "a análise não determinou o tipo de sanção; sem isso não é possível "
            "redigir a minuta do ato"
        )
    label_sancao = LABEL_SANCAO.get(tipo, tipo.title())

    autoridade = str(dados_formulario.get("autoridade") or "Autoridade Competente")
    orgao = str(dados_formulario.get("orgao") or "Órgão/Entidade")
    cnpj = str(dados_formulario.get("cnpj") or "")
    numero_contrato = str(dados_formulario.get("numero_contrato") or "não informado")
    valor_contrato = _optional_float(dados_formulario.get("valor_contrato"))

    partes = [
        "Redija a MINUTA DO ATO ADMINISTRATIVO de aplicação de sanção, "
        "com base no parecer abaixo.\n",
        f"Órgão/Entidade: {orgao}",
        f"Autoridade competente: {autoridade}",
        f"CNPJ do Fornecedor Apenado: {cnpj}",
        f"Número do Contrato: {numero_contrato}",
        "Valor do Contrato: " + _fmt_brl_opcional(valor_contrato, default='não informado'),
        f"\nSanção aplicada: {label_sancao}",
        f"Artigo de enquadramento: {enq.get('artigo') or 'Art. 156, Lei 14.133/2021'}",
        f"Justificativa: {enq.get('justificativa') or ''}",
        f"\nFatos apurados: {parecer.get('fatos_apurados') or ''}",
    ]

    if tipo == "multa":
        # Sem percentual apurado a minuta NAO pode trazer um numero: ela mandaria
        # a empresa pagar um valor que o sistema inventou.
        _pct_m = dos.get("percentual_multa")
        if _pct_m is None:
            partes.append(
                "Percentual da multa: NÃO DETERMINADO pela análise. Na minuta, deixe o "
                "percentual e o valor em branco, com a indicação de que devem ser "
                "preenchidos conforme o percentual previsto no edital e no contrato. "
                "NÃO arbitre percentual nem valor."
            )
        else:
            _val_est = dos.get("valor_multa_estimado")
            _linha_multa = f"Percentual da multa: {_pct_m}%"
            if _val_est:
                _linha_multa += f" ({_fmt_brl(_safe_float(_val_est))} estimado)"
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

    _base_m = dos.get("base_calculo_multa")
    if tipo == "multa" and _base_m:
        partes.append(f"Base de cálculo da multa (conforme o contrato): {_base_m}")
    partes.append("\n" + _ANDAIME_LEGAL_MINUTA)

    resultado = _chamar_api(
        "\n".join(partes), api_key, modelo,
        _SISTEMA_MINUTA + ia_utils.SUFIXO_SEGURANCA,
        max_tokens=8000,          # ato administrativo inteiro nao cabe em 3.000
    )
    return str(resultado.get("minuta") or "")
