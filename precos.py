# -*- coding: utf-8 -*-
"""
=============================================================================
 precos.py  -  RM IA-Licita / RM Vertice Digital
 Tabela de precos oficial do app (Anexo de precos / Item II da parceria).
=============================================================================
 - Cada modulo pertence a um NIVEL (Simples / Medio / Alto).
 - VALOR_REFERENCIA e o preco avulso por relatorio usado na consolidacao
   de cobranca (ponto medio da faixa da tabela; ajuste aqui para calibrar).
 - PLANOS mensais dao desconto e previsibilidade.
 Fonte: Tabela_Precos_RM_IA-Licita.docx (documento de trabalho).
=============================================================================
"""

# Modulo -> nivel  (nomes exatamente como registrados no uso)
NIVEIS = {
    # Simples — R$ 30 a 50
    "Recebimento":                "Simples",
    "Reabilitação de Fornecedor": "Simples",
    "Instituto da Diligência":    "Simples",
    "DDI":                        "Simples",
    # Médio — R$ 60 a 90
    "Auditoria de Edital":        "Médio",
    "Auditoria de TR":            "Médio",
    "Auditoria de ETP":           "Médio",
    "Alterações Contratuais":     "Médio",
    "Avaliação de PI":            "Médio",
    # Alto — R$ 120 a 180
    "Dosimetria de Sanções":      "Alto",
    "Pesquisa de Mercado":        "Alto",
    "Diagnóstico de Integridade": "Alto",
}

# Faixas da tabela (documentacao) e valor de referencia usado na cobranca
FAIXAS = {
    "Simples": (30.0, 50.0),
    "Médio":   (60.0, 90.0),
    "Alto":    (120.0, 180.0),
}
VALOR_REFERENCIA = {
    "Simples": 40.0,
    "Médio":   75.0,
    "Alto":    150.0,
}

# Pacotes mensais. limite=None -> sem limite numerico.
PLANOS = {
    "avulso": {
        "rotulo": "Avulso",
        "mensalidade": 0.0,
        "limite": None,          # paga por relatorio
    },
    "basico": {
        "rotulo": "Básico",
        "mensalidade": 900.0,
        "limite": 20,
    },
    "profissional": {
        "rotulo": "Profissional",
        "mensalidade": 1900.0,
        "limite": 50,
    },
    "ilimitado": {
        "rotulo": "Ilimitado",
        "mensalidade": 3500.0,
        "limite": None,
        "uso_justo": 120,        # referencia p/ conversa de reenquadramento
    },
}


def nivel_do_modulo(modulo: str) -> str:
    return NIVEIS.get(modulo, "Médio")


def valor_do_modulo(modulo: str) -> float:
    return VALOR_REFERENCIA[nivel_do_modulo(modulo)]


def plano_info(plano: str) -> dict:
    return PLANOS.get(plano or "avulso", PLANOS["avulso"])
