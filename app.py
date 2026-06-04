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
import ddi_consultas
import ia_ddi
import relatorio_ddi

AQUI = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(AQUI, "regras_14133.json"), encoding="utf-8") as _f:
    REGRAS = json.load(_f)["regras"]
BASE_RAG = os.path.join(AQUI, "base_juridica.json")
COR = {"inconformidade": "#C0392B", "alerta": "#E67E22", "revisar": "#2E75B6", "ok": "#27AE60"}
ROTULO = {"inconformidade": "Inconformidade", "alerta": "Alerta", "revisar": "Revisar", "ok": "Conforme"}

b = branding.carregar()
st.set_page_config(page_title="IA-Licita — Auditoria de Editais", page_icon="📄", layout="wide")

# --- Proteção por senha ---
_senha_correta = None
try:
    _senha_correta = st.secrets.get("APP_PASSWORD")
except Exception:
    pass
if _senha_correta and not st.session_state.get("autenticado"):
    st.title("IA-Licita — Acesso restrito")
    senha = st.text_input("Senha de acesso", type="password", key="pwd")
    if senha == _senha_correta:
        st.session_state["autenticado"] = True
    else:
        if senha:
            st.error("Senha incorreta.")
        st.stop()

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
st.title("IA-Licita — Conformidade e Integridade nas Contratações Públicas")

aba1, aba2 = st.tabs(["📄 Auditoria de Edital", "🔍 Due Diligence de Integridade"])

with aba1:
    st.subheader("Auditoria de Edital — Lei nº 14.133/2021")
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

