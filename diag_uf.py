#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
 DIAGNOSTICO RAPIDO - o parametro 'uf' funciona na API do PNCP?
 RM IA-Licita / RM Vertice Digital
=============================================================================
 Roda em SEGUNDOS. Faz poucas chamadas e responde:
   1. A busca SEM uf funciona? (controle)
   2. A busca COM uf=SP funciona?
   3. Se sim, os resultados sao mesmo so de SP?
   4. Quantas contratacoes tem "notebook" no OBJETO vs. objetos genericos?

 COMO RODAR:
     python3 ~/Downloads/diag_uf.py
 (nao precisa estar na pasta do projeto; nao importa nada do app)

 Cole TODA a saida para o Claude.
=============================================================================
"""
import urllib.request
import urllib.parse
import json
import ssl
import unicodedata
from datetime import datetime, timedelta

_CTX = ssl.create_default_context()
_H = {"Accept": "application/json", "User-Agent": "RM-IA-Licita/diag"}
BASE = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"

ini = (datetime.now() - timedelta(days=90)).strftime("%Y%m%d")
fim = datetime.now().strftime("%Y%m%d")


def _norm(s):
    if not s:
        return ""
    return unicodedata.normalize("NFD", str(s)).encode("ascii", "ignore").decode().lower()


def chamar(campos, rotulo):
    params = urllib.parse.urlencode(campos)
    url = f"{BASE}?{params}"
    print(f"\n>>> {rotulo}")
    print(f"    {url}")
    req = urllib.request.Request(url, headers=_H)
    try:
        with urllib.request.urlopen(req, context=_CTX, timeout=40) as r:
            d = json.loads(r.read().decode("utf-8", errors="replace"))
            print(f"    STATUS 200 OK | totalRegistros={d.get('totalRegistros')} "
                  f"| totalPaginas={d.get('totalPaginas')} | nesta pagina={len(d.get('data') or [])}")
            return d
    except urllib.error.HTTPError as e:
        corpo = ""
        try:
            corpo = e.read().decode("utf-8", errors="replace")[:200]
        except Exception:
            pass
        print(f"    ERRO HTTP {e.code}  {corpo}")
        return None
    except Exception as e:
        print(f"    FALHA: {type(e).__name__}: {str(e)[:120]}")
        return None


print("=" * 72)
print("  DIAGNOSTICO DO PARAMETRO 'uf' NA API DO PNCP")
print("=" * 72)
print(f"Periodo: {ini} a {fim} | modalidade 6 (Pregao Eletronico)")

base_campos = {
    "dataInicial": ini, "dataFinal": fim,
    "codigoModalidadeContratacao": 6,
    "pagina": 1, "tamanhoPagina": 50,
}

# --- TESTE 1: sem uf (controle) ---
d_sem = chamar(dict(base_campos), "TESTE 1 - SEM o parametro uf (controle)")

# --- TESTE 2: com uf=SP ---
d_com = chamar({**base_campos, "uf": "SP"}, "TESTE 2 - COM uf=SP")

# --- TESTE 3: nomes alternativos do parametro ---
for nome in ["ufSigla", "siglaUf", "estado"]:
    chamar({**base_campos, nome: "SP"}, f"TESTE 3 - COM {nome}=SP (nome alternativo)")

# --- ANALISE: os resultados de uf=SP sao mesmo so de SP? ---
print("\n" + "=" * 72)
print("  ANALISE DOS RESULTADOS")
print("=" * 72)

if d_com and (d_com.get("data")):
    ufs = {}
    for c in d_com["data"]:
        u = (c.get("unidadeOrgao") or {}).get("ufSigla", "?")
        ufs[u] = ufs.get(u, 0) + 1
    print(f"\n  Distribuicao de UF nos resultados de 'uf=SP': {ufs}")
    if len(ufs) == 1 and "SP" in ufs:
        print("  => O FILTRO uf FUNCIONA (so veio SP).")
    else:
        print("  => O FILTRO uf NAO esta filtrando (veio UF misturada!).")
else:
    print("\n  'uf=SP' nao retornou dados -> o parametro provavelmente QUEBRA a busca.")

# --- Quantas tem "notebook" no OBJETO? ---
print("\n  --- Quao raro e o termo aparecer no OBJETO da contratacao? ---")
for rotulo, d in [("SEM uf", d_sem), ("COM uf=SP", d_com)]:
    if not d or not d.get("data"):
        print(f"  {rotulo}: sem dados")
        continue
    lista = d["data"]
    com_termo = sum(1 for c in lista if "notebook" in _norm(c.get("objetoCompra")))
    genericos = sum(1 for c in lista
                    if any(g in _norm(c.get("objetoCompra"))
                           for g in ["aquisicao", "compra", "fornecimento",
                                     "equipamento", "material", "registro de precos"]))
    print(f"  {rotulo}: de {len(lista)} contratacoes desta pagina -> "
          f"{com_termo} com 'notebook' no objeto | {genericos} com objeto generico")

print("\n" + "=" * 72)
print("  FIM - copie TODA esta saida e cole para o Claude.")
print("=" * 72)
