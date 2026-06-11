from __future__ import annotations
import types
from ia_utils import chamar_api as _chamar_api, fmt_brl_opcional as _fmt_brl_opcional

_MODELO_PADRAO = "claude-haiku-4-5-20251001"

TIPOS_OBJETO: types.MappingProxyType[str, str] = types.MappingProxyType({
    "servico": "Serviço",
    "bem":     "Fornecimento de Bem",
    "obra":    "Obra",
})

PARECER_OPTIONS: types.MappingProxyType[str, str] = types.MappingProxyType({
    "APTO":               "APTO",
    "APTO COM RESSALVAS": "APTO COM RESSALVAS",
    "INAPTO":             "INAPTO",
})

# Normalização canônica de aliases de parecer — importável por app.py e relatorio_recebimento.py
NORM_PARECER_RECV: types.MappingProxyType[str, str] = types.MappingProxyType({
    "APTO COM RESSALVA":    "APTO COM RESSALVAS",
    "APTO C/ RESSALVAS":    "APTO COM RESSALVAS",
    "APTO C/ RESSALVA":     "APTO COM RESSALVAS",
    "APTO COM RESERVAS":    "APTO COM RESSALVAS",
    "PARCIALMENTE APTO":    "APTO COM RESSALVAS",
    "APTO PARCIALMENTE":    "APTO COM RESSALVAS",
})

STATUS_CONDICAO: types.MappingProxyType[str, str] = types.MappingProxyType({
    "ATENDIDA": "ATENDIDA",
    "PARCIAL":  "PARCIAL",
    "AUSENTE":  "AUSENTE",
})

_SISTEMA_POR_TIPO: types.MappingProxyType[str, str] = types.MappingProxyType({
    "servico": (
        "Você é um fiscal de contratos especialista em recebimento de SERVIÇOS "
        "nos termos do Art. 140 da Lei 14.133/2021. Avalie as condições de recebimento "
        "provisório e definitivo do serviço contratado com base nas informações fornecidas. "
        "Verifique conformidade com o Termo de Referência, regularidade fiscal e trabalhista, "
        "medição elaborada e prazo contratual. Emita parecer motivado. "
        "Responda SOMENTE com JSON válido no formato especificado. Não inclua texto fora do JSON."
    ),
    "bem": (
        "Você é um fiscal de contratos especialista em recebimento de BENS/MATERIAIS "
        "nos termos do Art. 140 da Lei 14.133/2021. Avalie as condições de recebimento "
        "provisório e definitivo do bem fornecido com base nas informações fornecidas. "
        "Verifique quantidade, qualidade aparente, nota fiscal, laudo técnico de inspeção "
        "e conformidade com especificações do TR. Emita parecer motivado. "
        "Responda SOMENTE com JSON válido no formato especificado. Não inclua texto fora do JSON."
    ),
    "obra": (
        "Você é um fiscal de obras especialista em recebimento de OBRAS PÚBLICAS "
        "nos termos do Art. 140 da Lei 14.133/2021, com conhecimento em engenharia civil "
        "e legislação de responsabilidade técnica (CREA/CAU). Avalie as condições de recebimento "
        "provisório e definitivo da obra com base nas informações fornecidas. "
        "Verifique ART/RRT de conclusão, conformidade com projeto executivo, medição final, "
        "as-built, ausência de vícios aparentes e período de observação. Emita parecer motivado. "
        "Responda SOMENTE com JSON válido no formato especificado. Não inclua texto fora do JSON."
    ),
})

_CONDICOES_POR_TIPO: types.MappingProxyType = types.MappingProxyType({
    "servico": {
        "provisorio": [
            "Serviço prestado conforme especificações do Termo de Referência",
            "Medição elaborada pelo fiscal do contrato",
            "Prazo contratual de execução respeitado",
            "Documentação fiscal (NF/fatura) apresentada",
        ],
        "definitivo": [
            "Qualidade do serviço confirmada após período de verificação",
            "Pendências do recebimento provisório sanadas",
            "Autoridade competente habilitada para emitir o ateste final",
        ],
    },
    "bem": {
        "provisorio": [
            "Quantidade conferida conforme ordem de fornecimento",
            "Qualidade aparente sem avarias visíveis",
            "Nota fiscal e documentos de entrega presentes",
            "Entrega realizada no local e prazo contratados",
        ],
        "definitivo": [
            "Inspeção técnica concluída com laudo",
            "Conformidade com especificações do TR confirmada",
            "Garantia do fabricante registrada (se aplicável)",
        ],
    },
    "obra": {
        "provisorio": [
            "Obra concluída fisicamente conforme projeto",
            "ART/RRT de conclusão anotada pelo responsável técnico",
            "Medição final elaborada pela fiscalização",
            "Vistoria realizada pela comissão de recebimento",
        ],
        "definitivo": [
            "Período de observação decorrido sem defeitos aparentes",
            "Ausência de vícios ocultos identificados",
            "As-built entregue pelo contratado",
            "Responsabilidade técnica do contratado formalmente encerrada",
        ],
    },
})

