from __future__ import annotations
import calendar
import ia_utils
import logging
import types
from datetime import date, datetime
from ia_utils import (
    chamar_api as _chamar_api,
    fmt_brl_opcional as _fmt_brl_opcional,
    normalizar_parecer as _normalizar_parecer,
)

_MODELO_PADRAO = "claude-haiku-4-5-20251001"

TIPOS_SANCAO: types.MappingProxyType[str, str] = types.MappingProxyType({
    "impedimento":  "Impedimento de Licitar e Contratar (Art. 156, III)",
    "inidoneidade": "Declaração de Inidoneidade (Art. 156, IV)",
})

PRAZOS_MINIMOS_ANOS: types.MappingProxyType[str, int] = types.MappingProxyType({
    "impedimento":  1,
    "inidoneidade": 3,
})

PARECER_OPTIONS: types.MappingProxyType[str, str] = types.MappingProxyType({
    "ELEGÍVEL":               "ELEGÍVEL",
    "ELEGÍVEL COM RESSALVAS": "ELEGÍVEL COM RESSALVAS",
    "INELEGÍVEL":             "INELEGÍVEL",
})

# Estado distinto dos tres pareceres. Aqui o fallback antigo era INELEGIVEL —
# negar reabilitacao por resposta malformada do modelo mantem uma empresa fora
# do mercado publico sem base. Negar sem fundamento e tao grave quanto deferir.
PARECER_NAO_AVALIADO = "NÃO AVALIADO"

NORM_PARECER_REAB: types.MappingProxyType[str, str] = types.MappingProxyType({
    "ELEGIVEL":               "ELEGÍVEL",
    "ELEGIVEL COM RESSALVAS": "ELEGÍVEL COM RESSALVAS",
    "ELEGIVEL COM RESSALVA":  "ELEGÍVEL COM RESSALVAS",
    "ELEGÍVEL COM RESSALVA":  "ELEGÍVEL COM RESSALVAS",
    "INELEGIVEL":             "INELEGÍVEL",
})


def calcular_prazo(
    tipo_sancao: str,
    data_aplicacao: date,
    data_referencia: date | None = None,
) -> dict:
    if tipo_sancao not in PRAZOS_MINIMOS_ANOS:
        raise ValueError(
            f"tipo_sancao inválido: '{tipo_sancao}'. Esperado: {list(TIPOS_SANCAO)}"
        )
    hoje = data_referencia or date.today()
    prazo_anos = PRAZOS_MINIMOS_ANOS[tipo_sancao]

    anos = hoje.year - data_aplicacao.year
    meses = hoje.month - data_aplicacao.month
    _last_day = calendar.monthrange(hoje.year, hoje.month)[1]
    if hoje.day < min(data_aplicacao.day, _last_day):
        meses -= 1
    if meses < 0:
        anos -= 1
        meses += 12

    total_meses = anos * 12 + meses
    return {
        "atendido":          total_meses >= prazo_anos * 12,
        "anos_decorridos":   anos,
        "meses_decorridos":  meses,
        "prazo_minimo_anos": prazo_anos,
    }


_SISTEMA = (
    "Você é um especialista em licitações e contratos públicos brasileiros. "
    "Analise o pedido de reabilitação de fornecedor com base no Art. 163, Parágrafo Único, "
    "da Lei 14.133/2021. Avalie cada uma das 5 condições cumulativas e emita parecer de "
    "elegibilidade motivado. "
    "Responda SOMENTE com JSON válido no formato especificado. Não inclua texto fora do JSON."
)

_ESTRUTURA_PARECER = """{
  "parecer": "ELEGÍVEL|ELEGÍVEL COM RESSALVAS|INELEGÍVEL",
  "condicoes_avaliadas": [
    {
      "numero": "I",
      "descricao": "Reparação integral do dano",
      "status": "ATENDIDA|PARCIAL|AUSENTE|N.A.",
      "observacao": "..."
    }
  ],
  "sintese": "Parágrafo conclusivo fundamentado no Art. 163 Par. Único, Lei 14.133/2021",
  "base_legal": ["Art. 163, Par. Único, Lei 14.133/2021"]
}"""


def _inelegivel_data_futura(data_apl: date, ref: date, dados_empresa: dict, dados_sancao: dict) -> dict:
    return {
        "parecer": "INELEGÍVEL",
        "condicoes_avaliadas": [{"numero": "III", "descricao": "Transcurso do prazo mínimo",
            "status": "AUSENTE", "observacao": (
                f"Data de aplicação da sanção ({data_apl}) é posterior à data de "
                f"referência ({ref}) — verifique o dado informado.")}],
        "sintese": (
            f"Reabilitação inelegível: data de aplicação da sanção ({data_apl}) é posterior "
            f"à data de referência ({ref}). Verifique o dado informado."
        ),
        "base_legal": ["Art. 163, Par. Único, III, Lei 14.133/2021"],
        "dados_empresa": dados_empresa,
        "dados_sancao": dados_sancao,
    }


