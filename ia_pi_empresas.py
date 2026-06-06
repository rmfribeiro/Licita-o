from __future__ import annotations
import json
import types
import urllib.request
import urllib.error
import logging
from ia_utils import extrair_json as _extrair_json

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

_MATURIDADE_FAIXAS: tuple[tuple[float, str], ...] = (
    (75.0, "CONSOLIDADO"),
    (50.0, "EM DESENVOLVIMENTO"),
    (25.0, "INICIAL"),
    (0.0,  "INEXISTENTE"),
)


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