_ESTRUTURA_PARECER = """{
  "tipo_objeto": "servico|bem|obra",
  "recebimento_provisorio": {
    "parecer": "APTO|APTO COM RESSALVAS|INAPTO",
    "condicoes": [
      {"descricao": "...", "status": "ATENDIDA|PARCIAL|AUSENTE", "observacao": "..."}
    ],
    "pendencias": ["..."],
    "sintese": "..."
  },
  "recebimento_definitivo": {
    "parecer": "APTO|APTO COM RESSALVAS|INAPTO",
    "condicoes": [
      {"descricao": "...", "status": "ATENDIDA|PARCIAL|AUSENTE", "observacao": "..."}
    ],
    "pendencias": ["..."],
    "sintese": "..."
  },
  "recomendacoes_gerais": ["..."],
  "base_legal": ["Art. 140, I, Lei 14.133/2021"]
}"""


def analisar(
    tipo_objeto: str,
    dados_entrega: dict,
    texto_docs: str | None,
    api_key: str,
    modelo: str = _MODELO_PADRAO,
) -> dict:
    if tipo_objeto not in TIPOS_OBJETO:
        raise ValueError(
            f"Tipo de objeto inválido: '{tipo_objeto}'. Esperado: {list(TIPOS_OBJETO)}"
        )

    conds = _CONDICOES_POR_TIPO[tipo_objeto]
    partes = [
        f"Análise de Recebimento Contratual — {TIPOS_OBJETO[tipo_objeto]}\n",
        f"Número do Contrato: {dados_entrega.get('numero_contrato') or 'não informado'}",
        f"Objeto: {dados_entrega.get('objeto') or 'não informado'}",
        f"Data de Entrega/Conclusão: {dados_entrega.get('data_entrega') or 'não informada'}",
        "Valor do Contrato: " + _fmt_brl_opcional(dados_entrega.get('valor_contrato'), default='não informado'),
        f"Descrição do que foi entregue/executado:\n{dados_entrega.get('descricao_entrega') or 'não informado'}",
    ]
    nao_conf = dados_entrega.get("nao_conformidades")
    if nao_conf:
        partes.append(f"\nNão conformidades/pendências identificadas:\n{nao_conf}")

    partes.append("\nCondições de Recebimento Provisório a verificar (Art. 140, I):")
    for i, c in enumerate(conds["provisorio"], 1):
        partes.append(f"{i}. {c}")

    partes.append("\nCondições de Recebimento Definitivo a verificar (Art. 140, II):")
    for i, c in enumerate(conds["definitivo"], 1):
        partes.append(f"{i}. {c}")

    if texto_docs:
        partes.append(f"\nDocumentos fornecidos:\n{texto_docs[:30000]}")
    else:
        partes.append(
            "\nNenhum documento adicional fornecido. Analise com base nas informações "
            "acima e sinalize as condições não verificáveis pela falta de documentação."
        )

    partes.append(f"\nRetorne a análise no formato JSON:\n{_ESTRUTURA_PARECER}")

    qualitativo = _chamar_api(
        "\n".join(partes), api_key, modelo, _SISTEMA_POR_TIPO[tipo_objeto]
    )

    for _bk in ("recebimento_provisorio", "recebimento_definitivo"):
        _b = qualitativo.get(_bk)
        if isinstance(_b, dict):
            _p = str(_b.get("parecer") or "INAPTO").strip().upper()
            _pnorm = NORM_PARECER_RECV.get(_p, _p)
            _b["parecer"] = _pnorm if _pnorm in PARECER_OPTIONS else "INAPTO"
    return {**qualitativo, "tipo_objeto": tipo_objeto, "dados_entrega": dados_entrega}
