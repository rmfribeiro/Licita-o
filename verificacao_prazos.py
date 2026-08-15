# -*- coding: utf-8 -*-
"""
=============================================================================
 verificacao_prazos.py  -  RM Lisura / RM Vertice Digital
 Conferencia DETERMINISTICA do prazo de entrega/execucao (achados P01 e P02).
=============================================================================

POR QUE ESTE MODULO EXISTE
--------------------------
A conferencia X01 ("prazo de entrega: edital x Termo de Referencia") era feita
pela IA e oscilava entre execucoes: ora "revisar", ora "inconformidade", sobre
o MESMO edital. Mas o que ela faz e LOCALIZAR numeros, COMPARAR numeros e
COMPARAR marcos temporais — isso e leitura mecanica, nao interpretacao
juridica, e pertence ao codigo. Mesma decisao ja tomada para as datas
(verificacao_datas.py) e para os anexos (verificacao_anexos.py).

O QUE ELE FAZ
-------------
P01 - Coerencia do PRAZO (numero + unidade) entre as pecas do processo:
      corpo do edital, Termo de Referencia, minuta da ata e minuta de contrato.
      Prazos diferentes para a mesma obrigacao geram inseguranca sobre o dever
      do contratado e dao margem a impugnacao.

P02 - Coerencia do TERMO INICIAL (dies a quo): "30 dias a contar da nota de
      empenho" e "30 dias apos atestada a solicitacao" tem o mesmo numero e
      obrigacoes diferentes. Foi o achado real do edital de Laranjeiras.

REGRAS DE PROJETO OBEDECIDAS AQUI
---------------------------------
1. "Nao consegui verificar" NUNCA vira afirmacao sobre o verificado. Sem
   prazo localizado, ou sem conseguir delimitar as secoes do documento, o
   achado sai como "revisar" explicando o que faltou — jamais como "conforme".
2. "dias" e "dias uteis" NAO sao convertidos um no outro: sao unidades com
   efeitos juridicos distintos, e tratar 30 dias uteis como 30 dias corridos
   seria inventar uma equivalencia que a lei nao faz. Sao comparados como
   unidades diferentes.
3. IDs fixos (P01, P02), sempre presentes no relatorio, para que a contagem de
   linhas nao mude entre duas execucoes do mesmo edital.
"""
from __future__ import annotations

import re
import unicodedata

CATEGORIA = "Prazos"
BASE_LEGAL = "Lei 14.133/2021, arts. 6º, XXIII, 'd', 40, §1º, e 92, IV"


def _sem_acento(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s or ""))
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", _sem_acento(s)).strip().lower()


# --------------------------------------------------------------- secoes
# O edital chega como UM arquivo com todas as pecas emendadas. Para dizer
# "o edital diz X e o TR diz Y" e preciso saber onde cada peca comeca.
# So contam cabecalhos: a expressao "Termo de Referencia" aparece dezenas de
# vezes como REMISSAO ("conforme o Anexo I - Termo de Referencia"), e tomar
# a primeira ocorrencia como inicio da secao jogaria o corpo do edital inteiro
# para dentro do TR.
_CABECALHOS = (
    ("TR",        r"termo de referencia\s*(?:[-–—]\s*tr)?\s*$"),
    ("TR",        r"^\s*anexo\s+[ivx\d]+\s*[-–—]?\s*termo de referencia\s*$"),
    ("ATA",       r"^\s*(?:anexo\s+[ivx\d]+\s*[-–—]?\s*)?minuta\s+d[ao]\s+ata\s+de\s+registro\s+de\s+precos\s*$"),
    ("CONTRATO",  r"^\s*(?:anexo\s+[ivx\d]+\s*[-–—]?\s*)?minuta\s+d[eo]\s+contrato\b.*$"),
)

_ROTULO_SECAO = {
    "CORPO":    "corpo do edital",
    "TR":       "Termo de Referência",
    "ATA":      "minuta da ata de registro de preços",
    "CONTRATO": "minuta de contrato",
}


