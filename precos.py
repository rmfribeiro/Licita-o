# -*- coding: utf-8 -*-
"""
=============================================================================
 precos.py  -  RM Lisura / RM Vertice Digital
 Tabela de precos oficial do app (Anexo de precos / Item II da parceria).
=============================================================================
 - Cada modulo pertence a um NIVEL (Simples / Medio / Alto).
 - VALOR_REFERENCIA e o preco avulso por relatorio usado na consolidacao
   de cobranca (ponto medio da faixa da tabela; ajuste aqui para calibrar).
 - PLANOS mensais dao desconto e previsibilidade.
 Fonte: Tabela_Precos_RM_Lisura.docx (documento de trabalho).
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

# PRECO POR RELATORIO (decisao do Roberto em 28/07/2026): valor unico por
# nivel, no teto das faixas que constavam da tabela enviada a Daysival em
# 09/07 (30-50 / 60-90 / 120-180). Faixa aberta gera ruido na negociacao;
# preco unico e mais simples de defender e de cobrar.
VALOR_REFERENCIA = {
    "Simples": 50.0,
    "Médio":   90.0,
    "Alto":    180.0,
}
# Mantido para exibicao/documentacao: hoje o piso e o teto coincidem.
FAIXAS = {nivel: (v, v) for nivel, v in VALOR_REFERENCIA.items()}

# Pacotes mensais. limite=None -> sem limite numerico.
PLANOS = {
    "avulso": {
        "rotulo": "Avulso",
        "mensalidade": 0.0,
        "limite": 3,             # cortesia de boas-vindas...
        "cortesia_unica": True,  # ...uma unica vez, NAO todo mes: o limite vale
                                 # sobre o total ja gerado pelo usuario. Depois
                                 # disso ele precisa contratar um plano.
    },
    # Mensalidades recalculadas em 28/07/2026, junto com a subida do avulso
    # para 50/90/180: os pacotes mantem desconto de ~35% (Basico), ~45%
    # (Profissional) e ~65% (Ilimitado) sobre o equivalente avulso. Sem isso,
    # o Basico ficaria 58% abaixo do avulso e a tabela perderia coerencia.
    "basico": {
        "rotulo": "Básico",
        "mensalidade": 1400.0,
        "limite": 20,
    },
    "profissional": {
        "rotulo": "Profissional",
        "mensalidade": 2900.0,
        "limite": 50,
    },
    "ilimitado": {
        "rotulo": "Ilimitado",
        "mensalidade": 4500.0,
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
