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

# -----------------------------------------------------------------------------
# TETO COMERCIAL — por que os precos param onde param
# -----------------------------------------------------------------------------
# Contratacao direta por dispensa (Lei 14.133/2021, art. 75, II) vale ate
# R$ 65.492,11 no exercicio de 2026 (Decreto 12.807/2025, IPCA-E de 4,41%).
# Acima disso a prefeitura precisa LICITAR para contratar o RM Lisura — meses de
# espera, concorrencia e edital. Por isso o plano mais caro fica com folga
# abaixo desse teto (e o limite e reajustado todo ano; conferir em janeiro).
LIMITE_DISPENSA_ANUAL = 65_492.11   # art. 75, II — exercicio 2026

# PRECO POR RELATORIO (revisao de 30/07/2026, apos conversa com o Daysival):
# os valores anteriores (50/90/180) eram baixos para o setor publico, onde
# preco irrisorio sinaliza ferramenta amadora e nao cobre pedidos fora do
# escopo. Referencia de valor: um edital anulado custa meses ao orgao e pode
# responsabilizar o gestor — a auditoria que evita isso nao pode custar menos
# que uma refeicao.
VALOR_REFERENCIA = {
    "Simples": 90.0,
    "Médio":   190.0,
    "Alto":    380.0,
}
# Mantido para exibicao/documentacao: hoje o piso e o teto coincidem.
FAIXAS = {nivel: (v, v) for nivel, v in VALOR_REFERENCIA.items()}

# -----------------------------------------------------------------------------
# SERVICOS FORA DO ESCOPO DO APP (nao entram na cobranca automatica)
# -----------------------------------------------------------------------------
# Existem para resolver o problema real levantado pelo Daysival: cliente que
# pede "so mais uma coisinha". Sem preco definido, o trabalho extra sai de
# graca — subir a mensalidade sozinha nao resolveria isso.
SERVICOS_EXTRAS = {
    "implantacao_pi": {
        "rotulo": "Implantação de Programa de Integridade",
        "faixa": (1500.0, 3500.0),
        "unidade": "por plano",
    },
    "relatorio_customizado": {
        "rotulo": "Relatório customizado / análise não prevista",
        "faixa": (400.0, 400.0),
        "unidade": "por hora",
    },
    "treinamento": {
        "rotulo": "Treinamento da equipe do órgão",
        "faixa": (1200.0, 1200.0),
        "unidade": "por sessão",
    },
    "parecer_juridico": {
        "rotulo": "Parecer jurídico sobre caso concreto",
        "faixa": (None, None),
        "unidade": "tabela do parceiro jurídico (serviço dele, não do app)",
    },
}

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
    # Mensalidades revistas em 30/07/2026 junto com o avulso (90/190/380).
    # O Ilimitado e o que amarra a tabela: R$ 4.990 x 12 = R$ 59.880/ano, ou
    # seja, ~R$ 5,6 mil ABAIXO do limite de dispensa de 2026. Essa folga
    # protege contra o reajuste anual do limite e contra a soma de outras
    # contratacoes do mesmo objeto no exercicio (vedacao de fracionamento).
    "basico": {
        "rotulo": "Básico",
        "mensalidade": 2500.0,
        "limite": 20,
    },
    "profissional": {
        "rotulo": "Profissional",
        "mensalidade": 3900.0,
        "limite": 50,
    },
    "ilimitado": {
        "rotulo": "Ilimitado",
        "mensalidade": 4990.0,
        "limite": None,
        # Uso justo reduzido de 120 para 60 em 30/07/2026: com o avulso a
        # 90/190/380, a referencia antiga embutia 81% de desconto — numero
        # dificil de defender se o cliente fizer a conta, e convite ao uso
        # como fabrica de relatorios. Com 60, o desconto volta a ~62% e ainda
        # e volume que nenhuma prefeitura media alcanca na pratica.
        "uso_justo": 60,         # referencia p/ conversa de reenquadramento
    },
}


def nivel_do_modulo(modulo: str) -> str:
    return NIVEIS.get(modulo, "Médio")


def valor_do_modulo(modulo: str) -> float:
    return VALOR_REFERENCIA[nivel_do_modulo(modulo)]


def plano_info(plano: str) -> dict:
    return PLANOS.get(plano or "avulso", PLANOS["avulso"])