def mapear_secoes(texto: str) -> list[tuple[int, str]]:
    """Devolve [(posicao_inicial, secao)] ordenado. Sempre comeca em CORPO."""
    marcos: list[tuple[int, str]] = []
    for linha in re.finditer(r"(?m)^.*$", texto):
        bruto = linha.group(0).strip()
        if not bruto or len(bruto) > 90:      # cabecalho e linha curta
            continue
        alvo = _norm(bruto)
        for secao, padrao in _CABECALHOS:
            if re.search(padrao, alvo):
                marcos.append((linha.start(), secao))
                break
    # Fica a ULTIMA ocorrencia de cada secao, nao a primeira.
    #
    # DEFEITO REAL, pego no 1o teste com o edital de Laranjeiras (14/08/2026):
    # o edital traz, perto do fim do corpo, o SUMARIO dos anexos —
    #   "ANEXO I - Termo de Referencia."
    #   "ANEXO III - Minuta da Ata de Registro de Precos"
    #   "ANEXO IV - Minuta do Contrato"
    # tres linhas seguidas que casam com os cabecalhos. Tomando a primeira
    # ocorrencia, a "minuta de contrato" comecava no sumario (posicao 83.179) e
    # a secao real (175.906) ficava dentro dela — resultado: TODOS os prazos
    # eram atribuidos ao Termo de Referencia e a comparacao entre pecas virava
    # ficcao. O sumario sempre PRECEDE as pecas, entao a ultima ocorrencia e a
    # peca de verdade.
    ultimos: dict[str, int] = {}
    for pos, sec in sorted(marcos):
        ultimos[sec] = pos
    limpos = sorted((pos, sec) for sec, pos in ultimos.items())

    # As pecas tem ordem canonica no processo. Cabecalho fora de ordem e sinal
    # de que casamos com um indice ou com uma remissao — descartar e melhor do
    # que delimitar errado e afirmar divergencia inexistente.
    ordem = {"TR": 1, "ATA": 2, "CONTRATO": 3}
    coerentes: list[tuple[int, str]] = []
    ultimo_grau = 0
    for pos, sec in limpos:
        grau = ordem.get(sec, 0)
        if grau >= ultimo_grau:
            coerentes.append((pos, sec))
            ultimo_grau = grau
    return [(0, "CORPO")] + coerentes


def secao_de(pos: int, marcos: list[tuple[int, str]]) -> str:
    atual = "CORPO"
    for ini, sec in marcos:
        if pos >= ini:
            atual = sec
        else:
            break
    return atual


# --------------------------------------------------------------- prazos
# "30 (trinta) dias", "10 (dez) dias uteis", "12 (doze) meses", "48 horas".
_RE_PRAZO = re.compile(
    r"(\d{1,3})\s*(?:\(\s*[^)]{1,30}\s*\))?\s*"
    r"(dias?\s+uteis|dias?\s+corridos|dias?\s+consecutivos|dias?|meses|mes|horas?)",
    re.IGNORECASE,
)

# So interessa o prazo DE ENTREGA/EXECUCAO. Sem este filtro o modulo compararia
# prazo de recurso com prazo de pagamento e apontaria divergencia inexistente.
_RE_CONTEXTO_ENTREGA = re.compile(
    r"prazo\s+(?:maximo\s+)?(?:de|para|da)\s+(?:entrega|execucao|fornecimento)"
    r"|entregas?\s+d[oe]s?\s+iten?s?\s+dever[ao]",
    re.IGNORECASE,
)

# DEFEITO REAL, pego no 1o teste (14/08/2026): a primeira versao incluia aqui
# "prazo de vigencia da contratacao". Vigencia (12 meses) e prazo de ENTREGA
# (30 dias) sao obrigacoes distintas; compara-las fez o modulo acusar
# "inconformidade — prazos diferentes: 12 meses e 30 dias" num edital onde os
# dois numeros estao corretos. Falso positivo desta natureza, num relatorio
# assinado, destroi a credibilidade do produto inteiro.