def analisar(
    tipo_sancao: str,
    dados_empresa: dict,
    dados_sancao: dict,
    respostas_condicoes: dict,
    texto_docs: str | None,
    api_key: str,
    modelo: str = _MODELO_PADRAO,
    data_referencia: date | None = None,
) -> dict:
    if tipo_sancao not in TIPOS_SANCAO:
        raise ValueError(
            f"tipo_sancao inválido: '{tipo_sancao}'. Esperado: {list(TIPOS_SANCAO)}"
        )

    # Guarda de prazo: retorna INELEGÍVEL sem chamar a IA
    _data_apl = dados_sancao.get("data_aplicacao")
    if isinstance(_data_apl, str):
        _raw = _data_apl.strip()
        _ref = data_referencia or date.today()
        try:
            _data_apl = datetime.strptime(_raw.split("T")[0][:10], "%Y-%m-%d").date()
            if _data_apl > _ref:
                return _inelegivel_data_futura(_data_apl, _ref, dados_empresa, dados_sancao)
        except ValueError:
            # tenta ISO básico sem separadores: YYYYMMDD (ex: retorno de APIs REST)
            try:
                _data_apl = datetime.strptime(_raw[:8], "%Y%m%d").date()
                if _data_apl > _ref:
                    return _inelegivel_data_futura(_data_apl, _ref, dados_empresa, dados_sancao)
            except ValueError:
                pass  # formato inválido — tenta próximo parser
            # tenta DD/MM/YYYY (formato brasileiro) — só se YYYYMMDD também falhou
            if not isinstance(_data_apl, date):
                _p = _raw.split("/")
                try:
                    if len(_p) == 3:
                        _ano = int(_p[2])
                        if _ano < 100:
                            _ano += 1900 if _ano >= 70 else 2000
                        _data_apl = date(_ano, int(_p[1]), int(_p[0]))
                        if _data_apl > _ref:
                            return _inelegivel_data_futura(_data_apl, _ref, dados_empresa, dados_sancao)
                    else:
                        _data_apl = None
                except (ValueError, TypeError, IndexError):
                    _data_apl = None
    if _data_apl is None and isinstance(dados_sancao.get("data_aplicacao"), str):
        logging.warning(
            "ia_reabilitacao: não foi possível interpretar data_aplicacao=%r — "
            "guarda de prazo ignorada, IA será consultada",
            _raw,
        )
    if isinstance(_data_apl, date):
        _prazo = calcular_prazo(tipo_sancao, _data_apl, data_referencia)
        if not _prazo["atendido"]:
            _min = _prazo["prazo_minimo_anos"]
            _a = _prazo["anos_decorridos"]
            _m = _prazo["meses_decorridos"]
            return {
                "parecer": "INELEGÍVEL",
                "condicoes_avaliadas": [{
                    "numero": "III",
                    "descricao": "Transcurso do prazo mínimo",
                    "status": "AUSENTE",
                    "observacao": (
                        f"Prazo mínimo de {_min} ano(s) não decorrido. "
                        f"Decorrido: {_a} ano(s) e {_m} mês(es)."
                    ),
                }],
                "sintese": (
                    f"Reabilitação inelegível: prazo mínimo de {_min} ano(s) previsto no "
                    "Art. 163, Par. Único, III, da Lei 14.133/2021 ainda não foi cumprido."
                ),
                "base_legal": ["Art. 163, Par. Único, III, Lei 14.133/2021"],
                "dados_empresa": dados_empresa,
                "dados_sancao":  dados_sancao,
            }

    _tipo_label    = TIPOS_SANCAO[tipo_sancao]
    # `, False` transformava NAO RESPONDIDO em "nao houve multa" — e, sem multa,
    # a condicao II do art. 163 (quitacao) simplesmente sumia da analise, EM
    # FAVOR da empresa que pede reabilitacao. Ausencia agora e ausencia.
    _multa_apl     = dados_sancao.get("multa_aplicada")
    _multa_quit    = dados_sancao.get("multa_quitada")
    _multa_valor   = dados_sancao.get("multa_valor")

    partes = [
        f"Análise de Pedido de Reabilitação — {_tipo_label}\n",
        f"Empresa: {dados_empresa.get('razao_social') or 'não informado'}",
        f"CNPJ: {dados_empresa.get('cnpj') or 'não informado'}",
        f"Órgão sancionador: {dados_sancao.get('orgao') or 'não informado'}",
        f"Data de aplicação da sanção: {dados_sancao.get('data_aplicacao') or 'não informada'}",
        "",
        "Condições do Art. 163, Par. Único, Lei 14.133/2021:",
        f"Condição I — Reparação integral do dano: {respostas_condicoes.get('reparacao') or 'não informado'}",
        f"  Descrição/comprovação: {respostas_condicoes.get('reparacao_descricao') or 'não informada'}",
        "Condição II — Multa aplicada: " + (
            "não informado" if _multa_apl is None else ("Sim" if _multa_apl else "Não")
        ),
    ]
    if _multa_apl is None:
        partes.append(
            "  ATENÇÃO: não foi informado se houve multa. NÃO presuma ausência de multa "
            "nem quitação: registre a condição II como não verificada."
        )
    elif _multa_apl:
        partes.append(
            "  Valor: " + _fmt_brl_opcional(_multa_valor, default='não informado')
        )
        partes.append("  Multa quitada: " + (
            "não informado" if _multa_quit is None else ("Sim" if _multa_quit else "Não")
        ))

    partes += [
        # So se afirma "decorrido" quando a data foi lida e conferida. Quando o
        # parser falha, a guarda acima e PULADA — e a versao anterior mandava ao
        # modelo "Decorrido (verificado automaticamente)" mesmo assim, afirmando
        # o que ninguem verificou, na condicao que e puro calculo de calendario.
        (f"Condição III — Prazo mínimo ({PRAZOS_MINIMOS_ANOS[tipo_sancao]} ano(s)): "
         "Decorrido (verificado automaticamente pelo sistema)"
         if isinstance(_data_apl, date) else
         f"Condição III — Prazo mínimo ({PRAZOS_MINIMOS_ANOS[tipo_sancao]} ano(s)): "
         "NÃO FOI POSSÍVEL VERIFICAR — a data de aplicação da sanção não foi informada ou "
         "não pôde ser interpretada. Registre esta condição como não verificada; não "
         "presuma que o prazo decorreu."),
        "Condição IV — Condições do ato punitivo:",
        f"  Descrição das condições: {dados_sancao.get('condicoes_ato_punitivo') or 'não informado'}",
        f"  Condições cumpridas: {respostas_condicoes.get('cond_ato_cumpridas') or 'não informado'}",
        f"Condição V — Análise jurídica prévia: {respostas_condicoes.get('analise_juridica') or 'não informado'}",
    ]

    if texto_docs:
        # Isolamento anti-injecao: estes documentos sao juntados pela EMPRESA
        # SANCIONADA que pede para voltar a contratar com a Administracao. Nao
        # ha parte mais interessada no resultado.
        _bloco, _aviso_corte = ia_utils.bloco_documento(
            texto_docs, rotulo="conjunto de documentos", marca="DOCS_REABILITACAO"
        )
        partes.append(f"\nDocumentos comprobatórios fornecidos:\n{_bloco}")
        if _aviso_corte:
            partes.append(_aviso_corte)
    else:
        partes.append("\nNenhum documento adicional fornecido.")

    partes.append(f"\nRetorne o parecer no formato JSON:\n{_ESTRUTURA_PARECER}")

    parecer = _chamar_api(
        "\n".join(partes), api_key, modelo,
        _SISTEMA + ia_utils.SUFIXO_SEGURANCA,
        max_tokens=8000,        # 5 condicoes + observacoes + sintese nao cabem em 3.000
    )

    parecer["_documentos_analisados"] = ia_utils.manifesto_documentos(texto_docs)
    _normalizar_parecer(parecer, NORM_PARECER_REAB,
                        frozenset(PARECER_OPTIONS) | {PARECER_NAO_AVALIADO},
                        PARECER_NAO_AVALIADO, "ia_reabilitacao")
    _derivar_parecer_das_condicoes(parecer)
    return {**parecer, "dados_empresa": dados_empresa, "dados_sancao": dados_sancao}


