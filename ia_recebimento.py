from __future__ import annotations
import json
import types
import urllib.error
import urllib.request

from ia_utils import extrair_json as _extrair_json

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

STATUS_CONDICAO: types.MappingProxyType[str, str] = types.MappingProxyType({
    "ATENDIDA": "ATENDIDA",
    "PARCIAL":  "PARCIAL",
    "AUSENTE":  "AUSENTE",
})

_SISTEMA = (
    "Você é um fiscal de contratos especialista em recebimento de objetos contratuais "
    "nos termos do Art. 140 da Lei 14.133/2021. Avalie as condições de recebimento "
    "provisório e definitivo do objeto contratual com base nas informações fornecidas. "
    "Verifique cada condição legal aplicável ao tipo de objeto e emita parecer motivado. "
    "Responda SOMENTE com JSON válido no formato especificado. Não inclua texto fora do JSON."
)

_CONDICOES_POR_TIPO: dict = {
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
}

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


def _chamar_anthropic(prompt: str, api_key: str, modelo: str) -> str:
    corpo = json.dumps({
        "model": modelo,
        "max_tokens": 4000,
        "system": _SISTEMA,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=corpo,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        raw_bytes = resp.read()
    try:
        dados = json.loads(raw_bytes.decode("utf-8"))
    except ValueError as exc:
        raise RuntimeError(f"Resposta da API não é JSON válido: {exc}") from exc
    return "".join(b.get("text", "") for b in (dados.get("content") or []) if isinstance(b, dict))


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
        f"Valor do Contrato: R$ {float(dados_entrega.get('valor_contrato') or 0):.2f}",
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

    try:
        bruto = _chamar_anthropic("\n".join(partes), api_key, modelo)
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

    return {**qualitativo, "tipo_objeto": tipo_objeto, "dados_entrega": dados_entrega}
