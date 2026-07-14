from __future__ import annotations
"""
=============================================================================
 pncp_busca.py  -  RM IA-Licita / RM Vertice Digital
 Ponte entre a busca de precos no PNCP e o modulo de pesquisa de mercado.
=============================================================================
 O que faz:
   Dado um TERMO (ex: "notebook"), busca precos reais no PNCP (Portal Nacional
   de Contratacoes Publicas), saneia os dados e devolve uma estrutura pronta
   para o app usar - no MESMO formato que ia_pesquisa_mercado.analisar() produz.

 Como se encaixa:
   - Reaproveita ia_pesquisa_mercado.calcular_referencia() para o calculo
     (mediana, exclusao de outliers, status) - NAO duplica logica.
   - Devolve 'itens_avaliados', 'fornecedores', etc., que os geradores de PDF
     (relatorio_pesquisa_mercado) ja entendem.

 Base legal: a IN SEGES/MGI 65/2021 PRIORIZA "contratacoes similares de outros
 entes publicos" como fonte de pesquisa de precos. O PNCP e a fonte oficial
 dessas contratacoes. Por isso, no relatorio, cada "fornecedor" e, na verdade,
 um ORGAO/MUNICIPIO de referencia.
=============================================================================
"""

import urllib.request
import urllib.parse
import urllib.error
import json
import ssl
import time
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

# Reaproveita o calculo que ja existe no sistema (nao duplica logica)
import ia_pesquisa_mercado

# ---------------------------------------------------------------------------
# CONFIGURACOES
# ---------------------------------------------------------------------------
DIAS_PARA_TRAS       = 90
MODALIDADES          = [6, 8]   # 6 = Pregao Eletronico ; 8 = Dispensa
MAX_CONTRATACOES     = 25       # teto de seguranca
ALVO_PRECOS_VALIDOS  = 12       # PARA de buscar ao juntar este tanto de precos aceitos
PAUSA_ENTRE_CHAMADAS = 0.0
TAMANHO_PAGINA       = 50
WORKERS_PARALELOS    = 6        # buscas de itens simultaneas
LOTE_CONTRATACOES    = 10       # itens de N contratacoes por vez, em paralelo

# UFs a pesquisar. Filtrar por estado reduz MUITO o volume a varrer (mais rapido)
# e costuma dar precos mais representativos (mesma regiao do cliente = IN 65/2021).
# Padrao: estados de maior volume de licitacoes. Para busca nacional, use [] (vazio).
# Para o estado do cliente, troque a lista (ex.: ["SE"] para Sergipe).
UFS_BUSCA            = ["SP", "MG", "RS", "PR", "SC"]
PAGINAS_PARALELAS    = 5        # baixa N paginas de contratacoes ao mesmo tempo

PALAVRAS_EXCLUSAO = [
    "manutencao", "conserto", "reparo", "assistencia tecnica", "assistencia",
    "locacao", "aluguel", "comodato", "instalacao",
    "reposicao", "acessorio", "acessorios",
    "suporte para", "carregador", "bateria",
    "cartucho", "toner", "recarga", "mochila",
    "fonte para", "gabinete", "carrinho de recarga",
]
PALAVRAS_EXCLUSAO_INTEIRAS = [
    "capa", "case", "hd", "ssd", "cabo", "peca", "pecas", "mouse", "teclado",
]

PISO_MINIMO_REAIS = 10.0

# Objetos "genericos" aceitos na 2a passada (quando a busca pelo objeto exato
# nao junta precos suficientes). O filtro pelo termo acontece depois, item a
# item, entao aqui basta reconhecer que a contratacao e uma COMPRA de bens.
OBJETOS_GENERICOS = [
    "aquisicao", "aquisicoes", "compra", "fornecimento",
    "equipamento", "equipamentos", "material", "materiais", "bens",
    "registro de precos",
]

_CTX = ssl.create_default_context()
_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "RM-IA-Licita/1.0 (pesquisa de precos PNCP)",
}
BASE_CONSULTA = "https://pncp.gov.br/api/consulta"
BASE_PNCP     = "https://pncp.gov.br/api/pncp"


