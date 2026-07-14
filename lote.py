#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Runner de lote do IA-Licita.
-----------------------------
Audita varios editais de uma vez e gera a estatistica de validacao
(% de editais com inconformidade, % com achado grave, achados mais comuns,
distribuicao de risco) + um painel HTML. E o numero que sustenta a venda.

Uso:
    python3 lote.py                # usa o manifesto padrao (editais ja auditados)
    python3 lote.py pasta/         # audita todos os PDFs da pasta (camada automatica)
"""
import os, sys, json, glob, datetime, html
from collections import Counter
from analisador import extrair_texto, analisar, aplicar_pareceres, indice_de_risco, precisa_ocr

AQUI = os.path.dirname(os.path.abspath(__file__))
BASE_RAG = os.path.join(AQUI, "base_juridica.json")

# manifesto padrao: (pdf, pareceres_ou_None, rotulo)
MANIFESTO = [
    ("edital_amostra.pdf", None, "Amostra (ficticio)"),
    ("edital_real.pdf", "pareceres_edital_real.json", "Municipal - Santa Teresinha/BA"),
    ("edital2.pdf", "pareceres_edital2.json", "Federal - TRF3 (PE 027/2024)"),
]

def carregar_regras():
    with open(os.path.join(AQUI, "regras_14133.json"), encoding="utf-8") as f:
        return json.load(f)["regras"]

def auditar(pdf, pareceres, regras):
    texto, paginas = extrair_texto(pdf)
    if precisa_ocr(texto, paginas):
        return {"pdf": os.path.basename(pdf), "paginas": len(paginas), "ocr": True,
                "risco": None, "nivel": "SEM TEXTO", "n_inconformidades": 0,
                "n_alertas": 0, "n_alta": 0, "categorias_inc": [], "itens_inc": []}
    apont = analisar(texto, regras)
    if pareceres and os.path.exists(os.path.join(AQUI, pareceres)):
        apont = aplicar_pareceres(apont, os.path.join(AQUI, pareceres), BASE_RAG)
    pct, nivel = indice_de_risco(apont)
    inc = [a for a in apont if a["status"] == "inconformidade"]
    ale = [a for a in apont if a["status"] == "alerta"]
    return {
        "pdf": os.path.basename(pdf), "paginas": len(paginas),
        "risco": pct, "nivel": nivel,
        "n_inconformidades": len(inc), "n_alertas": len(ale),
        "n_alta": sum(1 for a in inc if a["severidade"] == "alta"),
        "categorias_inc": [a["categoria"] for a in inc],
        "itens_inc": [{"item": a["item"], "severidade": a["severidade"]} for a in inc],
    }

def montar_manifesto(args):
    if args and os.path.isdir(args[0]):
        pdfs = sorted(glob.glob(os.path.join(args[0], "*.pdf")))
        return [(p, None, os.path.basename(p)) for p in pdfs]
    return [(os.path.join(AQUI, pdf), par, rot) for pdf, par, rot in MANIFESTO
            if os.path.exists(os.path.join(AQUI, pdf))]

def agregar(resultados):
    analisados = [r for r in resultados if not r.get("ocr")]
    n = len(analisados)            # base de calculo: so editais com texto analisavel
    n_sem_texto = len(resultados) - n
    com_inc = sum(1 for r in analisados if r["n_inconformidades"] > 0)
    com_alta = sum(1 for r in analisados if r["n_alta"] > 0)
    com_apont = sum(1 for r in analisados if r["n_inconformidades"] + r["n_alertas"] > 0)
    risco_medio = round(sum(r["risco"] for r in analisados) / n) if n else 0
    cats = Counter()
    for r in analisados:
        cats.update(r["categorias_inc"])
    return {
        "n_editais": len(resultados),
        "n_analisados": n,
        "n_sem_texto": n_sem_texto,
        "pct_com_inconformidade": round(100 * com_inc / n) if n else 0,
        "pct_com_achado_grave": round(100 * com_alta / n) if n else 0,
        "pct_com_qualquer_apontamento": round(100 * com_apont / n) if n else 0,
        "risco_medio": risco_medio,
        "total_inconformidades": sum(r["n_inconformidades"] for r in analisados),
        "achados_mais_comuns": cats.most_common(8),
    }

# ----------------------------------------------------------------- painel HTML
def painel_html(resultados, agg):
    e = html.escape
    data = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    cards = [
        ("Editais auditados", agg["n_editais"], "#1F4E79"),
        ("% com inconformidade", f'{agg["pct_com_inconformidade"]}%', "#C0392B"),
        ("% com achado grave", f'{agg["pct_com_achado_grave"]}%', "#C0392B"),
        ("Risco medio", f'{agg["risco_medio"]}/100', "#2E75B6"),
    ]
    cards_html = "".join(
        f'<div class="card"><div class="n" style="color:{c}">{v}</div><div class="l">{e(t)}</div></div>'
        for t, v, c in cards)

    def cor_nivel(n): return {"BAIXO": "#27AE60", "MEDIO": "#E67E22", "ALTO": "#C0392B"}.get(n, "#888")
    linhas = ""
    for r in sorted(resultados, key=lambda x: (x["risco"] if x.get("risco") is not None else -1), reverse=True):
        if r.get("ocr"):
            linhas += f"""<tr><td>{e(r['pdf'])}</td>
              <td style="text-align:center;color:#888">&mdash;</td>
              <td colspan="3" style="color:#888">Sem texto extraivel (necessita OCR)</td></tr>"""
            continue
        badge_alta = f'<span class="pill" style="background:#C0392B">{r["n_alta"]} grave(s)</span>' if r["n_alta"] else ""
        linhas += f"""<tr>
          <td>{e(r['pdf'])}</td>
          <td style="text-align:center"><b style="color:{cor_nivel(r['nivel'])}">{r['risco']}</b></td>
          <td style="text-align:center">{r['n_inconformidades']}</td>
          <td style="text-align:center">{r['n_alertas']}</td>
          <td>{badge_alta}</td>
        </tr>"""

    barras = ""
    maxc = agg["achados_mais_comuns"][0][1] if agg["achados_mais_comuns"] else 1
    for cat, q in agg["achados_mais_comuns"]:
        barras += f"""<div class="brow"><div class="blab">{e(cat)}</div>
          <div class="btrack"><div class="bfill" style="width:{100*q/maxc}%"></div></div>
          <div class="bval">{q}</div></div>"""

    return f"""<!DOCTYPE html><html lang="pt-br"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Painel de validacao - IA-Licita</title><style>
  body {{ font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif; color:#1f2d3d; background:#f5f7fa; margin:0; }}
  .wrap {{ max-width:920px; margin:0 auto; padding:28px 20px 60px; }}
  h1 {{ color:#1F4E79; font-size:23px; margin:0 0 4px; }}
  .sub {{ color:#5a6b7b; font-size:13px; margin-bottom:22px; }}
  .cards {{ display:flex; gap:12px; flex-wrap:wrap; margin-bottom:26px; }}
  .card {{ flex:1; min-width:150px; background:#fff; border:1px solid #e2e8f0; border-radius:10px; padding:16px; text-align:center; }}
  .card .n {{ font-size:30px; font-weight:800; }}
  .card .l {{ font-size:12px; color:#5a6b7b; margin-top:4px; }}
  h2 {{ font-size:15px; color:#1F4E79; margin:24px 0 10px; }}
  table {{ width:100%; border-collapse:collapse; background:#fff; border:1px solid #e2e8f0; border-radius:10px; overflow:hidden; }}
  th,td {{ padding:11px 12px; border-top:1px solid #eef2f6; font-size:13px; text-align:left; }}
  th {{ background:#1F4E79; color:#fff; border:none; font-size:12px; }}
  .pill {{ color:#fff; font-size:11px; padding:3px 8px; border-radius:20px; }}
  .brow {{ display:flex; align-items:center; gap:10px; margin:6px 0; font-size:13px; }}
  .blab {{ width:230px; color:#445; }}
  .btrack {{ flex:1; background:#eef2f6; border-radius:6px; height:14px; overflow:hidden; }}
  .bfill {{ height:100%; background:#2E75B6; }}
  .bval {{ width:24px; text-align:right; color:#5a6b7b; }}
  .nota {{ font-size:12px; color:#7a8a99; margin-top:22px; line-height:1.6; }}
</style></head><body><div class="wrap">
  <h1>Painel de validacao &mdash; auditoria em lote</h1>
  <div class="sub">{agg['n_editais']} edital(is) processado(s) &middot; {agg['n_analisados']} analisado(s)
    {('&middot; ' + str(agg['n_sem_texto']) + ' sem texto (OCR)') if agg['n_sem_texto'] else ''}
    &middot; Lei 14.133/2021 &middot; gerado em {data} &middot; IA-Licita (piloto)</div>
  <div class="cards">{cards_html}</div>
  <h2>Editais (ordenados por risco)</h2>
  <table><tr><th>Edital</th><th>Risco</th><th>Inconformidades</th><th>Alertas</th><th>Graves</th></tr>{linhas}</table>
  <h2>Categorias de inconformidade mais frequentes</h2>
  {barras or '<div class="sub">Nenhuma inconformidade no lote.</div>'}
  <div class="nota"><b>Argumento de venda:</b> dos {agg['n_analisados']} editais analisados,
    {agg['pct_com_inconformidade']}% apresentaram ao menos uma inconformidade e
    {agg['pct_com_achado_grave']}% continham achado de alta severidade. Amostra de demonstracao;
    a estatistica ganha robustez ao processar dezenas de editais reais.
    Ferramenta de apoio &mdash; apontamentos sujeitos a validacao juridica.</div>
</div></body></html>"""

def main():
    args = sys.argv[1:]
    regras = carregar_regras()
    manifesto = montar_manifesto(args)
    resultados = [auditar(pdf, par, regras) for pdf, par, rot in manifesto]
    agg = agregar(resultados)

    with open(os.path.join(AQUI, "lote_resultado.json"), "w", encoding="utf-8") as f:
        json.dump({"agregado": agg, "editais": resultados}, f, ensure_ascii=False, indent=2)
    with open(os.path.join(AQUI, "painel_lote.html"), "w", encoding="utf-8") as f:
        f.write(painel_html(resultados, agg))

    print(f"\n=== LOTE: {agg['n_editais']} editais ({agg['n_analisados']} analisados, "
          f"{agg['n_sem_texto']} sem texto/OCR) ===")
    print(f"  % com inconformidade : {agg['pct_com_inconformidade']}%")
    print(f"  % com achado grave   : {agg['pct_com_achado_grave']}%")
    print(f"  risco medio          : {agg['risco_medio']}/100")
    print(f"  total inconformidades: {agg['total_inconformidades']}")
    print("  achados mais comuns  :", ", ".join(f"{c} ({q})" for c, q in agg["achados_mais_comuns"]))
    print("\nPainel: painel_lote.html | Dados: lote_resultado.json")

if __name__ == "__main__":
    main()
