from __future__ import annotations
import types
import urllib.error

from ia_utils import extrair_json as _extrair_json, chamar_anthropic as _chamar_anthropic

_MODELO_PADRAO = "claude-haiku-4-5-20251001"

DIMENSOES_PI: types.MappingProxyType[str, tuple[str, tuple[str, ...]]] = types.MappingProxyType({
    "comprometimento_alta_direcao": (
        "Comprometimento da Alta Direção",
        ("p1", "p2", "p3"),
    ),
    "analise_riscos": (
        "Análise de Riscos",
        ("p4", "p5"),
    ),
    "estrutura_controles": (
        "Estrutura de Controles",
        ("p6", "p7", "p8", "p9", "p10", "p11", "p12"),
    ),
    "monitoramento_melhoria": (
        "Monitoramento e Melhoria Contínua",
        ("p13", "p14", "p15"),
    ),
    "transparencia": (
        "Transparência e Comunicação",
        ("p16", "p17"),
    ),
})

QUESTOES_PI: types.MappingProxyType[str, str] = types.MappingProxyType({
    "p1":  "Política formal de integridade aprovada e publicada pela alta direção",
    "p2":  "Responsável formalmente designado com autonomia e recursos adequados",
    "p3":  "Programa incluído no planejamento estratégico e orçamento da empresa",
    "p4":  "Mapeamento e análise periódica de riscos de integridade",
    "p5":  "Procedimentos internos adaptados ao perfil de risco da empresa",
    "p6":  "Código de ética ou conduta formal",
    "p7":  "Canal de denúncias ativo, acessível, com garantia de anonimato",
    "p8":  "Política de conflito de interesses",
    "p9":  "Treinamentos periódicos de integridade para colaboradores",
    "p10": "Due diligence de terceiros (fornecedores, parceiros, agentes)",
    "p11": "Controles sobre doações, patrocínios, brindes e hospitalidade",
    "p12": "Procedimentos de integridade em interações com o setor público",
    "p13": "Auditorias internas ou externas periódicas do programa",
    "p14": "Indicadores (KPIs) de efetividade do programa",
    "p15": "Investigações internas e ações corretivas aplicadas",
    "p16": "Registros contábeis e financeiros íntegros e auditáveis",
    "p17": "Relatório periódico do programa publicado ou disponível para consulta",
})

HIPOTESES: types.MappingProxyType[str, str] = types.MappingProxyType({
    "grande_vulto": "Grande Vulto (Decreto 12.304/2024, Art. 4º)",
    "desempate":    "Desempate por PI (Lei 14.133/2021, Art. 60, IV)",
    "reabilitacao": "Reabilitação de Fornecedor (Lei 14.133/2021, Art. 163, Par. Único)",
})

PESOS_DIMENSAO: types.MappingProxyType[str, float] = types.MappingProxyType({
    "comprometimento_alta_direcao": 0.20,
    "analise_riscos":               0.15,
    "estrutura_controles":          0.35,
    "monitoramento_melhoria":       0.20,
    "transparencia":                0.10,
})

_VALORES_RESPOSTA: types.MappingProxyType[str, int] = types.MappingProxyType({
    "Não existe":   0,
    "Parcialmente": 50,
    "Implementado": 100,
})

_TEXTO_POR_VALOR: types.MappingProxyType[int, str] = types.MappingProxyType({
    0:   "Não existe",
    50:  "Parcialmente",
    100: "Implementado",
})

# Level names match ia_integridade._MATURIDADE_ORDEM — update both if levels change.
_MATURIDADE_FAIXAS: tuple[tuple[float, str], ...] = (
    (75.0, "CONSOLIDADO"),
    (50.0, "EM DESENVOLVIMENTO"),
    (25.0, "INICIAL"),
    (0.0,  "INEXISTENTE"),
)

if set(PESOS_DIMENSAO) != set(DIMENSOES_PI):
    _missing = set(DIMENSOES_PI) - set(PESOS_DIMENSAO)
    raise RuntimeError(f"PESOS_DIMENSAO não cobre todas as dimensões de DIMENSOES_PI: {_missing}")


def nivel_maturidade(score: float) -> str:
    for limite, nivel in _MATURIDADE_FAIXAS:
        if score >= limite:
            return nivel
    return "INEXISTENTE"


