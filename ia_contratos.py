from __future__ import annotations
import types
import urllib.error

from ia_utils import extrair_json as _extrair_json, chamar_anthropic as _chamar_anthropic, safe_float as _safe_float

_MODELO_PADRAO = "claude-haiku-4-5-20251001"

TIPOS_ALTERACAO: types.MappingProxyType[str, str] = types.MappingProxyType({
    "reajuste":     "Reajuste (Art. 25 §8º, Lei 14.133/2021)",
    "repactuacao":  "Repactuação (Art. 25 §8º + IN SEGES 5/2017)",
    "reequilibrio": "Reequilíbrio Econômico-Financeiro (Art. 124 II 'd' + Art. 37 XXI CF/88)",
})

REQUISITOS_POR_TIPO: types.MappingProxyType[str, tuple[str, ...]] = types.MappingProxyType({
    "reajuste": (
        "Cláusula expressa no contrato com índice de reajuste e data-base definidos",
        "Intervalo mínimo de 12 meses contado da data-base contratual",
        "Cálculo elaborado conforme índice previsto (IPCA, INPC, IGP-M etc.)",
        "Memória de cálculo detalhada apresentada pela contratada",
    ),
    "repactuacao": (
        "Contrato é de serviços com dedicação exclusiva de mão de obra",
        "Convenção Coletiva de Trabalho (CCT) ou ACT vigente apresentada",
        "Planilha de Custos e Formação de Preços atualizada com nova CCT",
        "Intervalo mínimo de 12 meses da data-base (data da proposta ou última repactuação)",
        "Solicitação dentro do prazo de preclusão contratual",
        "Comprovação objetiva da variação nos custos trabalhistas",
    ),
    "reequilibrio": (
        "Evento identificado é imprevisível e extraordinário (não álea ordinária de mercado)",
        "Nexo causal entre o evento e o desequilíbrio econômico-financeiro demonstrado",
        "Comprovação documental do impacto financeiro (notas, cotações, laudos)",
        "Memória de cálculo fundamentada com valores precisos antes e após o evento",
        "Equação econômico-financeira original identificada no contrato ou proposta",
    ),
})

STATUS_REQUISITO: types.MappingProxyType[str, str] = types.MappingProxyType({
    "ATENDIDO": "ATENDIDO",
    "PARCIAL":  "PARCIAL",
    "AUSENTE":  "AUSENTE",
})

PARECER_OPTIONS: types.MappingProxyType[str, str] = types.MappingProxyType({
    "DEFERÍVEL":               "DEFERÍVEL",
    "DEFERÍVEL COM RESSALVAS": "DEFERÍVEL COM RESSALVAS",
    "INDEFERÍVEL":             "INDEFERÍVEL",
})

_SISTEMA_POR_TIPO: types.MappingProxyType[str, str] = types.MappingProxyType({
    "reajuste": (
        "Você é um consultor jurídico especialista em contratos administrativos brasileiros. "
        "Analise pedidos de REAJUSTE contratual à luz do Art. 25 §8º da Lei 14.133/2021. "
        "Verifique se há cláusula expressa de reajuste com índice e data-base, se o intervalo "
        "mínimo de 12 meses foi respeitado e se a memória de cálculo está correta. "
        "Responda SOMENTE com JSON válido no formato especificado. Não inclua texto fora do JSON."
    ),
    "repactuacao": (
        "Você é um consultor jurídico especialista em contratos administrativos brasileiros. "
        "Analise pedidos de REPACTUAÇÃO contratual à luz do Art. 25 §8º da Lei 14.133/2021 e "
        "IN SEGES 5/2017. Verifique se o contrato é de serviços com mão de obra dedicada, se há "
        "CCT ou ACT, planilha de custos atualizada, prazo de preclusão e comprovação dos novos custos. "
        "Responda SOMENTE com JSON válido no formato especificado. Não inclua texto fora do JSON."
    ),
    "reequilibrio": (
        "Você é um consultor jurídico especialista em contratos administrativos brasileiros. "
        "Analise pedidos de REEQUILÍBRIO ECONÔMICO-FINANCEIRO à luz do Art. 124 II 'd' da "
        "Lei 14.133/2021 e Art. 37 XXI da CF/88. Verifique se o evento é imprevisível e "
        "extraordinário, se há nexo causal comprovado e documentação suficiente do impacto. "
        "Responda SOMENTE com JSON válido no formato especificado. Não inclua texto fora do JSON."
    ),
})