# Unidades equivalentes: dia corrido, consecutivo e "dia" simples sao a mesma
# coisa no calendario civil (art. 132 do Codigo Civil). Dia UTIL nao entra aqui.
_EQUIV_UNIDADE = {
    "dia": "dias corridos", "dias": "dias corridos",
    "dia corrido": "dias corridos", "dias corridos": "dias corridos",
    "dia consecutivo": "dias corridos", "dias consecutivos": "dias corridos",
    "dia util": "dias úteis", "dias uteis": "dias úteis",
    "mes": "meses", "meses": "meses",
    "hora": "horas", "horas": "horas",
}

# Marcos iniciais reconhecidos. A chave e o rotulo exibido; o valor, os termos
# que o identificam no texto.
_MARCOS = (
    ("nota de empenho",        (r"nota\s+de\s+empenho", r"\bempenho\b")),
    ("ordem de fornecimento",  (r"ordem\s+de\s+fornecimento",)),
    ("ordem de serviço",       (r"ordem\s+de\s+servico",)),
    ("solicitação atestada",   (r"atestada\s+a\s+solicitacao", r"solicitacao\s+previamente")),
    ("assinatura do contrato", (r"assinatura\s+d[oe]\s+contrato",)),
    ("assinatura da ata",      (r"assinatura\s+d[ae]\s+ata",)),
    ("recebimento da notificação", (r"recebimento\s+d[ae]\s+(?:notificacao|comunicacao)",)),
    ("publicação",             (r"publicacao\s+n[oa]",)),
)


def _unidade(bruta: str) -> str:
    return _EQUIV_UNIDADE.get(_norm(bruta), _norm(bruta))


def _marco_inicial(depois: str) -> str | None:
    """Le o trecho POSTERIOR ao prazo e identifica o dies a quo."""
    alvo = _norm(depois)
    gatilho = re.search(r"(contad[oa]s?|a\s+contar|apos|a\s+partir)", alvo)
    if not gatilho:
        return None
    janela = alvo[gatilho.start(): gatilho.start() + 140]
    for rotulo, termos in _MARCOS:
        for t in termos:
            if re.search(t, janela):
                return rotulo
    return None


def extrair_prazos_entrega(texto: str) -> list[dict]:
    """Prazos de entrega/execucao localizados, com secao e marco inicial."""
    marcos = mapear_secoes(texto)
    achados: list[dict] = []
    for m in _RE_PRAZO.finditer(texto):
        antes = texto[max(0, m.start() - 200): m.start()]
        if not _RE_CONTEXTO_ENTREGA.search(_norm(antes)):
            continue
        depois = texto[m.end(): m.end() + 200]
        achados.append({
            "valor":   int(m.group(1)),
            "unidade": _unidade(m.group(2)),
            "secao":   secao_de(m.start(), marcos),
            "marco":   _marco_inicial(depois),
            "pos":     m.start(),
            "trecho":  re.sub(r"\s+", " ", texto[max(0, m.start() - 130): m.end() + 90]).strip(),
        })
    return achados


# --------------------------------------------------------------- achados
def _achado(pid, item, status, severidade, detalhe, trecho=""):
    return {
        "id": pid, "categoria": CATEGORIA, "item": item,
        "base_legal": BASE_LEGAL, "severidade": severidade,
        "tipo": "automatica", "status": status, "detalhe": detalhe,
        "trecho": (trecho or "")[:400], "fonte": "Automatico", "fundamento": "",
    }


_ITEM_P01 = "Prazo de entrega/execução: coerência entre as peças"
_ITEM_P02 = "Termo inicial do prazo de entrega (dies a quo)"


