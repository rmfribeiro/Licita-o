from __future__ import annotations
import types
import logging
from ia_utils import chamar_api as _chamar_api
import ia_utils

_MODELO_PADRAO = "claude-haiku-4-5-20251001"
_MATURIDADE_ORDEM = ["INEXISTENTE", "INICIAL", "EM DESENVOLVIMENTO", "CONSOLIDADO"]

# Estado distinto dos quatro niveis: nao e um grau baixo de maturidade, e a
# AUSENCIA DE BASE para afirmar qualquer grau. Sem ele, formulario em branco
# virava "INEXISTENTE" — o erro do "Itau 0/100" repetido no diagnostico publico.
NAO_AVALIADO = "NÃO AVALIADO"


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
    NAO_AVALIADO:         "⚪",
    "CONSOLIDADO":        "🟢",
    "EM DESENVOLVIMENTO": "🔵",
    "INICIAL":            "🟡",
    "INEXISTENTE":        "🔴",
}

COR_MATURIDADE_HEX: types.MappingProxyType[str, str] = types.MappingProxyType({
    NAO_AVALIADO:         "#808080",
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


# Proporção de perguntas sem resposta a partir da qual o diagnóstico não pode
# concluir nada. Mesmo critério do módulo de PI de empresas.
LIMITE_SEM_RESPOSTA = 0.5


def _respondida(valor) -> bool:
    """True quando a pergunta foi efetivamente respondida.

    NÃO confundir com "respondeu Não". A distinção é a mesma do incidente de
    29/07/2026 (o "Itaú 0/100"): silêncio do usuário não é resposta negativa.
    """
    if valor is None:
        return False
    txt = str(valor).strip()
    return bool(txt) and txt.upper() not in ("NÃO INFORMADO", "NAO INFORMADO", "-", "N/A")


def _base_insuficiente(respostas: dict) -> tuple[bool, int, int]:
    """(base insuficiente?, respondidas, total).

    Regra única de "não dá para concluir nada", usada tanto pelo piso quanto
    pela neutralização do laudo — para que o selo e o texto nunca digam coisas
    diferentes.
    """
    respondidas = sum(1 for k, _ in QUESTOES_PIP if _respondida(respostas.get(k)))
    total = len(QUESTOES_PIP)
    insuficiente = respondidas == 0 or (total - respondidas) / total >= LIMITE_SEM_RESPOSTA
    return insuficiente, respondidas, total


_RESUMO_NAO_AVALIADO = (
    "Não foi possível diagnosticar a maturidade do Programa de Integridade Pública deste "
    "município: {respondidas} de {total} questões do questionário ficaram sem resposta. "
    "Este documento NÃO afirma que o município deixa de cumprir o Decreto 11.129/2022, a IN "
    "CGU 21/2021, a Lei 12.846/2013 ou o Decreto 8.420/2015 — afirma apenas que não foram "
    "apresentadas as informações necessárias para avaliar. Qualquer conclusão sobre a "
    "existência, a ausência ou o estágio do programa depende do preenchimento do "
    "questionário e da apresentação dos documentos comprobatórios."
)

_ACHADO_NAO_AVALIADO = (
    "Não avaliado — as questões correspondentes do questionário não foram respondidas e não "
    "há documento nos autos que permita verificação."
)


def _neutralizar_parecer(parecer: dict, respondidas: int, total: int) -> None:
    """Apaga do laudo toda conclusão que a IA tirou sem base.

    Descoberto no teste de 14/08/2026 com o formulário em branco: o selo saía
    NÃO AVALIADO (correto), mas o corpo do relatório continuava dizendo
    "INEXISTENTE" em todas as seis dimensões e afirmando que "não há ato formal
    de instituição, responsável designado..." — ou seja, a acusação apenas mudou
    do cabeçalho para o parágrafo, que é justamente a parte que o cliente copia.
    Sem base, o documento não conclui: nem no selo, nem no texto.
    """
    parecer["_diagnostico_ia_descartado"] = {
        "resumo_executivo": parecer.get("resumo_executivo"),
        "dimensoes": parecer.get("dimensoes"),
        "prioridades": parecer.get("prioridades"),
    }
    parecer["_motivo_nao_avaliado"] = (
        f"{total - respondidas} de {total} questões do questionário sem resposta"
    )
    parecer["resumo_executivo"] = _RESUMO_NAO_AVALIADO.format(
        respondidas=total - respondidas, total=total
    )
    parecer["dimensoes"] = {
        chave: {"nivel": NAO_AVALIADO, "achados": [_ACHADO_NAO_AVALIADO], "recomendacoes": []}
        for chave in LABEL_DIMENSAO
    }
    parecer["prioridades"] = [
        f"Responder as {total - respondidas} questões pendentes do questionário do PIP.",
        "Reunir os documentos comprobatórios (ato de instituição, designação do responsável, "
        "diretrizes publicadas, plano de gestão, indicadores).",
        "Gerar novo diagnóstico com as informações completas.",
    ]
    # A mensagem de piso ("rebaixada por critérios estruturantes ausentes") descreve
    # outra situação e confundiria o leitor aqui.
    parecer.pop("_aviso_piso_maturidade", None)


def _aplicar_piso(respostas: dict, maturidade_ia: str) -> str:
    """Aplica pisos de maturidade a partir das respostas EFETIVAS.

    A versão anterior fazia `respostas.get(k) or "Não"` — ou seja, tratava
    pergunta NÃO RESPONDIDA como resposta "Não". Com o formulário em branco,
    todas viravam "Não", a regra 1 disparava e o diagnóstico afirmava
    INEXISTENTE: exatamente o erro que corrigimos no módulo de PI, sobrevivendo
    aqui dentro do piso. O prompt pedia à IA para não presumir, mas o código
    presumia por ela.
    """
    if _base_insuficiente(respostas)[0]:
        # Base insuficiente: não se conclui maturidade nenhuma, nem para baixo.
        return NAO_AVALIADO
    respondidas = {k: str(respostas.get(k)).strip()
                   for k, _ in QUESTOES_PIP if _respondida(respostas.get(k))}

    # Regra 1 — todas as RESPONDIDAS são "Não" → INEXISTENTE
    if all(v == "Não" for v in respondidas.values()):
        return "INEXISTENTE"

    # Regra 2 — campos críticos ausentes/parciais → cap INICIAL.
    # Só se aplica quando os dois foram efetivamente respondidos.
    ato = respondidas.get(_CHAVE_ATO_FORMAL)
    resp = respondidas.get(_CHAVE_RESPONSAVEL)
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
    _sem_resposta = 0
    for chave, pergunta in QUESTOES_PIP:
        # `or` (e nao o default do .get): quando o formulario nao foi respondido
        # o valor vem como None PRESENTE no dicionario, e o default nao seria
        # aplicado — o prompt receberia a string "None".
        _r = respostas.get(chave) or "NÃO INFORMADO"
        if _r == "NÃO INFORMADO":
            _sem_resposta += 1
        partes.append(f"- {pergunta} Resposta: {_r}")
    if _sem_resposta:
        partes.append(
            f"\nATENÇÃO: {_sem_resposta} de {len(QUESTOES_PIP)} perguntas ficaram "
            "SEM RESPOSTA. Para essas, não presuma cumprimento nem "
            "descumprimento: registre como 'não informado / não avaliado' e "
            "indique que a verificação depende de informação do órgão. "
            "O nível de maturidade deve refletir apenas o que foi efetivamente "
            "informado ou comprovado por documento."
        )

    if texto_docs:
        _bloco, _aviso_corte = ia_utils.bloco_documento(
            texto_docs, rotulo="conjunto de documentos", marca="DOCS_ORGAO"
        )
        if _aviso_corte:
            partes.append(_aviso_corte)
        partes.append(f"\nDocumentos da prefeitura fornecidos:\n{_bloco}")

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
        "\n".join(partes), api_key, modelo,
        _SISTEMA + ia_utils.SUFIXO_SEGURANCA,
        max_tokens=8000,
    )

    parecer["_documentos_analisados"] = ia_utils.manifesto_documentos(texto_docs)
    parecer.pop("_aviso_maturidade", None)
    parecer.pop("_aviso_piso_maturidade", None)
    _raw_mat = parecer.get("maturidade_geral")
    # Valor ausente ou irreconhecivel NAO vira "INEXISTENTE": isso seria afirmar
    # que a prefeitura nao tem programa por causa de uma resposta malformada do
    # modelo. Vira NAO AVALIADO, e o piso decide a partir das respostas reais.
    _mat = NAO_AVALIADO if _raw_mat is None else str(_raw_mat).strip().upper()
    if _mat not in _MATURIDADE_ORDEM and _mat != NAO_AVALIADO:
        logging.warning(
            "ia_integridade: maturidade_geral inesperada da IA: %r — normalizado para NÃO AVALIADO", _mat
        )
        if _raw_mat is not None:
            parecer["_aviso_maturidade"] = _mat
        _mat = NAO_AVALIADO
    _mat_piso = _aplicar_piso(respostas, _mat)
    if _mat_piso != _mat:
        parecer["_aviso_piso_maturidade"] = _mat
    parecer["maturidade_geral"] = _mat_piso

    parecer.pop("_diagnostico_ia_descartado", None)
    parecer.pop("_motivo_nao_avaliado", None)
    _insuf, _n_resp, _n_tot = _base_insuficiente(respostas)
    if _insuf:
        _neutralizar_parecer(parecer, _n_resp, _n_tot)

    return parecer
