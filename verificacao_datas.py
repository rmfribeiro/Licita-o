# -*- coding: utf-8 -*-
"""
=============================================================================
 verificacao_datas.py  -  RM Lisura / RM Vertice Digital
 Conferencia DETERMINISTICA das datas do edital (Lei 14.133/2021).
=============================================================================

POR QUE ESTE MODULO EXISTE
--------------------------
Ate 12/08/2026 a coerencia das datas era perguntada a IA. O resultado, medido
em 20 execucoes sobre o MESMO edital: numa rodada o parecer afirmava "ha
incoerencia nas datas"; na seguinte, "as datas estao conformes". Nao sao duas
leituras possiveis de um ponto interpretativo — ou as datas batem, ou nao
batem, e uma das respostas estava errada.

Comparar datas e contar dias e aritmetica. Aritmetica pertence ao codigo:
o resultado e o mesmo hoje, amanha e daqui a um ano, e cada apontamento e
rastreavel ate o trecho do edital que o gerou. E isso que torna o parecer
defensavel perante o orgao de controle.

O QUE ESTE MODULO NAO FAZ
-------------------------
- Nao considera feriados municipais/estaduais/nacionais na contagem de dias
  uteis (so exclui sabados e domingos). Por isso, quando o prazo fica no
  limite, o achado sai como ALERTA para conferencia humana, nunca como
  inconformidade.
- Nao adivinha o prazo aplicavel quando o objeto e o criterio de julgamento
  nao aparecem de forma reconhecivel: nesse caso usa o PISO ABSOLUTO do
  art. 55 (8 dias uteis) e diz explicitamente que a checagem foi pelo piso.
- Quando nao encontra as datas, devolve "nao verificavel". Silencio nunca
  vira aprovacao.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta

# -----------------------------------------------------------------------------
# ART. 55 — PRAZOS MINIMOS ENTRE A DIVULGACAO DO EDITAL E A APRESENTACAO DE
# PROPOSTAS, EM DIAS UTEIS.
# -----------------------------------------------------------------------------
# Redacao da Lei 14.133/2021. A escolha do inciso depende do objeto e do
# criterio de julgamento; por isso cada entrada guarda o texto do dispositivo,
# que vai citado no achado.
PRAZOS_ART_55 = {
    "bens_menor_preco":        (8,  "art. 55, I, 'a' — aquisicao de bens, menor preco ou maior desconto"),
    "bens_demais":             (15, "art. 55, I, 'b' — aquisicao de bens, demais hipoteses"),
    "servicos_comuns":         (10, "art. 55, II, 'a' — servicos e obras comuns, menor preco ou maior desconto"),
    "servicos_especiais":      (25, "art. 55, II, 'b' — servicos e obras especiais, menor preco ou maior desconto"),
    "contratacao_integrada":   (60, "art. 55, II, 'c' — regime de contratacao integrada"),
    "semi_integrada_demais":   (35, "art. 55, II, 'd' — semi-integrada ou demais hipoteses"),
    "maior_lance":             (15, "art. 55, III — criterio de maior lance"),
    "tecnica_e_preco":         (35, "art. 55, IV — tecnica e preco, melhor tecnica ou conteudo artistico"),
}
PISO_ABSOLUTO = 8   # menor prazo previsto no art. 55; violar isso e inconformidade em qualquer hipotese

_MESES = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}


def _sem_acento(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s or ""))
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", _sem_acento(s).lower())


# dd/mm/aaaa  ·  dd.mm.aaaa  ·  dd-mm-aaaa
_RE_DATA_NUM = re.compile(r"\b(\d{1,2})\s*[/.\-]\s*(\d{1,2})\s*[/.\-]\s*(\d{4})\b")
# "10 de agosto de 2026"
_RE_DATA_EXT = re.compile(
    r"\b(\d{1,2})\s+de\s+(" + "|".join(_MESES) + r")\s+de\s+(\d{4})\b", re.IGNORECASE
)


def _data_valida(d: int, m: int, a: int):
    """Devolve date ou None. None significa data impossivel (ex.: 31/02)."""
    try:
        if not (1900 < a < 2200):
            return None
        return date(a, m, d)
    except ValueError:
        return None


def extrair_datas(texto: str) -> list[dict]:
    """Extrai todas as datas do texto com a janela de contexto ao redor.

    A janela e o que permite classificar a data depois (publicacao, sessao,
    validade...) e e citada no relatorio como trecho comprobatorio.
    """
    achadas = []
    bruto = texto or ""
    n = _norm(bruto)

    for m in _RE_DATA_NUM.finditer(bruto):
        dd, mm, aa = (int(g) for g in m.groups())
        achadas.append({
            "data": _data_valida(dd, mm, aa),
            "texto": m.group(0),
            "pos": m.start(),
            "antes": _norm(bruto[max(0, m.start() - 200): m.start()]),
            "depois": _norm(bruto[m.end(): m.end() + 60]),
        })

    for m in _RE_DATA_EXT.finditer(bruto):
        dd = int(m.group(1))
        mm = _MESES[_sem_acento(m.group(2)).lower()]
        aa = int(m.group(3))
        achadas.append({
            "data": _data_valida(dd, mm, aa),
            "texto": m.group(0),
            "pos": m.start(),
            "antes": _norm(bruto[max(0, m.start() - 200): m.start()]),
            "depois": _norm(bruto[m.end(): m.end() + 60]),
        })

    achadas.sort(key=lambda x: x["pos"])
    return achadas


# Termos que identificam o papel de cada data. Ordem importa: o primeiro grupo
# que casar define a classificacao.
_PAPEIS = (
    ("sessao", ("sessao publica", "abertura da sessao", "recebimento das propostas",
                "apresentacao das propostas", "abertura das propostas", "data da disputa",
                "inicio da sessao", "abertura do certame", "recebimento de propostas")),
    ("publicacao", ("publicacao", "divulgacao", "publicado no", "disponibilizacao do edital",
                    "divulgado no pncp", "aviso de licitacao")),
    ("assinatura", ("assinatura", "assinado em", "emitido em", "expedido em")),
    ("validade_proposta", ("validade da proposta", "prazo de validade da proposta")),
    ("vigencia", ("vigencia do contrato", "vigencia contratual", "prazo de vigencia")),
)


# Fecho de documento oficial: "<municipio>/<UF>, <data>" ou "<municipio>, <data>".
# Exige a virgula colada ao fim da janela anterior, para nao casar com qualquer
# palavra seguida de virgula no meio de um paragrafo.
_RE_FECHO = re.compile(r"(?:^|[\s\-–—])[a-z][a-z\s'\.]{2,40}(?:/[a-z]{2})?,\s*$")


def classificar(datas: list[dict]) -> dict:
    """Agrupa as datas por papel, a partir do contexto em que aparecem.

    O texto ANTERIOR a data tem prioridade absoluta sobre o posterior. Em
    portugues o papel da data e declarado antes dela ("publicado em X", "a
    sessao ocorrera em Y"); a oracao seguinte costuma tratar de outra coisa.
    Sem essa prioridade, em "publicado no PNCP em 10/08. A sessao sera em 14/08"
    a PRIMEIRA data era classificada como sessao — porque a frase seguinte
    mencionava a sessao — e o prazo do art. 55 deixava de ser conferido.
    """
    fora = {p: [] for p, _ in _PAPEIS}
    fora["indefinido"] = []
    for d in datas:
        antes, depois = d.get("antes", ""), d.get("depois", "")
        papel_escolhido = None
        for janela in (antes, antes + " " + depois):      # anterior primeiro
            for papel, termos in _PAPEIS:
                if any(t in janela for t in termos):
                    papel_escolhido = papel
                    break
            if papel_escolhido:
                break
        # Fecho do documento: "Municipio/UF, <data>". E a data de emissao do
        # edital. Muitos editais nao trazem a data de publicacao no corpo — o
        # aviso e divulgado a parte, no PNCP e no diario oficial — e sem esta
        # deteccao o prazo do art. 55 nunca seria conferido em documento real.
        # Como a divulgacao NUNCA precede a assinatura, tomar esta data como
        # referencia e conservador: se o prazo ja estoura contado daqui, estoura
        # com mais razao contado da publicacao.
        if papel_escolhido is None and _RE_FECHO.search(antes):
            papel_escolhido = "assinatura"
        fora[papel_escolhido or "indefinido"].append(d)
    return fora


def dias_uteis_entre(inicio: date, fim: date) -> int:
    """Dias uteis entre duas datas, excluindo o dia inicial e incluindo o final.

    NAO desconta feriados — a lista varia por municipio e nao esta no edital.
    Por isso o resultado e tratado como ESTIMATIVA no limite (ver montar_achados).
    """
    if fim <= inicio:
        return 0
    dias, cur = 0, inicio
    while cur < fim:
        cur += timedelta(days=1)
        if cur.weekday() < 5:      # 0-4 = segunda a sexta
            dias += 1
    return dias


def detectar_prazo_aplicavel(texto: str):
    """Descobre qual inciso do art. 55 se aplica, pelo objeto e criterio.

    Devolve (dias_minimos, dispositivo, seguro). `seguro=False` significa que
    nao foi possivel identificar com confianca e usou-se o piso absoluto —
    o achado deve dizer isso ao leitor.
    """
    t = _norm(texto)
    tecnica = ("tecnica e preco" in t or "melhor tecnica" in t or "conteudo artistico" in t)
    maior_lance = "maior lance" in t
    integrada = "contratacao integrada" in t
    semi = "contratacao semi-integrada" in t or "semi integrada" in t
    menor_preco = "menor preco" in t or "maior desconto" in t
    obra_serv = any(x in t for x in ("obra", "servico de engenharia", "servicos de engenharia",
                                     "prestacao de servicos", "execucao de servicos"))
    bens = any(x in t for x in ("aquisicao de bens", "aquisicao de equipamentos", "fornecimento de",
                                "aquisicao de materiais", "compra de"))

    if integrada:
        d, disp = PRAZOS_ART_55["contratacao_integrada"]; return d, disp, True
    if semi:
        d, disp = PRAZOS_ART_55["semi_integrada_demais"]; return d, disp, True
    if tecnica:
        d, disp = PRAZOS_ART_55["tecnica_e_preco"]; return d, disp, True
    if maior_lance:
        d, disp = PRAZOS_ART_55["maior_lance"]; return d, disp, True
    if bens and menor_preco:
        d, disp = PRAZOS_ART_55["bens_menor_preco"]; return d, disp, True
    if bens:
        d, disp = PRAZOS_ART_55["bens_demais"]; return d, disp, True
    if obra_serv and menor_preco:
        d, disp = PRAZOS_ART_55["servicos_comuns"]; return d, disp, True
    if obra_serv:
        d, disp = PRAZOS_ART_55["servicos_especiais"]; return d, disp, True

    return PISO_ABSOLUTO, "art. 55, I, 'a' (piso absoluto)", False


def _achado(aid, item, status, severidade, detalhe, trecho="", base="Lei 14.133/2021"):
    return {
        "id": aid, "categoria": "Datas e prazos", "item": item,
        "base_legal": base, "severidade": severidade, "tipo": "automatica",
        "status": status, "detalhe": detalhe, "trecho": trecho[:400],
        "fonte": "Automatico", "fundamento": "",
    }


def verificar(texto: str, ano_referencia: int | None = None) -> list[dict]:
    """Confere as datas do edital e devolve achados no formato do analisador.

    Sempre devolve os mesmos IDs (D01..D04) para o mesmo texto: e o que garante
    que dois relatorios do mesmo edital tragam exatamente o mesmo resultado.
    """
    datas = extrair_datas(texto)
    grupos = classificar(datas)
    achados = []

    # ---------------- D01: prazo minimo do art. 55 ----------------
    pubs = [d for d in grupos["publicacao"] if d["data"]] or \
           [d for d in grupos["assinatura"] if d["data"]]
    sessoes = [d for d in grupos["sessao"] if d["data"]]

    if not pubs or not sessoes:
        achados.append(_achado(
            "D01", "Prazo minimo entre divulgacao e apresentacao de propostas (art. 55)",
            "revisar", "alta",
            "Nao foi possivel identificar no texto, com seguranca, a data de divulgacao "
            "e/ou a data da sessao publica. A contagem do prazo minimo do art. 55 depende "
            "dessas duas datas e precisa ser conferida manualmente.",
            base="Lei 14.133/2021, art. 55",
        ))
    else:
        d_pub = min(d["data"] for d in pubs)
        d_ses = min(d["data"] for d in sessoes)
        minimo, disp, seguro = detectar_prazo_aplicavel(texto)
        uteis = dias_uteis_entre(d_pub, d_ses)
        ressalva = ("" if seguro else
                    " O objeto/criterio de julgamento nao foi identificado com seguranca no "
                    "texto; a conferencia usou o PISO ABSOLUTO de 8 dias uteis. Confirme qual "
                    "inciso do art. 55 se aplica.")
        nota_feriado = (" A contagem exclui sabados e domingos, mas NAO feriados; "
                        "com feriados no periodo o prazo real e menor.")
        base = f"Lei 14.133/2021, {disp}"
        if uteis < minimo:
            achados.append(_achado(
                "D01", "Prazo minimo entre divulgacao e apresentacao de propostas (art. 55)",
                "inconformidade", "alta",
                f"Entre a divulgacao ({d_pub.strftime('%d/%m/%Y')}) e a sessao publica "
                f"({d_ses.strftime('%d/%m/%Y')}) ha {uteis} dia(s) util(eis), abaixo do minimo "
                f"de {minimo} exigido pelo {disp}. O descumprimento do prazo minimo e causa de "
                f"nulidade do certame e enseja impugnacao.{ressalva}{nota_feriado}",
                base=base,
            ))
        elif uteis <= minimo + 2:
            achados.append(_achado(
                "D01", "Prazo minimo entre divulgacao e apresentacao de propostas (art. 55)",
                "alerta", "media",
                f"Entre a divulgacao ({d_pub.strftime('%d/%m/%Y')}) e a sessao "
                f"({d_ses.strftime('%d/%m/%Y')}) ha {uteis} dia(s) util(eis), contra o minimo de "
                f"{minimo} ({disp}). A margem e estreita.{ressalva}{nota_feriado}",
                base=base,
            ))
        else:
            achados.append(_achado(
                "D01", "Prazo minimo entre divulgacao e apresentacao de propostas (art. 55)",
                "ok", "media",
                f"Entre a divulgacao ({d_pub.strftime('%d/%m/%Y')}) e a sessao "
                f"({d_ses.strftime('%d/%m/%Y')}) ha {uteis} dia(s) util(eis), acima do minimo de "
                f"{minimo} ({disp}).{ressalva}{nota_feriado}",
                base=base,
            ))

        # ---------------- D02: sessao anterior a divulgacao ----------------
        if d_ses < d_pub:
            achados.append(_achado(
                "D02", "Ordem cronologica entre divulgacao e sessao publica",
                "inconformidade", "alta",
                f"A data da sessao publica ({d_ses.strftime('%d/%m/%Y')}) e ANTERIOR a data de "
                f"divulgacao do edital ({d_pub.strftime('%d/%m/%Y')}). Ha erro material no edital "
                "ou as datas foram trocadas.",
            ))
        else:
            achados.append(_achado(
                "D02", "Ordem cronologica entre divulgacao e sessao publica", "ok", "media",
                f"A sessao ({d_ses.strftime('%d/%m/%Y')}) e posterior a divulgacao "
                f"({d_pub.strftime('%d/%m/%Y')}), como deve ser.",
            ))

    # ---------------- D03: exercicio orcamentario ----------------
    anos_doc = sorted({d["data"].year for d in datas if d["data"]})
    ano_ref = ano_referencia or (max((d["data"].year for d in sessoes if d["data"]), default=None)) \
              or (max(anos_doc) if anos_doc else None)
    m_ex = re.search(r"exerc[ií]cio\s+(?:financeiro\s+|or[cç]ament[aá]rio\s+)?(?:de\s+)?(\d{4})",
                     texto or "", re.IGNORECASE)
    if not m_ex or ano_ref is None:
        achados.append(_achado(
            "D03", "Exercicio orcamentario indicado", "revisar", "media",
            "Nao foi localizada mencao explicita ao exercicio orcamentario (ou nao foi possivel "
            "determinar o ano do certame). Confirme a dotacao no processo.",
            base="Lei 14.133/2021, art. 150",
        ))
    else:
        ano_ex = int(m_ex.group(1))
        if ano_ex != ano_ref:
            achados.append(_achado(
                "D03", "Exercicio orcamentario indicado", "inconformidade", "alta",
                f"O edital indica o exercicio orcamentario de {ano_ex}, mas o certame ocorre em "
                f"{ano_ref}. A despesa deve correr a conta do exercicio em que sera realizada; "
                "divergencia sugere reaproveitamento de minuta de ano anterior.",
                trecho=m_ex.group(0), base="Lei 14.133/2021, art. 150",
            ))
        else:
            achados.append(_achado(
                "D03", "Exercicio orcamentario indicado", "ok", "media",
                f"O exercicio orcamentario indicado ({ano_ex}) coincide com o ano do certame.",
                trecho=m_ex.group(0), base="Lei 14.133/2021, art. 150",
            ))

    # ---------------- D04: datas impossiveis ----------------
    invalidas = [d for d in datas if d["data"] is None]
    if invalidas:
        amostra = ", ".join(dict.fromkeys(d["texto"] for d in invalidas))[:180]
        achados.append(_achado(
            "D04", "Datas invalidas no texto", "alerta", "media",
            f"Foram encontradas {len(invalidas)} ocorrencia(s) de data inexistente no calendario "
            f"({amostra}). Pode ser erro de digitacao ou falha na leitura do PDF; confirme no "
            "documento original.",
            trecho=amostra,
        ))
    else:
        achados.append(_achado(
            "D04", "Datas invalidas no texto", "ok", "baixa",
            f"Nenhuma data invalida encontrada ({len(datas)} data(s) analisada(s)).",
        ))

    return achados