def verificar(texto: str) -> list[dict]:
    """IDs fixos P01 e P02, sempre presentes — a contagem nao pode variar."""
    prazos = extrair_prazos_entrega(texto)

    if not prazos:
        # Ausencia de prazo localizado NAO e ausencia de prazo no edital: pode
        # ser falha de extracao do PDF, redacao atipica ou prazo remetido a
        # anexo nao enviado. Por isso "revisar", nunca "inconformidade".
        motivo = (
            "Não foi localizada, no texto extraído, nenhuma previsão numérica de prazo de "
            "entrega ou execução. Isto NÃO significa que o edital seja omisso: pode decorrer "
            "de redação atípica, de anexo não enviado junto ao arquivo ou de falha na "
            "extração do PDF. Confira manualmente o Termo de Referência e a minuta de contrato."
        )
        return [
            _achado("P01", _ITEM_P01, "revisar", "media", motivo),
            _achado("P02", _ITEM_P02, "revisar", "baixa",
                    "Sem prazo de entrega localizado, não há termo inicial a conferir."),
        ]

    # ---------------------------------------------------------------- P01
    combos = {}
    for p in prazos:
        combos.setdefault((p["valor"], p["unidade"]), []).append(p)
    secoes_com_prazo = sorted({p["secao"] for p in prazos})
    onde = ", ".join(_ROTULO_SECAO.get(s, s) for s in secoes_com_prazo)

    if len(combos) > 1:
        listagem = "; ".join(
            f"{v} {u} ({', '.join(sorted({_ROTULO_SECAO.get(x['secao'], x['secao']) for x in itens}))})"
            for (v, u), itens in sorted(combos.items())
        )
        p01 = _achado(
            "P01", _ITEM_P01, "inconformidade", "alta",
            f"Foram localizados prazos de entrega/execução DIFERENTES no mesmo processo: "
            f"{listagem}. A divergência gera insegurança sobre a obrigação do contratado e "
            f"dá margem a impugnação; deve ser uniformizada antes da publicação.",
            prazos[0]["trecho"],
        )
    elif len(secoes_com_prazo) == 1:
        (valor, unidade) = next(iter(combos))
        p01 = _achado(
            "P01", _ITEM_P01, "alerta", "media",
            f"O prazo de entrega/execução ({valor} {unidade}) foi localizado APENAS em "
            f"{onde}. Não foi localizada previsão correspondente nas demais peças do processo. "
            f"Como o Termo de Referência e a minuta integram o edital, não há divergência a "
            f"apontar — mas convém repetir o prazo na peça que vincula o contratado, para "
            f"afastar dúvida na execução.",
            prazos[0]["trecho"],
        )
    else:
        (valor, unidade) = next(iter(combos))
        p01 = _achado(
            "P01", _ITEM_P01, "ok", "media",
            f"O prazo de entrega/execução é o mesmo em todas as peças em que foi localizado "
            f"({valor} {unidade} — {onde}).",
            prazos[0]["trecho"],
        )

    # ---------------------------------------------------------------- P02
    com_marco = [p for p in prazos if p["marco"]]
    marcos_distintos = sorted({p["marco"] for p in com_marco})

    if not com_marco:
        p02 = _achado(
            "P02", _ITEM_P02, "revisar", "media",
            "O prazo de entrega foi localizado, mas não foi possível identificar no texto o "
            "seu termo inicial (a partir de que evento ele começa a correr). Confira "
            "manualmente: prazo sem marco inicial expresso é inexequível na prática.",
            prazos[0]["trecho"],
        )
    elif len(marcos_distintos) > 1:
        detalhe_marcos = "; ".join(
            f"'{mk}' ({', '.join(sorted({_ROTULO_SECAO.get(p['secao'], p['secao']) for p in com_marco if p['marco'] == mk}))})"
            for mk in marcos_distintos
        )
        p02 = _achado(
            "P02", _ITEM_P02, "alerta", "media",
            f"O prazo de entrega tem TERMOS INICIAIS diferentes ao longo do processo: "
            f"{detalhe_marcos}. Mesmo com igual número de dias, marcos iniciais distintos "
            f"produzem datas de vencimento distintas e comprometem a fiscalização e a "
            f"aplicação de sanção por atraso.",
            next(p["trecho"] for p in com_marco),
        )
    else:
        p02 = _achado(
            "P02", _ITEM_P02, "ok", "baixa",
            f"O termo inicial do prazo de entrega é uniforme: contado da "
            f"{marcos_distintos[0]}.",
            com_marco[0]["trecho"],
        )

    return [p01, p02]