_ESTRUTURA_PARECER = """{
  "parecer": "DEFERÍVEL|DEFERÍVEL COM RESSALVAS|INDEFERÍVEL",
  "tipo_alteracao": "reajuste|repactuacao|reequilibrio",
  "requisitos": [
    {
      "descricao": "Descrição do requisito verificado",
      "status": "ATENDIDO|PARCIAL|AUSENTE",
      "observacao": "Observação explicativa (pode ser vazio)"
    }
  ],
  "lacunas_documentais": ["Documento X não localizado ou insuficiente"],
  "fundamentos_legais": ["Art. 25 §8º, Lei 14.133/2021"],
  "recomendacoes": ["Próxima ação recomendada ao gestor público"],
  "sintese": "Parágrafo explicando o parecer conclusivo e seus principais fundamentos."
}"""


def analisar(
    tipo: str,
    dados_contrato: dict,
    texto_docs: str | None,
    api_key: str,
    modelo: str = _MODELO_PADRAO,
) -> dict:
    if tipo not in TIPOS_ALTERACAO:
        raise ValueError(
            f"Tipo de alteração inválido: '{tipo}'. Esperado: {list(TIPOS_ALTERACAO)}"
        )

    partes = [
        f"Análise de Pedido de Alteração Contratual — {TIPOS_ALTERACAO[tipo]}\n",
        f"Número do Contrato: {dados_contrato.get('numero_contrato') or 'não informado'}",
        f"Objeto: {dados_contrato.get('objeto') or 'não informado'}",
        f"Data de Assinatura: {dados_contrato.get('data_assinatura') or 'não informada'}",
        f"Valor Atual: R$ {_safe_float(dados_contrato.get('valor_atual')):.2f}",
        f"\nRequisitos legais a verificar para {TIPOS_ALTERACAO[tipo]}:",
    ]
    for i, req in enumerate(REQUISITOS_POR_TIPO[tipo], 1):
        partes.append(f"{i}. {req}")

    if texto_docs:
        partes.append(
            f"\nDocumentos fornecidos pelo gestor:\n{texto_docs[:30000]}"
        )
    else:
        partes.append(
            "\nNenhum documento adicional fornecido. Analise com base nas informações "
            "acima e sinalize as lacunas documentais que impedem a análise completa."
        )

    partes.append(
        f"\nRetorne a análise no formato JSON:\n{_ESTRUTURA_PARECER}"
    )

    try:
        bruto = _chamar_anthropic(
            "\n".join(partes), api_key, modelo, _SISTEMA_POR_TIPO[tipo]
        )
    except urllib.error.HTTPError as exc:
        _body = ""
        try:
            _body = exc.read().decode("utf-8", errors="replace")
        except (OSError, IOError):
            pass
        raise RuntimeError(
            f"Falha na API Anthropic: HTTP {exc.code} {exc.reason} — {_body}"
        ) from exc
    except (urllib.error.URLError, OSError) as exc:
        raise RuntimeError(f"Falha na API Anthropic: {exc}") from exc

    try:
        qualitativo = _extrair_json(bruto)
    except ValueError as exc:
        raise RuntimeError(f"Resposta da API não contém JSON válido: {exc}") from exc

    if not isinstance(qualitativo, dict):
        raise RuntimeError(
            f"Resposta inesperada da API: objeto JSON esperado, "
            f"recebeu {type(qualitativo).__name__}"
        )

    _pval = str(qualitativo.get("parecer") or "INDEFERÍVEL").strip().upper()
    qualitativo["parecer"] = {
        "DEFERIVEL":               "DEFERÍVEL",
        "DEFERIVEL COM RESSALVAS": "DEFERÍVEL COM RESSALVAS",
        "DEFERIVEL COM RESSALVA":  "DEFERÍVEL COM RESSALVAS",
        "DEFERÍVEL COM RESSALVA":  "DEFERÍVEL COM RESSALVAS",
        "INDEFERIVEL":             "INDEFERÍVEL",
    }.get(_pval, _pval)
    return {**qualitativo, "tipo_alteracao": tipo, "dados_contrato": dados_contrato}