# Status que a IA pode atribuir a cada condicao do art. 163.
STATUS_CONDICAO_REAB = frozenset({"ATENDIDA", "PARCIAL", "AUSENTE", "N.A."})


def _derivar_parecer_das_condicoes(parecer: dict) -> None:
    """Deriva a elegibilidade DO STATUS DAS CONDICOES do art. 163.

    As condicoes do paragrafo unico do art. 163 sao CUMULATIVAS: basta uma nao
    atendida para que a reabilitacao nao possa ser deferida. Deixar a conclusao
    ao juizo livre do modelo permitia sair "ELEGIVEL" com uma condicao AUSENTE
    listada logo abaixo — mesmo defeito ja corrigido no ETP, DDI, Alteracoes e
    Recebimento.

      alguma condicao AUSENTE   -> INELEGIVEL
      alguma condicao PARCIAL   -> ELEGIVEL COM RESSALVAS
      todas ATENDIDA ou N.A.    -> ELEGIVEL
      nenhuma condicao avaliada -> NAO AVALIADO

    "N.A." e neutro de proposito: nao ha dano a reparar em toda sancao, e exigir
    reparacao onde nao houve dano seria criar requisito que a lei nao faz.
    """
    parecer.pop("_parecer_ia", None)
    conds = parecer.get("condicoes_avaliadas")
    if not isinstance(conds, list):
        conds = []
    status = [str((c or {}).get("status", "")).strip().upper()
              for c in conds if isinstance(c, dict)]
    status = [s for s in status if s in STATUS_CONDICAO_REAB]
    if not status:
        derivado = PARECER_NAO_AVALIADO
    elif "AUSENTE" in status:
        derivado = "INELEGÍVEL"
    elif "PARCIAL" in status:
        derivado = "ELEGÍVEL COM RESSALVAS"
    else:
        derivado = "ELEGÍVEL"
    if parecer.get("parecer") != derivado:
        parecer["_parecer_ia"] = parecer.get("parecer")
        parecer["parecer"] = derivado