# ---------------------------------------------------------------------------
# Auxiliares internos
# ---------------------------------------------------------------------------
def _norm(s) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFD", str(s))
    return s.encode("ascii", "ignore").decode().lower().strip()


def _get(url: str, tentativas: int = 3):
    req = urllib.request.Request(url, headers=_HEADERS)
    for t in range(1, tentativas + 1):
        try:
            with urllib.request.urlopen(req, context=_CTX, timeout=40) as resp:
                return True, json.loads(resp.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError:
            return False, None
        except Exception:
            if t < tentativas:
                time.sleep(2)
                continue
            return False, None
    return False, None


def _baixar_pagina(modalidade, uf, pagina, ini, fim):
    """Baixa UMA pagina de contratacoes. Devolve (lista, total_paginas)."""
    campos = {
        "dataInicial": ini, "dataFinal": fim,
        "codigoModalidadeContratacao": modalidade,
        "pagina": pagina, "tamanhoPagina": TAMANHO_PAGINA,
    }
    if uf:
        campos["uf"] = uf
    params = urllib.parse.urlencode(campos)
    ok, dados = _get(f"{BASE_CONSULTA}/v1/contratacoes/publicacao?{params}")
    if not ok or not isinstance(dados, dict):
        return [], 1
    return (dados.get("data") or []), (dados.get("totalPaginas") or 1)


def _combina(c: dict, termo_norm: str, relaxada: bool) -> bool:
    """Decide se a contratacao interessa.
    Passada exata  (relaxada=False): objeto contem o termo.
    Passada relaxada (relaxada=True): objeto generico de compra de bens
    (pula os que contem o termo — ja foram vistos na 1a passada)."""
    obj = _norm(c.get("objetoCompra"))
    if termo_norm in obj:
        return not relaxada
    if relaxada:
        return any(g in obj for g in OBJETOS_GENERICOS)
    return False


def _iterar_contratacoes(termo: str, ufs=None, dias=None, relaxada: bool = False):
    """Gera contratacoes que combinam com o termo.
    Otimizado: filtra por UF (menos volume) e baixa paginas EM PARALELO.
    """
    if dias is None:
        dias = DIAS_PARA_TRAS
    ini = (datetime.now() - timedelta(days=dias)).strftime("%Y%m%d")
    fim = datetime.now().strftime("%Y%m%d")
    termo_norm = _norm(termo)
    vistas = 0

    # ufs=None usa o padrao do modulo; lista vazia = busca nacional (uf=None)
    if ufs is None:
        ufs = UFS_BUSCA
    ufs = ufs if ufs else [None]

    for modalidade in MODALIDADES:
        for uf in ufs:
            if vistas >= MAX_CONTRATACOES:
                return
            # 1a pagina: descobre quantas paginas existem
            lista, total_paginas = _baixar_pagina(modalidade, uf, 1, ini, fim)
            for c in lista:
                if _combina(c, termo_norm, relaxada):
                    vistas += 1
                    yield c
                    if vistas >= MAX_CONTRATACOES:
                        return

            # Demais paginas: baixa em PARALELO, em blocos
            pagina = 2
            while pagina <= total_paginas and vistas < MAX_CONTRATACOES:
                bloco = list(range(pagina, min(pagina + PAGINAS_PARALELAS, total_paginas + 1)))
                with ThreadPoolExecutor(max_workers=PAGINAS_PARALELAS) as ex:
                    futuros = {
                        ex.submit(_baixar_pagina, modalidade, uf, p, ini, fim): p
                        for p in bloco
                    }
                    # Coleta resultados na ordem das paginas (p/ nao pular)
                    resultados = {}
                    for fut in as_completed(futuros):
                        p = futuros[fut]
                        try:
                            resultados[p] = fut.result()[0]
                        except Exception:
                            resultados[p] = []
                for p in bloco:
                    for c in resultados.get(p, []):
                        if _combina(c, termo_norm, relaxada):
                            vistas += 1
                            yield c
                            if vistas >= MAX_CONTRATACOES:
                                return
                pagina += PAGINAS_PARALELAS


def _buscar_itens(c: dict) -> list[dict]:
    cnpj = (c.get("orgaoEntidade") or {}).get("cnpj")
    ano  = c.get("anoCompra")
    seq  = c.get("sequencialCompra")
    if not (cnpj and ano and seq):
        return []
    ok, dados = _get(f"{BASE_PNCP}/v1/orgaos/{cnpj}/compras/{ano}/{seq}/itens")
    if PAUSA_ENTRE_CHAMADAS:
        time.sleep(PAUSA_ENTRE_CHAMADAS)
    return dados if (ok and isinstance(dados, list)) else []


def _motivo_exclusao(desc_norm: str):
    for palavra in PALAVRAS_EXCLUSAO:
        if palavra in desc_norm:
            return palavra
    for palavra in PALAVRAS_EXCLUSAO_INTEIRAS:
        if re.search(r'\b' + re.escape(palavra) + r'\b', desc_norm):
            return palavra + " (isolada)"
    return None


def _processar_itens(termo_norm, contratacao, itens):
    """Aplica filtros a uma lista de itens de UMA contratacao.
    Devolve (aceitos, descartados). Logica identica a de antes - so isolada
    para poder ser chamada apos a busca paralela.
    """
    mun = (contratacao.get("unidadeOrgao") or {}).get("municipioNome", "?")
    uf  = (contratacao.get("unidadeOrgao") or {}).get("ufSigla", "?")
    aceitos, descartados = [], []
    for item in itens:
        desc = item.get("descricao") or ""
        desc_norm = _norm(desc)
        preco = item.get("valorUnitarioEstimado")
        if termo_norm not in desc_norm or preco is None:
            continue
        try:
            preco_f = float(preco)
        except (ValueError, TypeError):
            continue
        registro = {
            "preco": preco_f,
            "descricao": desc,
            "orgao": f"{mun}/{uf}",
            "unidade": item.get("unidadeMedida") or "un",
        }
        motivo = _motivo_exclusao(desc_norm)
        if motivo:
            registro["motivo"] = f"contem '{motivo}' (servico/peca/acessorio)"
            descartados.append(registro)
        else:
            aceitos.append(registro)
    return aceitos, descartados


def _coletar_precos(termo: str, progresso=None, ufs=None, dias=None):
    """Itera contratacoes e busca os itens EM PARALELO, por lotes.
    PARA ao juntar ALVO_PRECOS_VALIDOS precos aceitos.
    Faz ate DUAS passadas: a 1a exige o termo no OBJETO da contratacao;
    se nao juntar precos suficientes, a 2a aceita objetos GENERICOS de
    compra de bens e filtra pelo termo item a item.
    Devolve (aceitos, descartados, n_contratacoes_vistas).
    """
    termo_norm = _norm(termo)
    aceitos: list[dict] = []
    descartados: list[dict] = []
    n_contratacoes = 0

    def processa_lote(lote_atual):
        """Busca os itens de todas as contratacoes do lote AO MESMO TEMPO."""
        nonlocal aceitos, descartados
        if not lote_atual:
            return
        # Dispara as buscas de itens em paralelo
        with ThreadPoolExecutor(max_workers=WORKERS_PARALELOS) as executor:
            futuros = {executor.submit(_buscar_itens, c): c for c in lote_atual}
            for fut in as_completed(futuros):
                c = futuros[fut]
                try:
                    itens = fut.result()
                except Exception:
                    itens = []
                a, d = _processar_itens(termo_norm, c, itens)
                aceitos.extend(a)
                descartados.extend(d)

    def passada(relaxada: bool) -> bool:
        """Roda uma passada completa. True = ja juntou precos suficientes."""
        nonlocal n_contratacoes
        rotulo = "ampliando (objetos genericos)" if relaxada else ""
        lote: list[dict] = []
        for c in _iterar_contratacoes(termo, ufs=ufs, dias=dias,
                                      relaxada=relaxada):
            n_contratacoes += 1
            lote.append(c)
            if progresso:
                mun = (c.get("unidadeOrgao") or {}).get("municipioNome", "?")
                uf  = (c.get("unidadeOrgao") or {}).get("ufSigla", "?")
                txt = f"{mun}/{uf} — {rotulo}" if rotulo else f"{mun}/{uf}"
                progresso(len(aceitos), ALVO_PRECOS_VALIDOS, txt)

            # Quando o lote enche, processa tudo de uma vez (em paralelo)
            if len(lote) >= LOTE_CONTRATACOES:
                processa_lote(lote)
                lote = []
                # Parada inteligente: ja tenho precos suficientes?
                if len(aceitos) >= ALVO_PRECOS_VALIDOS:
                    return True

        # Processa o que sobrou no ultimo lote (incompleto)
        processa_lote(lote)
        return len(aceitos) >= ALVO_PRECOS_VALIDOS

    # 1a passada: objeto exato. Se faltar preco, 2a passada: objetos genericos.
    if not passada(relaxada=False):
        passada(relaxada=True)

    return aceitos, descartados, n_contratacoes


# ---------------------------------------------------------------------------
# FUNCAO PRINCIPAL - a que o app.py vai chamar
# ---------------------------------------------------------------------------
def buscar_precos_pncp(
    termo: str,
    unidade: str = "un",
    quantidade_estimada: float | None = None,
    progresso=None,
    ufs: list | None = None,
    dias: int | None = None,
) -> dict:
    """
    Busca precos de um termo no PNCP e devolve estrutura no mesmo formato
    de ia_pesquisa_mercado.analisar().

    Parametros:
      termo               - o que pesquisar (ex: "notebook")
      unidade             - unidade de medida do item (ex: "un")
      quantidade_estimada - qtd para calcular subtotal (opcional)
      progresso           - funcao opcional (i, total, texto) p/ feedback
      ufs                 - lista de UFs (None = padrao do modulo;
                            lista vazia = Brasil todo)
      dias                - periodo em dias para tras (None = padrao)

    Retorno: dict com 'status_geral', 'itens_avaliados', 'fornecedores',
             'valor_total_estimado', 'parecer_narrativo', 'base_legal',
             'fonte' e 'diagnostico' (extras uteis).
    """
    _dias = dias if dias is not None else DIAS_PARA_TRAS
    aceitos, descartados_desc, n_contratacoes = _coletar_precos(
        termo, progresso, ufs=ufs, dias=dias
    )

    if not aceitos and n_contratacoes == 0:
        return {
            "status_geral":         ia_pesquisa_mercado.STATUS_PESQUISA["INVÁLIDA"],
            "itens_avaliados":      [],
            "fornecedores":         [],
            "valor_total_estimado": None,
            "parecer_narrativo": (
                f"Nenhuma contratacao encontrada no PNCP para o termo '{termo}' "
                f"nos ultimos {_dias} dias. Sugestao: usar termo mais generico, "
                f"ampliar o periodo ou incluir mais UFs."
            ),
            "base_legal": ["Art. 23, Lei 14.133/2021", "IN SEGES/MGI 65/2021"],
            "fonte": "PNCP",
            "diagnostico": {"contratacoes": 0, "aceitos": 0, "descartados": 0},
        }

    # Piso minimo (remove precos irrisorios antes de mandar ao calculo)
    precos_aceitos: list[float] = []
    excluidas_piso: list[dict] = []
    for x in aceitos:
        if x["preco"] < PISO_MINIMO_REAIS:
            excluidas_piso.append({
                "preco":  x["preco"],
                "motivo": f"{_fmt(x['preco'])} — abaixo do piso (R$ {PISO_MINIMO_REAIS:.0f}), irrisorio",
            })
        else:
            precos_aceitos.append(x["preco"])

    # Reaproveita o calculo que JA existe no sistema (mediana + saneamento)
    ref = ia_pesquisa_mercado.calcular_referencia(precos_aceitos)

    # Monta a lista de "fornecedores" = orgaos/municipios de referencia
    orgaos_vistos: dict = {}
    for x in aceitos:
        if x["orgao"] not in orgaos_vistos:
            orgaos_vistos[x["orgao"]] = {"nome": x["orgao"], "cnpj": "fonte: PNCP"}
    fornecedores = list(orgaos_vistos.values())

    # cotacoes_detalhadas no formato que o gerador de PDF espera
    cotacoes_detalhadas = [
        {"fornecedor": x["orgao"], "preco_unitario": x["preco"]}
        for x in aceitos if x["preco"] >= PISO_MINIMO_REAIS
    ]

    # Junta as exclusoes: por descricao + por piso + as do calcular_referencia
    cotacoes_excluidas = list(ref["cotacoes_excluidas"]) + excluidas_piso
    for d in descartados_desc:
        cotacoes_excluidas.append({"preco": d["preco"], "motivo": d["motivo"]})

    # Subtotal
    qtd = None
    if quantidade_estimada is not None:
        try:
            qtd = float(quantidade_estimada)
        except (ValueError, TypeError):
            qtd = None
    subtotal = (
        ref["preco_referencia"] * qtd
        if ref["preco_referencia"] is not None and qtd is not None
        else None
    )

    item_avaliado = {
        "item_id":             1,
        "descricao":           termo,
        "unidade":             unidade,
        "quantidade_estimada": qtd,
        "cotacoes_detalhadas": cotacoes_detalhadas,
        "preco_referencia":    ref["preco_referencia"],
        "cotacoes_validas":    ref["cotacoes_validas"],
        "cotacoes_excluidas":  cotacoes_excluidas,
        "status":              ref["status"],
        "subtotal_estimado":   subtotal,
    }

    # Status geral
    if ref["status"] == ia_pesquisa_mercado.STATUS_ITEM["VALIDO"]:
        status_geral = ia_pesquisa_mercado.STATUS_PESQUISA["VÁLIDA"]
    else:
        status_geral = ia_pesquisa_mercado.STATUS_PESQUISA["INVÁLIDA"]

    # Parecer automatico (sem IA - fatos objetivos da busca)
    n_val = len(ref["cotacoes_validas"])
    n_exc = len(cotacoes_excluidas)
    if ref["preco_referencia"] is not None:
        parecer = (
            f"Pesquisa de precos realizada junto ao Portal Nacional de Contratacoes "
            f"Publicas (PNCP), fonte prioritaria conforme a IN SEGES/MGI 65/2021 "
            f"(contratacoes similares de outros entes publicos). Foram consultadas "
            f"{n_contratacoes} contratacao(oes) dos ultimos {_dias} dias. "
            f"Apos saneamento (exclusao de servicos/pecas/acessorios e outliers), "
            f"{n_val} cotacao(oes) valida(s) compuseram a cesta, com {n_exc} exclusao(oes) "
            f"devidamente justificada(s). O preco de referencia foi calculado pela mediana, "
            f"resultando em {_fmt(ref['preco_referencia'])}/{unidade}."
        )
    else:
        parecer = (
            f"Pesquisa junto ao PNCP resultou em apenas {n_val} cotacao(oes) valida(s), "
            f"abaixo do minimo de {ia_pesquisa_mercado.MIN_COTACOES_VALIDAS} exigido. "
            f"Recomenda-se ampliar o periodo, usar termo mais generico, ou complementar "
            f"com outras fontes (IN SEGES/MGI 65/2021)."
        )

    return {
        "status_geral":          status_geral,
        "itens_avaliados":       [item_avaliado],
        "fornecedores":          fornecedores,
        "valor_total_estimado":  subtotal,
        "parecer_narrativo":     parecer,
        "base_legal": ["Art. 23, Lei 14.133/2021", "IN SEGES/MGI 65/2021"],
        "fonte": "PNCP",
        "diagnostico": {
            "contratacoes": n_contratacoes,
            "aceitos":      len(precos_aceitos),
            "descartados":  len(descartados_desc) + len(excluidas_piso),
        },
    }


def _fmt(v) -> str:
    """Formata em R$ (fallback simples, caso ia_utils nao esteja acessivel)."""
    try:
        from ia_utils import fmt_brl
        return fmt_brl(v)
    except Exception:
        try:
            return "R$ " + f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except (ValueError, TypeError):
            return str(v)
