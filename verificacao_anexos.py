# -*- coding: utf-8 -*-
"""
=============================================================================
 verificacao_anexos.py  -  RM Lisura / RM Vertice Digital
 Conferencia DETERMINISTICA dos anexos do edital.
=============================================================================

POR QUE ESTE MODULO EXISTE
--------------------------
A conferencia dos anexos era feita pela IA (verificacao X04) e oscilava entre
"inconformidade", "alerta" e "revisar" para o MESMO edital. Localizar as
mencoes a "Anexo I", "Anexo II"... e verificar se a sequencia esta completa e
sem repeticao e contagem, nao interpretacao — e contagem pertence ao codigo.

O achado real do edital de teste era: o ultimo anexo aparece numerado como
"Anexo IX" onde deveria ser "Anexo X". Isso se acha contando.

O QUE ESTE MODULO NAO FAZ
-------------------------
- Nao julga se o CONTEUDO do anexo corresponde ao titulo (isso e leitura).
- Nao afirma que um anexo esta ausente quando ha sinal de que a extracao do
  PDF falhou — nesse caso o achado sai como "revisar".
"""
from __future__ import annotations

import re
import unicodedata

_ROMANOS = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8,
    "IX": 9, "X": 10, "XI": 11, "XII": 12, "XIII": 13, "XIV": 14, "XV": 15,
    "XVI": 16, "XVII": 17, "XVIII": 18, "XIX": 19, "XX": 20,
}
_INV_ROMANOS = {v: k for k, v in _ROMANOS.items()}


def _sem_acento(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s or ""))
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


# "ANEXO I", "Anexo II –", "anexo 3", "ANEXO IV -"
_RE_ANEXO = re.compile(
    r"\banexo\s+(" + "|".join(sorted(_ROMANOS, key=len, reverse=True)) + r"|\d{1,2})\b",
    re.IGNORECASE,
)


def _numero(token: str):
    t = token.strip().upper()
    if t.isdigit():
        n = int(t)
        return n if 0 < n <= 30 else None
    return _ROMANOS.get(t)


def extrair_anexos(texto: str) -> list[dict]:
    """Todas as mencoes a anexos, classificadas em tres tipos.

    A distincao e o coracao deste modulo, e errar nela produz falso positivo
    grave. Todo edital cita cada anexo em DOIS lugares legitimos:

      1. na LISTA de anexos ("Anexo I - Termo de Referencia;" seguido de
         "Anexo II - ...", em linhas consecutivas);
      2. na ABERTURA do proprio anexo ("ANEXO I" sozinho na linha, com o
         titulo do documento na linha de baixo).

    Contar as duas como declaracao faz o modulo acusar "anexo repetido" num
    edital perfeitamente normal — foi o que aconteceu na primeira versao, que
    apontou repeticao dos anexos I a VIII do edital de teste.

    O criterio que separa: numa LISTA, a linha vizinha (acima ou abaixo)
    tambem menciona anexo. Numa ABERTURA, nao.
    """
    bruto = texto or ""
    linhas = bruto.split("\n")
    # posicao inicial de cada linha, para mapear match -> indice de linha
    inicios, acc = [], 0
    for ln in linhas:
        inicios.append(acc)
        acc += len(ln) + 1

    def indice_linha(pos):
        lo, hi = 0, len(inicios) - 1
        while lo < hi:
            meio = (lo + hi + 1) // 2
            if inicios[meio] <= pos:
                lo = meio
            else:
                hi = meio - 1
        return lo

    tem_anexo = [bool(_RE_ANEXO.search(ln)) for ln in linhas]

    achados = []
    for m in _RE_ANEXO.finditer(bruto):
        n = _numero(m.group(1))
        if n is None:
            continue
        li = indice_linha(m.start())
        linha = linhas[li]
        antes_na_linha = linha[: m.start() - inicios[li]].strip()
        resto_da_linha = linha[m.end() - inicios[li]:]
        no_comeco = len(antes_na_linha) <= 2

        # A abertura de um anexo ocupa a linha SOZINHA: depois do numero vem no
        # maximo um travessao, e o titulo do documento fica na linha de baixo.
        # Exigir isso e o que separa "ANEXO VI" (abertura) de "Anexo VI;"
        # — remissao cuja quebra de linha no PDF a deixou no inicio da linha,
        # falso positivo que apontava repeticao inexistente no edital de teste.
        so_o_anexo = bool(re.fullmatch(r"[\s\-–—:]*", resto_da_linha))

        vizinha_tem_anexo = ((li > 0 and tem_anexo[li - 1]) or
                             (li + 1 < len(linhas) and tem_anexo[li + 1]))

        if no_comeco and so_o_anexo:
            tipo = "abertura"          # declaracao do anexo em si
        elif no_comeco and vizinha_tem_anexo:
            tipo = "lista"             # sumario de anexos
        else:
            tipo = "remissao"          # citado no meio de um paragrafo

        achados.append({
            "numero": n,
            "texto": m.group(0),
            "pos": m.start(),
            "tipo": tipo,
            "titulo": tipo == "abertura",   # compatibilidade
            "linha": _sem_acento(linha).strip()[:120],
        })
    return achados


