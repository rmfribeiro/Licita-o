from __future__ import annotations
import types
import ia_utils
from ia_utils import (
    chamar_api as _chamar_api,
    fmt_brl_opcional as _fmt_brl_opcional,
    normalizar_parecer as _normalizar_parecer,
)

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

# Normalização canônica de aliases de parecer — importável por app.py e relatorio_contratos.py
NORM_PARECER_CONT: types.MappingProxyType[str, str] = types.MappingProxyType({
    "DEFERIVEL":               "DEFERÍVEL",
    "DEFERIVEL COM RESSALVAS": "DEFERÍVEL COM RESSALVAS",
    "DEFERIVEL COM RESSALVA":  "DEFERÍVEL COM RESSALVAS",
    "DEFERÍVEL COM RESSALVA":  "DEFERÍVEL COM RESSALVAS",
    "INDEFERIVEL":             "INDEFERÍVEL",
})

_SISTEMA_POR_TIPO: types.MappingProxyType[str, str] = types.MappingProxyType({
    "reajuste": (
        "Você é um consultor jurídico especialista em contratos administrativos brasileiros. "
        "Analise pedidos de REAJUSTE contratual à luz do Art. 25 §8º da Lei 14.133/2021. "
        "Verifique se há cláusula expressa de reajuste com índice e data-base, se o intervalo "
        "mínimo de 12 meses foi respeitado e se a memória de cálculo está correta. "
        "Para cada requisito legal listado, atribua status ATENDIDO, PARCIAL ou AUSENTE, "
        "com observação objetiva de no máximo 2 frases citando o documento que comprova "
        "(ou a lacuna). Use AUSENTE quando o requisito não foi comprovado por documento. "
        "Não emita juízo sobre o parecer conclusivo: ele é calculado a partir dos status "
        "que você atribuir aos requisitos. "
        "Responda SOMENTE com JSON válido no formato especificado. Não inclua texto fora do JSON."
    ),
    "repactuacao": (
        "Você é um consultor jurídico especialista em contratos administrativos brasileiros. "
        "Analise pedidos de REPACTUAÇÃO contratual à luz do Art. 25 §8º da Lei 14.133/2021 e "
        "IN SEGES 5/2017. Verifique se o contrato é de serviços com mão de obra dedicada, se há "
        "CCT ou ACT, planilha de custos atualizada, prazo de preclusão e comprovação dos novos custos. "
        "Para cada requisito legal listado, atribua status ATENDIDO, PARCIAL ou AUSENTE, "
        "com observação objetiva de no máximo 2 frases citando o documento que comprova "
        "(ou a lacuna). Use AUSENTE quando o requisito não foi comprovado por documento. "
        "Não emita juízo sobre o parecer conclusivo: ele é calculado a partir dos status "
        "que você atribuir aos requisitos. "
        "Responda SOMENTE com JSON válido no formato especificado. Não inclua texto fora do JSON."
    ),
    "reequilibrio": (
        "Você é um consultor jurídico especialista em contratos administrativos brasileiros. "
        "Analise pedidos de REEQUILÍBRIO ECONÔMICO-FINANCEIRO à luz do Art. 124 II 'd' da "
        "Lei 14.133/2021 e Art. 37 XXI da CF/88. Verifique se o evento é imprevisível e "
        "extraordinário, se há nexo causal comprovado e documentação suficiente do impacto. "
        "Para cada requisito legal listado, atribua status ATENDIDO, PARCIAL ou AUSENTE, "
        "com observação objetiva de no máximo 2 frases citando o documento que comprova "
        "(ou a lacuna). Use AUSENTE quando o requisito não foi comprovado por documento. "
        "Não emita juízo sobre o parecer conclusivo: ele é calculado a partir dos status "
        "que você atribuir aos requisitos. "
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
        "Valor Atual: " + _fmt_brl_opcional(dados_contrato.get('valor_atual'), default='não informado'),
        f"\nRequisitos legais a verificar para {TIPOS_ALTERACAO[tipo]}:",
    ]
    for i, req in enumerate(REQUISITOS_POR_TIPO[tipo], 1):
        partes.append(f"{i}. {req}")

    if texto_docs:
        # Documento do gestor vai ISOLADO em bloco delimitado (anti-injecao) e
        # com nonce derivado do conteudo (prompt deterministico).
        _bloco, _aviso_corte = ia_utils.bloco_documento(
            texto_docs, rotulo="conjunto de documentos", marca="DOCS"
        )
        if _aviso_corte:
            partes.append(_aviso_corte)
        partes.append(f"\nDocumentos fornecidos pelo gestor:\n{_bloco}")
    else:
        partes.append(
            "\nNenhum documento adicional fornecido. Analise com base nas informações "
            "acima e sinalize as lacunas documentais que impedem a análise completa."
        )

    partes.append(
        f"\nRetorne a análise no formato JSON:\n{_ESTRUTURA_PARECER}"
    )

    qualitativo = _chamar_api(
        "\n".join(partes), api_key, modelo,
        _SISTEMA_POR_TIPO[tipo] + ia_utils.SUFIXO_SEGURANCA,
        max_tokens=8000,
    )

    _normalizar_parecer(qualitativo, NORM_PARECER_CONT, PARECER_OPTIONS, "INDEFERÍVEL", "ia_contratos")
    _derivar_parecer_dos_requisitos(qualitativo)
    return {**qualitativo, "tipo_alteracao": tipo, "dados_contrato": dados_contrato}


def _derivar_parecer_dos_requisitos(parecer: dict) -> None:
    """Deriva a conclusão DO STATUS DOS REQUISITOS verificados.

    Mesma correção aplicada ao ETP e ao DDI em 13/08/2026: a conclusão não pode
    ser juízo livre do modelo, senão o mesmo pedido de reajuste sai "DEFERÍVEL"
    numa execução e "INDEFERÍVEL" na outra. Aqui a escala é a dos requisitos
    legais do tipo de alteração:

      algum requisito AUSENTE  -> INDEFERÍVEL
      algum requisito PARCIAL  -> DEFERÍVEL COM RESSALVAS
      todos ATENDIDOS          -> DEFERÍVEL

    É a regra que o próprio jurista aplicaria: falta requisito legal, não se
    defere. O que a IA havia concluído fica guardado em `_parecer_ia`.
    """
    parecer.pop("_parecer_ia", None)
    reqs = parecer.get("requisitos")
    if not isinstance(reqs, list) or not reqs:
        return
    status = [str((r or {}).get("status", "")).strip().upper()
              for r in reqs if isinstance(r, dict)]
    status = [s for s in status if s]
    if not status:
        return
    if "AUSENTE" in status:
        derivado = "INDEFERÍVEL"
    elif "PARCIAL" in status:
        derivado = "DEFERÍVEL COM RESSALVAS"
    else:
        derivado = "DEFERÍVEL"
    if parecer.get("parecer") != derivado:
        parecer["_parecer_ia"] = parecer.get("parecer")
        parecer["parecer"] = derivado
