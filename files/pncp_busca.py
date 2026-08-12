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
from datetime import datetime, timedelta

# Reaproveita o calculo que ja existe no sistema (nao duplica logica)
import ia_pesquisa_mercado

# ---------------------------------------------------------------------------
# CONFIGURACOES
# ---------------------------------------------------------------------------
DIAS_PARA_TRAS       = 90
MODALIDADES          = [6, 8]   # 6 = Pregao Eletronico ; 8 = Dispensa
MAX_CONTRATACOES     = 60
PAUSA_ENTRE_CHAMADAS = 0.3
TAMANHO_PAGINA       = 50

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


def _listar_contratacoes(termo: str) -> list[dict]:
    ini = (datetime.now() - timedelta(days=DIAS_PARA_TRAS)).strftime("%Y%m%d")
    fim = datetime.now().strftime("%Y%m%d")
    termo_norm = _norm(termo)
    encontradas: list[dict] = []
    for modalidade in MODALIDADES:
        pagina = 1
        while len(encontradas) < MAX_CONTRATACOES:
            params = urllib.parse.urlencode({
                "dataInicial": ini, "dataFinal": fim,
                "codigoModalidadeContratacao": modalidade,
                "pagina": pagina, "tamanhoPagina": TAMANHO_PAGINA,
            })
            ok, dados = _get(f"{BASE_CONSULTA}/v1/contratacoes/publicacao?{params}")
            time.sleep(PAUSA_ENTRE_CHAMADAS)
            if not ok or not isinstance(dados, dict):
                break
            lista = dados.get("data") or []
            if not lista:
                break
            for c in lista:
                if termo_norm in _norm(c.get("objetoCompra")):
                    encontradas.append(c)
                    if len(encontradas) >= MAX_CONTRATACOES:
                        break
            if pagina >= (dados.get("totalPaginas") or 1):
                break
            pagina += 1
    return encontradas


def _buscar_itens(c: dict) -> list[dict]:
    cnpj = (c.get("orgaoEntidade") or {}).get("cnpj")
    ano  = c.get("anoCompra")
    seq  = c.get("sequencialCompra")
    if not (cnpj and ano and seq):
        return []
    ok, dados = _get(f"{BASE_PNCP}/v1/orgaos/{cnpj}/compras/{ano}/{seq}/itens")
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


def _coletar_precos(termo: str, contratacoes: list[dict], progresso=None):
    """Coleta itens. Devolve (aceitos, descartados_por_descricao).
    'progresso' e uma funcao opcional (i, total, texto) para feedback no app.
    """
    termo_norm = _norm(termo)
    aceitos: list[dict] = []
    descartados: list[dict] = []
    total = len(contratacoes)
    for i, c in enumerate(contratacoes, 1):
        mun = (c.get("unidadeOrgao") or {}).get("municipioNome", "?")
        uf  = (c.get("unidadeOrgao") or {}).get("ufSigla", "?")
        if progresso:
            progresso(i, total, f"{mun}/{uf}")
        for item in _buscar_itens(c):
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


# ---------------------------------------------------------------------------
# FUNCAO PRINCIPAL - a que o app.py vai chamar
# ---------------------------------------------------------------------------
def buscar_precos_pncp(
    termo: str,
    unidade: str = "un",
    quantidade_estimada: float | None = None,
    progresso=None,
) -> dict:
    """
    Busca precos de um termo no PNCP e devolve estrutura no mesmo formato
    de ia_pesquisa_mercado.analisar().

    Parametros:
      termo               - o que pesquisar (ex: "notebook")
      unidade             - unidade de medida do item (ex: "un")
      quantidade_estimada - qtd para calcular subtotal (opcional)
      progresso           - funcao opcional (i, total, texto) p/ feedback

    Retorno: dict com 'status_geral', 'itens_avaliados', 'fornecedores',
             'valor_total_estimado', 'parecer_narrativo', 'base_legal',
             'fonte' e 'diagnostico' (extras uteis).
    """
    contratacoes = _listar_contratacoes(termo)

    if not contratacoes:
        return {
            "status_geral":         ia_pesquisa_mercado.STATUS_PESQUISA["INVÁLIDA"],
            "itens_avaliados":      [],
            "fornecedores":         [],
            "valor_total_estimado": None,
            "parecer_narrativo": (
                f"Nenhuma contratacao encontrada no PNCP para o termo '{termo}' "
                f"nos ultimos {DIAS_PARA_TRAS} dias. Sugestao: usar termo mais generico."
            ),
            "base_legal": ["Art. 23, Lei 14.133/2021", "IN SEGES/MGI 65/2021"],
            "fonte": "PNCP",
            "diagnostico": {"contratacoes": 0, "aceitos": 0, "descartados": 0},
        }

    aceitos, descartados_desc = _coletar_precos(termo, contratacoes, progresso)

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
            f"{len(contratacoes)} contratacao(oes) dos ultimos {DIAS_PARA_TRAS} dias. "
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
            "contratacoes": len(contratacoes),
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
