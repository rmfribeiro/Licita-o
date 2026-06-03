#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IA-Licita - Prototipo do analisador de editais (piloto)
--------------------------------------------------------
Fluxo: PDF -> extracao de texto -> checagem das regras (Lei 14.133/2021)
       -> indice de risco -> relatorio explicavel em HTML.

Uso:
    python3 analisador.py <edital.pdf> [saida.html]

Observacoes:
- A camada de IA/LLM (analise semantica) e isolada na funcao analise_semantica().
  No piloto real, e ali que se pluga a chamada de API (Claude ou equivalente).
  Neste prototipo offline, as regras "semanticas" sao sinalizadas para revisao
  e alguns "detectores de red flag" por padrao (regex) demonstram o conceito.
"""
import sys, json, re, unicodedata, datetime, html, os

# ---------------------------------------------------------------- utilidades
def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")

def norm(s):
    return strip_accents(s).lower()

def contem(texto, termo):
    """Casa o termo por limite de palavra (evita 'ME' dentro de 'equipamentos' e
    'marca' dentro de 'demarcacao'), com espacamento flexivel entre palavras."""
    nt = re.sub(r"\s+", " ", norm(texto))
    ntermo = re.sub(r"\s+", " ", norm(termo)).strip()
    if not ntermo:
        return False
    padrao = r"\b" + r"\s+".join(re.escape(w) for w in ntermo.split()) + r"\b"
    return re.search(padrao, nt) is not None

def extrair_texto(pdf_path):
    # caminho rapido: se existir um .txt ao lado (ex.: gerado por pdftotext), usa-o.
    sidecar = os.path.splitext(pdf_path)[0] + ".txt"
    if os.path.exists(sidecar):
        with open(sidecar, encoding="utf-8", errors="ignore") as f:
            texto = f.read()
        paginas = [(i + 1, p) for i, p in enumerate(texto.split("\f"))]
        return texto, paginas
    import pdfplumber
    paginas = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            t = page.extract_text() or ""
            paginas.append((i, t))
    texto = "\n".join(t for _, t in paginas)
    # se o PDF for escaneado (sem texto), aqui entraria o OCR gerenciado
    return texto, paginas

def precisa_ocr(texto, paginas):
    """Detecta PDF escaneado / sem camada de texto: ha paginas, mas quase nenhum
    caractere extraivel. Nesse caso a analise nao deve pontuar (precisa de OCR)."""
    n_pag = max(1, len(paginas))
    return len(texto.strip()) < 200 or (len(texto.strip()) / n_pag) < 30

def achar_trecho(texto, termo, janela=90):
    nt, ntermo = norm(texto), norm(termo)
    idx = nt.find(ntermo)
    if idx == -1:
        return None
    ini = max(0, idx - janela)
    fim = min(len(texto), idx + len(termo) + janela)
    trecho = texto[ini:fim].replace("\n", " ").strip()
    return ("..." if ini > 0 else "") + trecho + ("..." if fim < len(texto) else "")

# ------------------------------------------------- detectores de "red flag"
# Heuristicas simples que demonstram a deteccao de problemas pela presenca de
# padroes (no piloto real, complementadas/substituidas pela IA semantica).
def detectores_red_flag(texto):
    achados = []
    nt = re.sub(r"\s+", " ", norm(texto))  # colapsa quebras de linha do PDF

    # Garantia de execucao: teto de 10% (art. 98); >5% exige justificativa
    m = re.search(r"garantia de execu[cç][aã]o[^.\n]{0,80}?(\d{1,3})\s*%", nt)
    if m:
        pct = min(int(m.group(1)), 100)
        # justificativa precisa estar perto da clausula de garantia, nao em qualquer
        # ponto do edital (evita falso negativo por 'risco' citado em outra secao)
        janela = nt[max(0, m.start() - 250): m.end() + 250]
        tem_justif = re.search(r"(complexidade|risco|grande vulto|justific|seguro-garantia)", janela)
        if pct > 10:
            achados.append(("R10",
                f"Garantia de execucao de {pct}% excede o teto de 10% do art. 98. A majoracao ate 30% "
                "so se admite em obras/servicos de engenharia de grande vulto com seguro-garantia e "
                "clausula de retomada (art. 99).",
                m.group(0)))
        elif pct > 5 and not tem_justif:
            achados.append(("R10",
                f"Garantia de execucao de {pct}% (acima do padrao de 5%) sem justificativa visivel de "
                "complexidade tecnica e riscos, exigida pelo art. 98 para a majoracao ate 10%. "
                "Verificar a motivacao no processo.",
                m.group(0)))

    # Visita tecnica obrigatoria sem alternativa de declaracao
    visita_obrig = re.search(r"(visita|vistoria)[^.\n]{0,60}(obrigatori|sera exigid|devera comparecer)", nt)
    tem_alternativa = re.search(r"(visita|vistoria)[^.]{0,400}declara[cç][aã]o", nt)
    if visita_obrig and not tem_alternativa:
        achados.append(("R11",
            "Visita/vistoria aparentemente obrigatoria sem previsao de declaracao substitutiva. "
            "Tende a restringir a competicao (art. 63).",
            achar_trecho(texto, "visita") or achar_trecho(texto, "vistoria") or ""))

    # Atestado exigindo quantitativos elevados (>50%)
    m2 = re.search(r"atestad[^.\n]{0,160}?(\d{2,3})\s*%", nt)
    if m2 and int(m2.group(1)) > 50:
        achados.append(("R07",
            f"Exigencia de atestado com {m2.group(1)}% dos quantitativos do objeto. "
            "Em regra a exigencia limita-se a parcelas relevantes e ate ~50%; acima disso, restringe a competicao.",
            m2.group(0)))

    return achados

# --------------------------------------------- ponto de integracao da IA/LLM
def analise_semantica(texto, regra):
    """
    HOOK DE IA. No piloto real, esta funcao monta o prompt abaixo, chama a API
    do modelo (com RAG sobre a base juridica) e retorna o parecer estruturado.
    Aqui, retorna None (sinaliza 'requer analise') para manter o prototipo offline.
    """
    _prompt_template = (
        "Voce e um auditor de licitacoes. Com base na Lei 14.133/2021 "
        f"({regra['base_legal']}), avalie se o edital atende ao seguinte ponto:\n"
        f"\"{regra['o_que_checar']}\"\n"
        "Responda em JSON: {conforme: bool, justificativa, trecho_do_edital, risco}.\n"
        "Cite literalmente o trecho do edital que fundamenta sua conclusao."
    )
    return None  # <- substituir por chamada de API no piloto real

# -------------------------------------------------------------- motor de regras
PESO = {"alta": 3, "media": 2, "baixa": 1}

def analisar(texto, regras):
    apontamentos = []
    red = {rid: msg_trecho for rid, *msg_trecho in detectores_red_flag(texto)}

    for r in regras:
        encontrados = [t for t in r["termos"] if contem(texto, t)]
        trecho = None
        for t in r["termos"]:
            trecho = achar_trecho(texto, t)
            if trecho:
                break

        status, detalhe = None, ""
        # red flag especifico tem prioridade
        if r["id"] in red:
            status = "inconformidade"
            detalhe = red[r["id"]][0]
            trecho = red[r["id"]][1] or trecho
        elif r["tipo"] == "automatica":
            if encontrados:
                status = "ok"
                detalhe = "Termos relacionados localizados no edital. Recomenda-se validacao humana."
            else:
                status = "alerta"
                detalhe = "Nao foram localizados termos relacionados a este requisito - possivel ausencia."
        else:  # semantica
            parecer = analise_semantica(texto, r)
            if parecer is None:
                status = "revisar"
                detalhe = ("Requer analise semantica (IA + jurista): a presenca de termos nao garante "
                           "conformidade. Termos localizados: " + (", ".join(encontrados) if encontrados else "nenhum"))
            else:
                status = "ok" if parecer.get("conforme") else "inconformidade"
                detalhe = parecer.get("justificativa", "")

        apontamentos.append({
            "id": r["id"], "categoria": r["categoria"], "item": r["item"],
            "base_legal": r["base_legal"], "severidade": r["severidade"],
            "tipo": r["tipo"], "status": status, "detalhe": detalhe,
            "trecho": trecho or "", "fonte": "Automatico", "fundamento": "",
        })
    return apontamentos

def aplicar_pareceres(apont, pareceres_path, base_rag_path):
    """Versao a partir de arquivo (modo offline/demonstracao)."""
    with open(pareceres_path, encoding="utf-8") as f:
        pareceres = json.load(f)["pareceres"]
    return aplicar_pareceres_lista(apont, pareceres, base_rag_path)

def aplicar_pareceres_lista(apont, pareceres, base_rag_path):
    """Mescla a camada de IA (pareceres semanticos) e anexa o fundamento legal
    recuperado via RAG. Recebe a lista de achados (de arquivo ou da IA ao vivo)."""
    rag = None
    if base_rag_path and os.path.exists(base_rag_path):
        try:
            from rag import BaseRAG
            rag = BaseRAG(base_rag_path)
        except Exception as e:
            print("Aviso: RAG indisponivel:", e)
    try:
        from ia_semantica import STATUS_VALIDOS as _st_ok, SEV_VALIDAS as _sev_ok
    except ImportError:
        _st_ok  = {"inconformidade", "alerta", "revisar", "ok"}
        _sev_ok = {"alta", "media", "baixa"}
    novos = []
    for pz in pareceres:
        sev    = str(pz.get("severidade", "media")).strip().lower()
        status = str(pz.get("status",     "revisar")).strip().lower()
        fundamento = ""
        if rag and pz.get("consulta_rag"):
            hits = rag.buscar(pz["consulta_rag"], k=1)
            if hits:
                art, sc, txt = hits[0]
                fundamento = f"Art. {art}: {txt}"
        novos.append({
            "id":        str(pz.get("id", f"P{len(novos)+1}")).strip(),
            "categoria": str(pz.get("categoria", "")).strip() or "Analise semantica",
            "item":      str(pz.get("item", "(sem titulo)")).strip(),
            "base_legal": "Lei 14.133/2021",
            "severidade": sev    if sev    in _sev_ok else "media",
            "tipo":      "semantica",
            "status":    status  if status in _st_ok  else "revisar",
            "detalhe":   str(pz.get("detalhe", "")).strip(),
            "trecho":    str(pz.get("trecho") or ""),
            "fonte":     "IA (semantica)",
            "fundamento": fundamento,
        })
    # IA sobrescreve itens automáticos com mesmo ID, mas apenas quando encontrou algo
    # acionável (alerta/inconformidade/revisar). 'ok' da IA não suprime o 'revisar'
    # automático — preserva comportamento conservador.
    novos_acionaveis  = [n for n in novos if n["status"] != "ok"]
    ids_ia_acionaveis = {n["id"] for n in novos_acionaveis}
    apont_restante    = [a for a in apont if a["id"] not in ids_ia_acionaveis]
    return novos_acionaveis + apont_restante

def indice_de_risco(apont):
    # pontos de risco = soma dos pesos de inconformidades e alertas
    risco = sum(PESO.get(a["severidade"], 0) for a in apont if a["status"] in ("inconformidade", "alerta"))
    max_risco = sum(PESO.get(a["severidade"], 0) for a in apont)
    pct = round(100 * risco / max_risco) if max_risco else 0
    nivel = "BAIXO" if pct < 25 else "MEDIO" if pct < 55 else "ALTO"
    return pct, nivel

# ----------------------------------------------------------------- relatorio
COR_STATUS = {
    "inconformidade": ("#C0392B", "Inconformidade"),
    "alerta": ("#E67E22", "Alerta - possivel ausencia"),
    "revisar": ("#2E75B6", "Revisar (IA/jurista)"),
    "ok": ("#27AE60", "Presente"),
}
COR_SEV = {"alta": "#C0392B", "media": "#E67E22", "baixa": "#7F8C8D"}

def gerar_html(apont, pct, nivel, nome_arquivo, n_paginas):
    e = html.escape
    n_inc = sum(1 for a in apont if a["status"] == "inconformidade")
    n_ale = sum(1 for a in apont if a["status"] == "alerta")
    n_rev = sum(1 for a in apont if a["status"] == "revisar")
    n_ok = sum(1 for a in apont if a["status"] == "ok")
    cor_nivel = {"BAIXO": "#27AE60", "MEDIO": "#E67E22", "ALTO": "#C0392B"}.get(nivel, "#888")
    # nivel de atencao: dirigido pela PIOR severidade entre inconformidades/alertas,
    # distinto do indice numerico (que mede risco agregado de nulidade do merito)
    inc_ale = [a for a in apont if a["status"] in ("inconformidade", "alerta")]
    n_alta_g = sum(1 for a in inc_ale if a["severidade"] == "alta")
    n_media_g = sum(1 for a in inc_ale if a["severidade"] == "media")
    nivel_at = "ALTO" if n_alta_g else ("MEDIO" if n_media_g else "BAIXO")
    cor_at = {"BAIXO": "#27AE60", "MEDIO": "#E67E22", "ALTO": "#C0392B"}[nivel_at]
    det_at = (f"{n_alta_g} achado(s) de alta severidade" if n_alta_g else
              (f"{n_media_g} de severidade media" if n_media_g else "sem achados que exijam correcao"))
    data = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    linhas = ""
    ordem = {"inconformidade": 0, "alerta": 1, "revisar": 2, "ok": 3}
    for a in sorted(apont, key=lambda x: (ordem.get(x["status"], 4), x["fonte"] != "IA (semantica)", str(x["id"]))):
        cor, rotulo = COR_STATUS.get(a["status"], ("#888", a["status"]))
        trecho = f'<div class="trecho">&ldquo;{e(a["trecho"])}&rdquo;</div>' if a["trecho"] else ""
        fundamento = f'<div class="fund"><b>Fundamento (recuperado via RAG):</b> {e(a["fundamento"][:320])}{"..." if len(a["fundamento"])>320 else ""}</div>' if a.get("fundamento") else ""
        fonte_cor = "#6C3483" if a["fonte"].startswith("IA") else "#5a6b7b"
        fonte_tag = f'<span class="fonte" style="color:{fonte_cor}">{e(a["fonte"])}</span>'
        linhas += f"""
        <tr>
          <td class="id">{e(a['id'])}</td>
          <td>
            <div class="item">{e(a['item'])} &nbsp;{fonte_tag}</div>
            <div class="cat">{e(a['categoria'])} &middot; <span style="color:{COR_SEV.get(a['severidade'], '#7F8C8D')}">severidade {e(a['severidade'])}</span></div>
            <div class="detalhe">{e(a['detalhe'])}</div>
            {trecho}
            {fundamento}
            <div class="base">{e(a['base_legal'])}</div>
          </td>
          <td><span class="badge" style="background:{cor}">{e(rotulo)}</span></td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="pt-br"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Relatorio de Conformidade - IA-Licita</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif; color:#1f2d3d; margin:0; background:#f5f7fa; }}
  .wrap {{ max-width: 920px; margin: 0 auto; padding: 28px 20px 60px; }}
  header {{ border-bottom: 4px solid #2E75B6; padding-bottom: 14px; margin-bottom: 22px; }}
  h1 {{ color:#1F4E79; font-size: 24px; margin:0 0 4px; }}
  .sub {{ color:#5a6b7b; font-size: 14px; }}
  .cards {{ display:flex; gap:12px; flex-wrap:wrap; margin: 18px 0 26px; }}
  .card {{ flex:1; min-width:120px; background:#fff; border:1px solid #e2e8f0; border-radius:10px; padding:14px; text-align:center; }}
  .card .n {{ font-size: 26px; font-weight: 700; }}
  .card .l {{ font-size: 12px; color:#5a6b7b; margin-top:4px; }}
  .risco {{ background:#fff; border:1px solid #e2e8f0; border-radius:10px; padding:18px 20px; display:flex; align-items:center; gap:20px; margin-bottom:8px; }}
  .gauge {{ font-size: 40px; font-weight:800; color:{cor_nivel}; }}
  .bar {{ flex:1; }}
  .bar .track {{ background:#eef2f6; border-radius:8px; height:14px; overflow:hidden; }}
  .bar .fill {{ height:100%; width:{pct}%; background:{cor_nivel}; }}
  table {{ width:100%; border-collapse: collapse; background:#fff; border:1px solid #e2e8f0; border-radius:10px; overflow:hidden; }}
  td {{ padding:14px 14px; border-top:1px solid #eef2f6; vertical-align:top; font-size:14px; }}
  td.id {{ font-weight:700; color:#1F4E79; width:46px; }}
  .item {{ font-weight:600; margin-bottom:2px; }}
  .cat {{ font-size:12px; color:#7a8a99; margin-bottom:6px; }}
  .detalhe {{ font-size:13px; line-height:1.5; }}
  .trecho {{ font-style:italic; color:#445; background:#f3f6fb; border-left:3px solid #2E75B6; padding:8px 10px; margin:8px 0; font-size:12.5px; border-radius:4px; }}
  .base {{ font-size:11.5px; color:#94a3b8; margin-top:6px; }}
  .fund {{ font-size:12px; color:#3d2b50; background:#f6f1fb; border-left:3px solid #6C3483; padding:7px 10px; margin:8px 0; border-radius:4px; }}
  .fonte {{ font-size:11px; font-weight:600; }}
  .badge {{ color:#fff; font-size:11.5px; padding:5px 9px; border-radius:20px; white-space:nowrap; display:inline-block; }}
  .nota {{ font-size:12px; color:#7a8a99; margin-top:22px; line-height:1.6; }}
</style></head><body><div class="wrap">
  <header>
    <h1>Relatorio de Conformidade &mdash; Lei 14.133/2021</h1>
    <div class="sub">Edital analisado: <b>{e(nome_arquivo)}</b> &middot; {n_paginas} pagina(s) &middot; gerado em {data} &middot; <b>IA-Licita (piloto)</b></div>
  </header>

  <div class="risco">
    <div class="gauge">{pct}<span style="font-size:18px">/100</span></div>
    <div class="bar">
      <div style="font-weight:700; color:{cor_nivel}; margin-bottom:6px;">Indice de risco de nulidade: {nivel}</div>
      <div class="track"><div class="fill"></div></div>
      <div style="margin-top:10px; font-size:13px;">Nivel de atencao: <b style="color:{cor_at}">{nivel_at}</b>
        <span style="color:#7a8a99">&mdash; {det_at}</span></div>
    </div>
  </div>

  <div class="cards">
    <div class="card"><div class="n" style="color:#C0392B">{n_inc}</div><div class="l">Inconformidades</div></div>
    <div class="card"><div class="n" style="color:#E67E22">{n_ale}</div><div class="l">Alertas</div></div>
    <div class="card"><div class="n" style="color:#2E75B6">{n_rev}</div><div class="l">A revisar (IA/jurista)</div></div>
    <div class="card"><div class="n" style="color:#27AE60">{n_ok}</div><div class="l">Itens presentes</div></div>
  </div>

  <table>{linhas}
  </table>

  <div class="nota">
    <b>Como ler:</b> &ldquo;Inconformidade&rdquo; = padrao problematico detectado;
    &ldquo;Alerta&rdquo; = requisito obrigatorio nao localizado no texto (possivel ausencia);
    &ldquo;Revisar&rdquo; = exige leitura interpretativa da IA + jurista;
    &ldquo;Presente&rdquo; = termos do requisito localizados (ainda assim sujeito a validacao humana).<br>
    Prototipo de demonstracao. Todo apontamento deve ser confirmado por profissional habilitado &mdash; a ferramenta e de apoio, nao substitui o parecer juridico.
  </div>
</div></body></html>"""

# --------------------------------------------------------------------- main
def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a.split("=")[0]: a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--") and "=" in a}
    if not args:
        print("Uso: python3 analisador.py <edital.pdf> [saida.html] [--pareceres=arq.json] [--rag=base.json]")
        sys.exit(1)
    pdf_path = args[0]
    saida = args[1] if len(args) > 1 else "relatorio.html"
    aqui = os.path.dirname(os.path.abspath(__file__))
    base = os.path.join(aqui, "regras_14133.json")
    with open(base, encoding="utf-8") as f:
        regras = json.load(f)["regras"]

    texto, paginas = extrair_texto(pdf_path)
    if precisa_ocr(texto, paginas):
        print(f"ATENCAO: '{os.path.basename(pdf_path)}' nao tem texto extraivel "
              f"({len(texto.strip())} chars em {len(paginas)} pagina(s)) - provavel PDF "
              "escaneado. E necessario OCR antes da analise. Nenhum indice de risco foi calculado.")
        with open(saida, "w", encoding="utf-8") as f:
            f.write("<!DOCTYPE html><meta charset='utf-8'><body style='font-family:sans-serif;"
                    "max-width:640px;margin:40px auto;color:#333'><h2>Documento sem texto extraivel</h2>"
                    f"<p>O arquivo <b>{html.escape(os.path.basename(pdf_path))}</b> tem "
                    f"{len(paginas)} pagina(s), mas quase nenhum texto reconhecivel - provavelmente "
                    "e um PDF escaneado. Aplique OCR (ex.: Tesseract / OCR gerenciado) e rode novamente. "
                    "Nenhum indice de risco foi calculado para nao gerar resultado falso.</p></body>")
        print(f"Relatorio: {saida}")
        return
    apont = analisar(texto, regras)
    rag_base = flags.get("--rag") or os.path.join(aqui, "base_juridica.json")
    if "--ia" in [a.split("=")[0] for a in sys.argv[1:]]:
        # analise semantica automatica (IA ao vivo); cai no offline se indisponivel
        try:
            from ia_semantica import gerar_pareceres
            achados = gerar_pareceres(texto, regras, rag_base)
            apont = aplicar_pareceres_lista(apont, achados, rag_base)
            print("IA: analise semantica automatica concluida.")
        except Exception as e:
            print(f"IA indisponivel ({e}).")
            if flags.get("--pareceres"):
                print("-> usando modo offline (--pareceres).")
                apont = aplicar_pareceres(apont, flags["--pareceres"], rag_base)
    elif flags.get("--pareceres"):
        apont = aplicar_pareceres(apont, flags["--pareceres"], rag_base)
    pct, nivel = indice_de_risco(apont)
    out = gerar_html(apont, pct, nivel, os.path.basename(pdf_path), len(paginas))
    with open(saida, "w", encoding="utf-8") as f:
        f.write(out)

    n_inc = sum(1 for a in apont if a["status"] == "inconformidade")
    n_ale = sum(1 for a in apont if a["status"] == "alerta")
    print(f"OK: {len(apont)} requisitos checados | indice de risco {pct}/100 ({nivel}) "
          f"| {n_inc} inconformidades, {n_ale} alertas")
    print(f"Relatorio: {saida}")

if __name__ == "__main__":
    main()
