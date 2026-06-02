# -*- coding: utf-8 -*-
"""
IA-Licita — demo web (Streamlit).
Sobe um edital em PDF e mostra a auditoria na hora. Para publicar, ver DEPLOY.md.
Rodar localmente:  streamlit run app.py
"""
import os, io, json, tempfile
import streamlit as st
import analisador as A
import branding

AQUI = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(AQUI, "regras_14133.json"), encoding="utf-8") as _f:
    REGRAS = json.load(_f)["regras"]
BASE_RAG = os.path.join(AQUI, "base_juridica.json")
COR = {"inconformidade": "#C0392B", "alerta": "#E67E22", "revisar": "#2E75B6", "ok": "#27AE60"}
ROTULO = {"inconformidade": "Inconformidade", "alerta": "Alerta", "revisar": "Revisar", "ok": "Conforme"}

b = branding.carregar()
st.set_page_config(page_title="IA-Licita — Auditoria de Editais", page_icon="📄", layout="wide")

_logo_file = b.get("logo")
_logo_path = os.path.join(AQUI, _logo_file) if _logo_file else ""
_logo_visivel = False
if _logo_file and os.path.isfile(_logo_path):
    try:
        st.image(_logo_path, width=280)
        _logo_visivel = True
    except Exception:
        pass
if not _logo_visivel:
    st.markdown(f"#### {b['empresa']}")
    st.caption(b["tagline"])
st.title("Auditoria de Edital — Lei nº 14.133/2021")
st.write("Envie o edital em PDF e receba a análise de conformidade com índice de risco, "
         "apontamentos com fundamento legal e relatório para download.")

def _chave_disponivel():
    if os.environ.get("ANTHROPIC_API_KEY"):
        return True
    try:
        return bool(st.secrets.get("ANTHROPIC_API_KEY"))
    except Exception:
        return False

tem_chave = _chave_disponivel()
col_a, col_b = st.columns([3, 2])
up = col_a.file_uploader("Edital (PDF)", type=["pdf"])
usar_ia = col_b.toggle("Análise por IA (semântica)", value=tem_chave,
                       help="Requer chave de API configurada. Sem ela, roda só a camada de regras.")

if up is not None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(up.read())
        caminho = tmp.name
    try:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            try:
                if st.secrets.get("ANTHROPIC_API_KEY"):
                    os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
            except Exception:
                pass

        with st.spinner("Analisando o edital…"):
            texto, paginas = A.extrair_texto(caminho)
            if A.precisa_ocr(texto, paginas):
                st.warning(f"O arquivo tem {len(paginas)} página(s) mas quase nenhum texto extraível "
                           "— provável PDF escaneado. Aplique OCR e reenvie. Nenhum índice foi calculado "
                           "para não gerar resultado falso.")
                st.stop()
            apont = A.analisar(texto, REGRAS)
            if usar_ia:
                try:
                    from ia_semantica import gerar_pareceres
                    achados = gerar_pareceres(texto, REGRAS, BASE_RAG)
                    apont = A.aplicar_pareceres_lista(apont, achados, BASE_RAG)
                except Exception as e:
                    st.info(f"IA indisponível ({e}). Exibindo apenas a camada automática de regras.")
            pct, nivel = A.indice_de_risco(apont)
    finally:
        os.unlink(caminho)

    inc = [a for a in apont if a["status"] == "inconformidade"]
    ale = [a for a in apont if a["status"] == "alerta"]
    n_alta = sum(1 for a in inc if a["severidade"] == "alta")
    nivel_at = "ALTO" if n_alta else ("MÉDIO" if any(a["severidade"] == "media" for a in inc + ale) else "BAIXO")

    st.divider()
    m = st.columns(4)
    m[0].metric("Índice de risco", f"{pct}/100", nivel)
    m[1].metric("Nível de atenção", nivel_at)
    m[2].metric("Inconformidades", len(inc))
    m[3].metric("Alertas", len(ale))

    st.subheader("Apontamentos")
    ordem = {"inconformidade": 0, "alerta": 1, "revisar": 2, "ok": 3}
    mostrados = [a for a in sorted(apont, key=lambda x: (ordem.get(x["status"], 4), str(x["id"]))) if a["status"] != "ok"]
    if not mostrados:
        st.success("Nenhuma inconformidade, alerta ou ponto a revisar identificado nas regras aplicadas.")
    for a in mostrados:
        cor = COR[a["status"]]
        cab = f"{ROTULO[a['status']]} · {a['id']} — {a['item']}  ·  severidade {a['severidade']}"
        with st.expander(cab, expanded=(a["status"] == "inconformidade")):
            st.markdown(f"<span style='color:{cor};font-weight:600'>{ROTULO[a['status']]}</span> · "
                        f"<span style='color:#888'>{a['categoria']}</span>", unsafe_allow_html=True)
            st.write(a["detalhe"])
            if a["trecho"]:
                st.markdown(f"> *{a['trecho']}*")
            if a.get("fundamento"):
                st.caption("Fundamento (RAG): " + a["fundamento"][:400])
            st.caption(a["base_legal"])

    html = A.gerar_html(apont, pct, nivel, up.name, len(paginas))
    st.download_button("⬇️ Baixar relatório (HTML)", data=html.encode("utf-8"),
                       file_name=f"relatorio_{os.path.splitext(up.name)[0]}.html", mime="text/html")
    st.caption("Ferramenta de apoio — não substitui o parecer jurídico. "
               "Os apontamentos devem ser confirmados por profissional habilitado.")
else:
    st.info("Aguardando o envio de um edital em PDF.")