def calcular_scores(respostas: dict) -> dict:
    por_parametro: dict[str, int] = {}
    for p in QUESTOES_PI:
        resp = str(respostas.get(p) or "Não existe")
        por_parametro[p] = _VALORES_RESPOSTA.get(resp, 0)

    por_dimensao: dict[str, float] = {}
    for dim_key, (_, params) in DIMENSOES_PI.items():
        scores_dim = [por_parametro[p] for p in params]
        por_dimensao[dim_key] = sum(scores_dim) / len(scores_dim)

    geral = sum(por_dimensao[d] * PESOS_DIMENSAO[d] for d in por_dimensao)
    geral = round(geral, 1)

    return {
        "por_parametro": por_parametro,
        "por_dimensao":  por_dimensao,
        "geral":         geral,
        "nivel":         nivel_maturidade(geral),
    }


_SISTEMA = (
    "Você é um consultor sênior especialista em Programas de Integridade para empresas "
    "privadas e organismos que contratam com a Administração Pública brasileira. "
    "Avalie o Programa de Integridade da empresa com base nas respostas do questionário "
    "e nos documentos fornecidos, à luz do Decreto 12.304/2024, da Lei 12.846/2013 "
    "(art. 7º, IV) e da Lei 14.133/2021. "
    "Responda SOMENTE com JSON válido no formato especificado. Não inclua texto fora do JSON."
)

_ESTRUTURA_PARECER = """{
  "dimensoes": {
    "comprometimento_alta_direcao": {
      "sintese": "...",
      "parametros": {
        "p1": {"achados": ["..."], "recomendacoes": ["..."]},
        "p2": {"achados": [], "recomendacoes": []},
        "p3": {"achados": [], "recomendacoes": []}
      }
    },
    "analise_riscos": {
      "sintese": "...",
      "parametros": {
        "p4": {"achados": [], "recomendacoes": []},
        "p5": {"achados": [], "recomendacoes": []}
      }
    },
    "estrutura_controles": {
      "sintese": "...",
      "parametros": {
        "p6":  {"achados": [], "recomendacoes": []},
        "p7":  {"achados": [], "recomendacoes": []},
        "p8":  {"achados": [], "recomendacoes": []},
        "p9":  {"achados": [], "recomendacoes": []},
        "p10": {"achados": [], "recomendacoes": []},
        "p11": {"achados": [], "recomendacoes": []},
        "p12": {"achados": [], "recomendacoes": []}
      }
    },
    "monitoramento_melhoria": {
      "sintese": "...",
      "parametros": {
        "p13": {"achados": [], "recomendacoes": []},
        "p14": {"achados": [], "recomendacoes": []},
        "p15": {"achados": [], "recomendacoes": []}
      }
    },
    "transparencia": {
      "sintese": "...",
      "parametros": {
        "p16": {"achados": [], "recomendacoes": []},
        "p17": {"achados": [], "recomendacoes": []}
      }
    }
  },
  "pontos_criticos": ["..."],
  "conclusao_hipotese": "Texto específico para a hipótese.",
  "recomendacoes": ["..."],
  "base_legal": ["Decreto 12.304/2024, Art. 4º", "Lei 14.133/2021, Art. 60, IV"]
}"""


def avaliar(
    respostas: dict,
    hipotese: str,
    texto_docs: str | None,
    api_key: str,
    modelo: str = _MODELO_PADRAO,
) -> dict:
    scores = calcular_scores(respostas)

    partes = [
        f"Avaliação do Programa de Integridade — Hipótese: {HIPOTESES.get(hipotese, hipotese)}\n"
        f"Score geral calculado: {scores['geral']}/100 ({scores['nivel']})\n"
    ]
    for dim_key, (dim_label, params) in DIMENSOES_PI.items():
        partes.append(
            f"\n=== {dim_label} (score: {scores['por_dimensao'][dim_key]:.0f}/100) ==="
        )
        for p in params:
            valor = scores["por_parametro"][p]
            resp_txt = _TEXTO_POR_VALOR.get(valor, str(valor))
            partes.append(f"- {QUESTOES_PI[p]} → {resp_txt} ({valor}/100)")

    if texto_docs:
        partes.append(f"\nDocumentos fornecidos pela empresa:\n{texto_docs[:30000]}")

    partes.append(f"\nRetorne a análise qualitativa no formato:\n{_ESTRUTURA_PARECER}")

    try:
        bruto = _chamar_anthropic("\n".join(partes), api_key, modelo, _SISTEMA)
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
            f"Resposta inesperada da API: objeto JSON esperado, recebeu {type(qualitativo).__name__}"
        )

    return {
        **qualitativo,
        "scores":   scores,
        "hipotese": hipotese,
    }