def _achado(aid, item, status, severidade, detalhe, trecho=""):
    return {
        "id": aid, "categoria": "Anexos", "item": item,
        "base_legal": "Lei 14.133/2021, art. 25", "severidade": severidade,
        "tipo": "automatica", "status": status, "detalhe": detalhe,
        "trecho": trecho[:400], "fonte": "Automatico", "fundamento": "",
    }


def verificar(texto: str) -> list[dict]:
    """Confere a sequencia de anexos. IDs fixos A01..A03, sempre presentes."""
    mencoes = extrair_anexos(texto)
    if not mencoes:
        return [
            _achado("A01", "Sequencia de numeracao dos anexos", "revisar", "media",
                    "Nao foi localizada nenhuma mencao a anexos no texto. Confirme se o "
                    "edital possui anexos e se eles foram enviados junto ao arquivo."),
            _achado("A02", "Anexos citados e nao declarados", "revisar", "media",
                    "Sem mencoes a anexos, nao ha o que conferir."),
            _achado("A03", "Repeticao de numero de anexo", "ok", "baixa",
                    "Sem mencoes a anexos, nao ha repeticao a apontar."),
        ]

    titulos = [a for a in mencoes if a["tipo"] == "abertura"]
    listados = {a["numero"] for a in mencoes if a["tipo"] == "lista"}
    nums_titulo = sorted({a["numero"] for a in titulos})
    nums_todos = sorted({a["numero"] for a in mencoes})
    achados = []

    # ---------------- A01: sequencia continua ----------------
    universo = nums_titulo or nums_todos
    if not universo:
        achados.append(_achado("A01", "Sequencia de numeracao dos anexos", "revisar", "media",
                               "Nao foi possivel identificar a numeracao dos anexos."))
    else:
        esperado = list(range(1, max(universo) + 1))
        faltando = [n for n in esperado if n not in universo]
        if faltando:
            rotulos = ", ".join(_INV_ROMANOS.get(n, str(n)) for n in faltando)
            achados.append(_achado(
                "A01", "Sequencia de numeracao dos anexos", "inconformidade", "media",
                f"A numeracao dos anexos vai ate {_INV_ROMANOS.get(max(universo), max(universo))} "
                f"({max(universo)}), mas nao ha mencao ao(s) anexo(s) {rotulos}. Ha salto na "
                "sequencia: ou um anexo foi omitido, ou a numeracao esta incorreta — o caso "
                "classico e o ultimo anexo repetir o numero do anterior.",
                trecho="; ".join(a["linha"] for a in titulos[-3:]),
            ))
        else:
            achados.append(_achado(
                "A01", "Sequencia de numeracao dos anexos", "ok", "baixa",
                f"Numeracao continua de I ate {_INV_ROMANOS.get(max(universo), max(universo))} "
                f"({max(universo)} anexo(s)), sem saltos.",
            ))

    # ---------------- A02: citado no corpo mas nao declarado ----------------
    # Conta como "citado" tanto a remissao no texto quanto a entrada na lista de
    # anexos: nos dois casos o edital promete um documento que precisa existir.
    citados = {a["numero"] for a in mencoes if a["tipo"] in ("remissao", "lista")}
    declarados = set(nums_titulo)
    orfaos = sorted(citados - declarados) if declarados else []
    if orfaos:
        rotulos = ", ".join(_INV_ROMANOS.get(n, str(n)) for n in orfaos)
        achados.append(_achado(
            "A02", "Anexos citados e nao declarados", "alerta", "media",
            f"O(s) anexo(s) {rotulos} sao citados no corpo do edital, mas nao foi localizado "
            "o respectivo titulo/abertura no documento. Pode ser anexo faltante ou falha na "
            "leitura do PDF; confirme no arquivo original.",
        ))
    else:
        achados.append(_achado(
            "A02", "Anexos citados e nao declarados", "ok", "baixa",
            "Todo anexo citado no corpo do edital possui titulo correspondente no documento."
            if declarados else
            "Nao foi possivel distinguir titulos de remissoes; nada a apontar.",
        ))

    # ---------------- A03: numero repetido em titulos ----------------
    vistos, repetidos = set(), []
    for a in titulos:
        if a["numero"] in vistos:
            repetidos.append(a)
        vistos.add(a["numero"])
    if repetidos:
        rot = ", ".join(dict.fromkeys(
            _INV_ROMANOS.get(a["numero"], str(a["numero"])) for a in repetidos))
        achados.append(_achado(
            "A03", "Repeticao de numero de anexo", "inconformidade", "media",
            f"O(s) numero(s) de anexo {rot} aparece(m) mais de uma vez como titulo. Dois "
            "anexos com o mesmo numero geram duvida sobre qual documento o licitante deve "
            "apresentar e sao causa frequente de impugnacao.",
            trecho="; ".join(a["linha"] for a in repetidos[:3]),
        ))
    else:
        achados.append(_achado(
            "A03", "Repeticao de numero de anexo", "ok", "baixa",
            f"Nenhum numero de anexo repetido ({len(titulos)} titulo(s) de anexo localizado(s))."
        ))

    return achados