with aba2:
    st.subheader("Due Diligence de Integridade (DDI)")
    st.caption(
        "Portaria SEGES/ME 8.678/2021, art. 2º, III · "
        "Decreto 12.304/2024 · Portaria Normativa SE/CGU 226/2025"
    )

    if not ddi_consultas._get_cgu_key():
        st.warning(
            "CGU_API_KEY nao configurada — CEIS e CNEP nao serao consultados. "
            "Cadastre sua chave gratuita em portaldatransparencia.gov.br"
        )

    col1, col2 = st.columns([2, 1])
    cnpj_input = col1.text_input(
        "CNPJ do licitante (14 digitos, sem formatacao)", max_chars=18, key="ddi_cnpj_input"
    )
    valor_input = col2.number_input(
        "Valor do contrato (R$)", min_value=0.0, format="%.2f", step=10_000.0, key="ddi_valor_input"
    )

    if st.button("Consultar fontes publicas", type="primary", key="btn_ddi_consultar"):
        cnpj_limpo = "".join(c for c in cnpj_input if c.isdigit())
        if len(cnpj_limpo) != 14:
            st.error("Informe o CNPJ com 14 digitos numericos.")
        else:
            try:
                with st.spinner("Consultando Receita Federal, CEIS, CNEP e Empresa Pro-Etica..."):
                    dados = ddi_consultas.consultar(cnpj_limpo, valor_input)
                st.session_state["ddi_dados"] = dados
                st.session_state["ddi_cnpj"] = cnpj_limpo
                st.session_state["ddi_valor"] = valor_input
                st.session_state["ddi_etapa"] = 2
                nome = dados.get("razao_social") or "Empresa nao localizada na Receita"
                st.success(f"Consulta concluida — {nome}")
            except ValueError as e:
                st.error(str(e))

    if st.session_state.get("ddi_etapa", 0) >= 2:
        st.divider()
        st.subheader("Formulario de Integridade e Diligencia (FID)")
        st.caption("Responda com base nos documentos disponiveis sobre o licitante. Validade: 12 meses.")

        q1 = st.radio(
            "1. A empresa possui Codigo de Etica ou Conduta formal e publico?",
            ["Sim", "Nao", "Nao sei"], horizontal=True, key="ddi_q1"
        )
        q2 = st.radio(
            "2. Ha canal de denuncias ativo e acessivel a terceiros?",
            ["Sim", "Nao", "Nao sei"], horizontal=True, key="ddi_q2"
        )
        q3 = st.radio(
            "3. A empresa realiza treinamentos periodicos de integridade?",
            ["Sim", "Nao", "Nao sei"], horizontal=True, key="ddi_q3"
        )
        q4 = st.radio(
            "4. Ha politica de conflito de interesses documentada?",
            ["Sim", "Nao", "Nao sei"], horizontal=True, key="ddi_q4"
        )
        q5 = st.radio(
            "5. A empresa possui auditorias internas ou externas de integridade?",
            ["Sim", "Nao", "Nao sei"], horizontal=True, key="ddi_q5"
        )

        _dados_etapa2 = st.session_state.get("ddi_dados", {})
        if not _dados_etapa2.get("pro_etica"):
            pro_etica_manual = st.checkbox(
                "Empresa consta no Empresa Pro-Etica (CGU)? (marque se confirmado manualmente)",
                key="ddi_pro_etica_manual"
            )
        else:
            pro_etica_manual = False

        if st.button("Gerar Parecer DDI", type="primary", key="btn_ddi_parecer"):
            fid = {"q1": q1, "q2": q2, "q3": q3, "q4": q4, "q5": q5}
            _dados_analise = {**st.session_state["ddi_dados"]}
            if pro_etica_manual:
                _dados_analise = {**_dados_analise, "pro_etica": True}
            try:
                with st.spinner("Gerando parecer de integridade com IA..."):
                    parecer = ia_ddi.analisar(_dados_analise, fid)
                st.session_state["ddi_parecer"] = parecer
                st.session_state["ddi_fid"] = fid
                st.session_state["ddi_dados"] = _dados_analise
                st.session_state["ddi_etapa"] = 3
            except RuntimeError as e:
                st.error(str(e))

    if st.session_state.get("ddi_etapa", 0) >= 3:
        parecer = st.session_state["ddi_parecer"]
        fid = st.session_state["ddi_fid"]
        dados = st.session_state["ddi_dados"]
        cnpj_final = st.session_state["ddi_cnpj"]
        valor_final = st.session_state["ddi_valor"]

        st.divider()
        risco = parecer.get("risco_geral", "SEM RISCO IDENTIFICADO")
        _icone_risco = {
            "ALTO": "🔴", "MÉDIO": "🟠",
            "BAIXO": "🟡", "SEM RISCO IDENTIFICADO": "🟢"
        }
        st.subheader(f"{_icone_risco.get(risco, '⚪')} Risco Geral: {risco}")

        dims = parecer.get("dimensoes", {})
        _label_dim = {
            "situacao_cadastral": "Situacao Cadastral",
            "sancoes": "Sancoes e Punicoes",
            "programa_integridade": "Programa de Integridade",
            "fid": "Autoavaliacao (FID)",
            "contexto_contrato": "Contexto do Contrato",
        }
        _icone_status = {"ok": "✅", "alerta": "⚠️", "critico": "❌"}
        for chave, label in _label_dim.items():
            dim = dims.get(chave, {})
            icone = _icone_status.get(dim.get("status", "ok"), "ℹ️")
            with st.expander(f"{icone} {label}"):
                st.write(dim.get("descricao", "-"))
                for achado in dim.get("achados", []):
                    st.error(
                        f"**{achado.get('fonte')}:** {achado.get('descricao')} "
                        f"(gravidade: {achado.get('gravidade')})"
                    )

        st.subheader("Parecer")
        st.info(parecer.get("resumo", "-"))

        st.subheader("Recomendacao ao Gestor")
        st.write(parecer.get("recomendacao", "-"))

        with st.expander("Base Legal"):
            for bl in parecer.get("base_legal", []):
                st.write(f"- {bl}")

        pdf_bytes = relatorio_ddi.gerar_pdf(cnpj_final, valor_final, dados, fid, parecer)
        st.download_button(
            label="Baixar Relatorio PDF",
            data=pdf_bytes,
            file_name=f"DDI_{cnpj_final}.pdf",
            mime="application/pdf",
        )
