# -*- coding: utf-8 -*-
"""
IA-Licita — demo web (Streamlit).
Sobe um edital em PDF e mostra a auditoria na hora. Para publicar, ver DEPLOY.md.
Rodar localmente:  streamlit run app.py
"""
import os, io, json, html, tempfile
from datetime import date as _date_today
import streamlit as st
try:
    from streamlit.errors import StreamlitSecretNotFoundError as _SecretsNotFound
except ImportError:
    _SecretsNotFound = Exception  # Streamlit antigo: silencia tudo (incl. parse errors — limitação conhecida)
import analisador as A
import branding
import ddi_consultas
import ia_ddi
import relatorio_ddi
import etp_extrator
import ia_etp
import relatorio_etp
import ia_integridade
import relatorio_integridade
import ia_pi_empresas
import relatorio_pi_empresas
import ia_contratos
import relatorio_contratos
import ia_recebimento
import relatorio_recebimento
import ia_tr
import relatorio_tr
import ia_sancoes
import relatorio_sancoes
import ia_reabilitacao
import relatorio_reabilitacao
import ia_pesquisa_mercado
import relatorio_pesquisa_mercado

AQUI = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(AQUI, "regras_14133.json"), encoding="utf-8") as _f:
    REGRAS = json.load(_f)["regras"]
BASE_RAG = os.path.join(AQUI, "base_juridica.json")
COR = {"inconformidade": "#C0392B", "alerta": "#E67E22", "revisar": "#2E75B6", "ok": "#27AE60"}
ROTULO = {"inconformidade": "Inconformidade", "alerta": "Alerta", "revisar": "Revisar", "ok": "Conforme"}


def _safe_md(s: object) -> str:
    return str(s).replace('[', '&#91;')


def _fmt_brl(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _get_api_key():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        try:
            _val = st.secrets.get("ANTHROPIC_API_KEY")
            if _val:
                key = str(_val)
        except _SecretsNotFound:
            pass
        except Exception as _e:
            st.warning(f"Erro ao ler configurações (secrets.toml): {_e}")
    return key


b = branding.carregar()
st.set_page_config(page_title="IA-Licita — Auditoria de Editais", page_icon="📄", layout="wide")

# --- Proteção por senha ---
_senha_correta = None
try:
    _senha_correta = st.secrets.get("APP_PASSWORD")
except _SecretsNotFound:
    pass
except Exception as _e:
    st.error(f"Erro ao carregar configurações de acesso: {_e}. Contate o administrador.")
    st.stop()
if _senha_correta and not st.session_state.get("autenticado"):
    st.title("IA-Licita — Acesso restrito")
    senha = st.text_input("Senha de acesso", type="password", key="pwd")
    if senha == _senha_correta:
        st.session_state["autenticado"] = True
    else:
        if senha:
            st.error("Senha incorreta.")
        else:
            st.info("Informe a senha de acesso para continuar.")
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

aba1, aba2, aba3, aba4, aba5, aba6, aba7, aba8, aba9, aba10 = st.tabs([
    "📄 Auditoria de Edital",
    "🔍 Due Diligence de Integridade",
    "📋 Auditoria de ETP",
    "🏛️ Diagnóstico de Integridade",
    "🏢 Avaliação de PI",
    "⚖️ Alterações Contratuais",
    "📝 Auditoria de TR",
    "⚖️ Dosimetria de Sanções",
    "🔄 Reabilitação de Fornecedor",
    "💰 Pesquisa de Mercado",
])

with aba1:
    st.subheader("Auditoria de Edital — Lei nº 14.133/2021")
    st.write("Envie o edital em PDF e receba a análise de conformidade com índice de risco, "
             "apontamentos com fundamento legal e relatório para download.")

    def _chave_disponivel():
        if os.environ.get("ANTHROPIC_API_KEY"):
            return True
        try:
            return bool(st.secrets.get("ANTHROPIC_API_KEY"))
        except _SecretsNotFound:
            return False
        except Exception as _e:
            st.warning(f"Erro ao ler configurações de API: {_e}")
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
                _resolved = _get_api_key()
                if _resolved:
                    os.environ["ANTHROPIC_API_KEY"] = _resolved

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
                st.write(_safe_md(a["detalhe"]))
                if a["trecho"]:
                    st.markdown(f"> {_safe_md(a['trecho'])}")
                if a.get("fundamento"):
                    st.caption("Fundamento (RAG): " + _safe_md(a["fundamento"][:400]))
                st.caption(_safe_md(a["base_legal"]))

        _html_report = A.gerar_html(apont, pct, nivel, up.name, len(paginas))
        st.download_button("⬇️ Baixar relatório (HTML)", data=_html_report.encode("utf-8"),
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
            for _k in ("ddi_etapa", "ddi_parecer", "ddi_fid", "ddi_dados", "ddi_cnpj", "ddi_valor",
                       "ddi_q1", "ddi_q2", "ddi_q3", "ddi_q4", "ddi_q5", "ddi_pro_etica_manual"):
                st.session_state.pop(_k, None)
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
        risco = str(parecer.get("risco_geral") or "SEM RISCO IDENTIFICADO").strip().upper()
        risco = {"MEDIO": "MÉDIO"}.get(risco, risco)
        _icone_risco = {
            "ALTO": "🔴", "MÉDIO": "🟠",
            "BAIXO": "🟡", "SEM RISCO IDENTIFICADO": "🟢"
        }
        st.subheader(f"{_icone_risco.get(risco, '⚪')} Risco Geral: {_safe_md(risco)}")

        dims = parecer.get("dimensoes") or {}
        _label_dim = {
            "situacao_cadastral": "Situacao Cadastral",
            "sancoes": "Sancoes e Punicoes",
            "programa_integridade": "Programa de Integridade",
            "fid": "Autoavaliacao (FID)",
            "contexto_contrato": "Contexto do Contrato",
        }
        _icone_status = {"ok": "✅", "alerta": "⚠️", "critico": "❌"}
        for chave, label in _label_dim.items():
            dim = dims.get(chave) or {}
            icone = _icone_status.get((dim.get("status") or "ok").lower(), "ℹ️")
            with st.expander(f"{icone} {label}"):
                st.write(_safe_md(dim.get("descricao") or "-"))
                for achado in (dim.get("achados") or []):
                    if not achado:
                        continue
                    st.error(
                        f"**{_safe_md(achado.get('fonte') or '')}:** {_safe_md(achado.get('descricao') or '')} "
                        f"(gravidade: {_safe_md(achado.get('gravidade') or '')})"
                    )

        st.subheader("Parecer")
        st.info(_safe_md(parecer.get("resumo") or "-"))

        st.subheader("Recomendacao ao Gestor")
        st.write(_safe_md(parecer.get("recomendacao") or "-"))

        with st.expander("Base Legal"):
            for bl in (parecer.get("base_legal") or []):
                if bl:
                    st.write(f"- {_safe_md(bl)}")

        try:
            pdf_bytes = relatorio_ddi.gerar_pdf(cnpj_final, valor_final, dados, fid, parecer)
            st.download_button(
                label="Baixar Relatorio PDF",
                data=pdf_bytes,
                file_name=f"DDI_{cnpj_final}.pdf",
                mime="application/pdf",
            )
        except Exception as _e:
            st.error(f"Erro ao gerar PDF: {_e}")

with aba3:
    st.subheader("Auditoria de ETP — Estudo Técnico Preliminar")
    st.caption("IN SEGES/MGI 58/2022 · Lei 14.133/2021, art. 18, I")

    _api_key_etp = _get_api_key()
    _modelo_etp = os.environ.get("IA_LICITA_MODELO", "claude-haiku-4-5-20251001")

    _arqs_etp = st.file_uploader(
        "ETP e documentos complementares (PDF ou Word)",
        type=["pdf", "docx"],
        accept_multiple_files=True,
        key="etp_arquivos",
    )

    if st.button("Analisar ETP", type="primary", key="btn_etp", disabled=not _arqs_etp):
        if not _api_key_etp:
            st.error("ANTHROPIC_API_KEY não configurada — configure via variável de ambiente ou secrets.toml (verifique se o arquivo não tem erros de sintaxe).")
        else:
            try:
                with st.spinner("Extraindo texto e analisando com IA (pode levar 1-2 minutos)..."):
                    _texto_etp, _avisos_etp = etp_extrator.extrair_texto(_arqs_etp)
                    _parecer_etp = ia_etp.analisar_etp(_texto_etp, _api_key_etp, _modelo_etp)
                st.session_state["etp_parecer"] = _parecer_etp
                st.session_state["etp_avisos"] = _avisos_etp
                st.session_state["etp_nomes"] = [f.name for f in _arqs_etp]
            except ValueError as e:
                st.error(str(e))
            except RuntimeError as e:
                st.error(str(e))

    if "etp_parecer" in st.session_state:
        _pr = st.session_state["etp_parecer"]
        _av = st.session_state["etp_avisos"]
        _nm = st.session_state["etp_nomes"]

        for _aviso in _av:
            st.warning(_safe_md(_aviso))

        st.divider()
        _adeq = str(_pr.get("adequacao_geral") or "INADEQUADO").strip().upper()
        _icone_adeq = {"ADEQUADO": "🟢", "ADEQUADO COM RESSALVAS": "🟡", "INADEQUADO": "🔴"}
        st.subheader(f"{_icone_adeq.get(_adeq, '⚪')} Adequação Geral: {_safe_md(_adeq)}")

        _dims = _pr.get("dimensoes") or {}
        _labels = relatorio_etp._LABEL_DIMENSAO
        _ic_st = {"ok": "✅", "alerta": "⚠️", "critico": "❌"}
        for _ch, _lb in _labels.items():
            _d = _dims.get(_ch) or {}
            _ic = _ic_st.get((_d.get("status") or "ok").lower(), "ℹ️")
            with st.expander(f"{_ic} {_lb}"):
                st.write(_safe_md(_d.get("descricao") or "—"))

        _criticos = _pr.get("pontos_criticos", [])
        if _criticos:
            st.subheader("Pontos Críticos")
            for _c in _criticos:
                if _c:
                    st.error(_safe_md(_c))

        _recs = _pr.get("recomendacoes", [])
        if _recs:
            st.subheader("Recomendações ao Gestor")
            for _r in _recs:
                if _r:
                    st.info(_safe_md(_r))

        with st.expander("Base Legal"):
            for _bl in (_pr.get("base_legal") or []):
                if _bl:
                    st.write(f"• {_safe_md(_bl)}")

        try:
            _pdf_etp = relatorio_etp.gerar_pdf(_nm, _av, _pr)
            st.download_button(
                label="Baixar Relatório PDF",
                data=_pdf_etp,
                file_name="ETP_auditoria.pdf",
                mime="application/pdf",
            )
        except Exception as _e:
            st.error(f"Erro ao gerar PDF: {_e}")

with aba4:
    st.subheader("Diagnóstico do Programa de Integridade Pública")
    st.caption(
        "Decreto 11.129/2022 · IN CGU 21/2021 · Lei 12.846/2013, art. 7º, III · Decreto 8.420/2015"
    )

    _api_key_pip = _get_api_key()
    _modelo_pip = os.environ.get("IA_LICITA_MODELO", "claude-haiku-4-5-20251001")

    _municipio_pip = st.text_input("Nome do município", key="pip_municipio")

    st.markdown("**Questionário — 12 perguntas sobre o PIP**")
    _PERGUNTAS_PIP = [
        (k, f"{i}. {label}")
        for i, (k, label) in enumerate(ia_integridade.QUESTOES_PIP, 1)
    ]
    _respostas_pip = {}
    for _chave_pip, _pergunta_pip in _PERGUNTAS_PIP:
        _respostas_pip[_chave_pip] = st.selectbox(
            _pergunta_pip,
            ["Sim", "Não", "Parcialmente"],
            key=f"pip_{_chave_pip}",
        )

    _arqs_pip = st.file_uploader(
        "Documentos da prefeitura (opcional — PDF ou Word)",
        type=["pdf", "docx"],
        accept_multiple_files=True,
        key="pip_arquivos",
    )

    if st.button("Gerar Diagnóstico", type="primary", key="btn_pip", disabled=not _municipio_pip):
        if not _api_key_pip:
            st.error("ANTHROPIC_API_KEY não configurada — configure via variável de ambiente ou secrets.toml.")
        else:
            for _k in ("pip_parecer", "pip_municipio", "pip_avisos", "pip_pdf", "pip_pdf_nome"):
                st.session_state.pop(_k, None)
            try:
                with st.spinner("Analisando programa de integridade com IA (pode levar 1-2 minutos)..."):
                    _texto_pip, _avisos_pip = (
                        etp_extrator.extrair_texto(_arqs_pip) if _arqs_pip else (None, [])
                    )
                    _parecer_pip = ia_integridade.diagnosticar(
                        _respostas_pip,
                        _texto_pip,
                        _api_key_pip,
                        _modelo_pip,
                        st.session_state.get("ddi_parecer"),
                    )
                st.session_state["pip_parecer"] = _parecer_pip
                st.session_state["pip_municipio"] = _municipio_pip
                st.session_state["pip_avisos"] = _avisos_pip
                _nome_pip = _municipio_pip.replace("/", "-").replace(" ", "_")
                try:
                    st.session_state["pip_pdf"] = relatorio_integridade.gerar_pdf(
                        _municipio_pip, _parecer_pip
                    )
                    st.session_state["pip_pdf_nome"] = f"PIP_{_nome_pip}.pdf"
                except Exception as _pdf_e:
                    st.session_state.pop("pip_pdf", None)
                    st.warning(f"Não foi possível gerar o PDF: {_pdf_e}")
            except (ValueError, RuntimeError) as _e:
                st.error(str(_e))

    if "pip_parecer" in st.session_state:
        _pr_pip = st.session_state["pip_parecer"]
        _mun_pip = st.session_state.get("pip_municipio", "")
        _av_pip  = st.session_state.get("pip_avisos", [])

        for _aviso in _av_pip:
            st.warning(_safe_md(_aviso))

        st.divider()
        _mat_pip = str(_pr_pip.get("maturidade_geral") or "INEXISTENTE").strip().upper()
        st.subheader(f"{ia_integridade.ICONE_MATURIDADE.get(_mat_pip, '⚪')} Maturidade Geral: {_safe_md(_mat_pip)}")

        _resumo_pip = str(_pr_pip.get("resumo_executivo") or "")
        if _resumo_pip:
            st.info(_safe_md(_resumo_pip))

        _dims_pip = _pr_pip.get("dimensoes") or {}
        for _ch, _lb in ia_integridade.LABEL_DIMENSAO.items():
            _d   = _dims_pip.get(_ch) or {}
            _niv = str(_d.get("nivel") or "INEXISTENTE").strip().upper()
            _ic  = ia_integridade.ICONE_MATURIDADE.get(_niv, "⚪")
            with st.expander(f"{_ic} {_lb} — {_niv}"):
                for _ach in (_d.get("achados") or []):
                    if _ach:
                        st.warning(_safe_md(_ach))
                for _rec in (_d.get("recomendacoes") or []):
                    if _rec:
                        st.info(_safe_md(_rec))

        _prio_pip = _pr_pip.get("prioridades") or []
        if _prio_pip:
            st.subheader("Prioridades Imediatas")
            for _i, _p in enumerate(_prio_pip, 1):
                if _p:
                    st.error(f"{_i}. {_safe_md(_p)}")

        with st.expander("Base Legal"):
            for _bl in (_pr_pip.get("base_legal") or []):
                if _bl:
                    st.write(f"• {_safe_md(_bl)}")

        if "pip_pdf" in st.session_state:
            st.download_button(
                label="Baixar Relatório PDF",
                data=st.session_state["pip_pdf"],
                file_name=st.session_state.get("pip_pdf_nome", "PIP.pdf"),
                mime="application/pdf",
            )

with aba5:
    st.subheader("Avaliação do Programa de Integridade — Decreto 12.304/2024")
    st.caption(
        "Decreto 12.304/2024 · Lei 14.133/2021, arts. 60-IV e 163 · Lei 12.846/2013, art. 7º, IV"
    )

    _api_key_pi = _get_api_key()
    _modelo_pi = os.environ.get("IA_LICITA_MODELO", "claude-haiku-4-5-20251001")

    # ── Etapa 1: Identificação ─────────────────────────────────────────────
    st.markdown("### Etapa 1 — Identificação da Entidade")
    _col_cnpj, _col_tipo = st.columns([2, 3])
    _cnpj_pi = _col_cnpj.text_input(
        "CNPJ da entidade", key="pi_cnpj_input", placeholder="00.000.000/0000-00"
    )
    _tipo_opcoes = list(ia_pi_empresas.TIPOS_ENTIDADE.keys())
    _tipo_labels = list(ia_pi_empresas.TIPOS_ENTIDADE.values())
    _tipo_idx = _col_tipo.selectbox(
        "Tipo de Entidade",
        options=range(len(_tipo_opcoes)),
        format_func=lambda i: _tipo_labels[i],
        key="pi_tipo_select",
    )
    _tipo_entidade_pi = _tipo_opcoes[_tipo_idx]

    _hip_opcoes = dict(ia_pi_empresas.HIPOTESES_POR_TIPO.get(_tipo_entidade_pi) or {})
    _hip_chaves = list(_hip_opcoes.keys())
    _hip_labels_pi = list(_hip_opcoes.values())
    _hip_idx = st.selectbox(
        "Hipótese legal",
        options=range(len(_hip_chaves)),
        format_func=lambda i: _hip_labels_pi[i],
        key=f"pi_hipotese_select_{_tipo_entidade_pi}",
    )
    _hipotese_pi = _hip_chaves[_hip_idx]

    if st.button("Consultar entidade", key="btn_pi_etapa1", disabled=not _cnpj_pi):
        for _k in ("pi_etapa", "pi_dados", "pi_cnpj", "pi_hipotese",
                   "pi_tipo_entidade", "pi_respostas", "pi_parecer", "pi_pdf"):
            st.session_state.pop(_k, None)
        for _p in ia_pi_empresas.QUESTOES_PI:
            st.session_state.pop(f"pi_{_p}", None)
        st.session_state.pop("pi_docs", None)
        try:
            with st.spinner("Consultando Receita Federal..."):
                _dados_pi = ddi_consultas.consultar(_cnpj_pi, 0.0)
            st.session_state["pi_dados"] = _dados_pi
            st.session_state["pi_cnpj"] = _dados_pi["cnpj"]
            st.session_state["pi_hipotese"] = _hipotese_pi
            st.session_state["pi_tipo_entidade"] = _tipo_entidade_pi
            st.session_state["pi_etapa"] = 2
        except ValueError as _e:
            st.error(str(_e))
        except Exception as _e:
            st.error(f"Erro ao consultar empresa: {_e}")

    if st.session_state.get("pi_etapa", 0) >= 2:
        _d_pi = st.session_state["pi_dados"]
        _hip_pi = st.session_state["pi_hipotese"]
        st.success(f"**{_d_pi.get('razao_social') or 'Empresa'}** — "
                   f"CNPJ: {st.session_state['pi_cnpj']} — "
                   f"Situação: {_d_pi.get('situacao') or '-'} — "
                   f"Porte: {_d_pi.get('porte') or '-'}")
        if (
            _hip_pi == "grande_vulto"
            and st.session_state.get("pi_tipo_entidade", "empresa_privada") == "empresa_privada"
            and "GRANDE" not in str(_d_pi.get("porte") or "").upper()
        ):
            st.warning(
                "⚠️ PI obrigatório somente para contratos > R$ 239M (grande vulto). "
                "Confirme o enquadramento antes de prosseguir."
            )

        # ── Etapa 2: Questionário ──────────────────────────────────────────
        st.divider()
        st.markdown("### Etapa 2 — Questionário (17 parâmetros)")

        _respostas_pi = {}
        for _dim_key, (_dim_label, _params) in ia_pi_empresas.DIMENSOES_PI.items():
            with st.expander(f"**{_dim_label}** ({len(_params)} parâmetros)"):
                for _p in _params:
                    _rotulo_p = ia_pi_empresas.QUESTOES_PI[_p]
                    _respostas_pi[_p] = st.radio(
                        _rotulo_p,
                        options=["Não existe", "Parcialmente", "Implementado"],
                        key=f"pi_{_p}",
                        horizontal=True,
                    )

        _arqs_pi = st.file_uploader(
            "Documentos da empresa (opcional — PDF ou Word): regulamento interno, "
            "código de ética, relatório do PI, etc.",
            type=["pdf", "docx"],
            accept_multiple_files=True,
            key="pi_docs",
        )

        if st.button("Gerar Avaliação", type="primary", key="btn_pi_etapa2"):
            if not _api_key_pi:
                st.session_state["pi_etapa"] = 2  # oculta bloco de resultado de etapa anterior
                st.error(
                    "ANTHROPIC_API_KEY não configurada — "
                    "configure via variável de ambiente ou secrets.toml."
                )
            else:
                for _k in ("pi_respostas", "pi_parecer", "pi_pdf"):
                    st.session_state.pop(_k, None)
                try:
                    with st.spinner(
                        "Avaliando programa de integridade com IA (pode levar 1-2 minutos)..."
                    ):
                        _texto_pi, _avisos_pi = (
                            etp_extrator.extrair_texto(_arqs_pi) if _arqs_pi else (None, [])
                        )
                        for _av_pi in _avisos_pi:
                            st.warning(_av_pi)
                        if _texto_pi and len(_texto_pi) > 30_000:
                            st.warning(
                                "Documentos muito extensos: apenas os primeiros 30 000 "
                                "caracteres serão analisados."
                            )
                        _tipo_pi = _tipo_entidade_pi
                        _parecer_pi = ia_pi_empresas.avaliar(
                            _respostas_pi,
                            st.session_state["pi_hipotese"],
                            _texto_pi,
                            _api_key_pi,
                            _modelo_pi,
                            tipo_entidade=_tipo_pi,
                        )
                    st.session_state["pi_respostas"] = _respostas_pi
                    st.session_state["pi_parecer"] = _parecer_pi
                    st.session_state["pi_tipo_entidade"] = _tipo_pi
                    st.session_state["pi_etapa"] = 3
                    _razao_pi = st.session_state["pi_dados"].get("razao_social") or ""
                    try:
                        st.session_state["pi_pdf"] = relatorio_pi_empresas.gerar_pdf(
                            cnpj=st.session_state["pi_cnpj"],
                            razao_social=_razao_pi,
                            hipotese=st.session_state["pi_hipotese"],
                            parecer=_parecer_pi,
                            tipo_entidade=_tipo_pi,
                        )
                    except Exception as _pdf_e:
                        st.session_state.pop("pi_pdf", None)
                        st.warning(f"Não foi possível gerar o PDF: {_pdf_e}")
                except (ValueError, RuntimeError) as _e:
                    st.error(str(_e))

    # ── Etapa 3: Resultado ─────────────────────────────────────────────────
    if st.session_state.get("pi_etapa", 0) >= 3:
        _pr_pi = st.session_state.get("pi_parecer") or {}
        if not _pr_pi:
            st.error("Resultado da avaliação não encontrado. Por favor, refaça a análise.")
            st.stop()
        _sc_pi = _pr_pi.get("scores") or {}

        st.divider()
        st.markdown("### Resultado da Avaliação")
        _tipo_label_pi = ia_pi_empresas.TIPOS_ENTIDADE.get(
            st.session_state.get("pi_tipo_entidade", _tipo_entidade_pi), _tipo_entidade_pi
        )
        st.caption(f"Tipo de Entidade: {_tipo_label_pi}")

        _nivel_pi = str(_sc_pi.get("nivel") or "INEXISTENTE").strip().upper()
        _score_pi = _sc_pi.get("geral", 0.0)
        _cor_pi = ia_integridade.COR_MATURIDADE_HEX.get(_nivel_pi, "#888888")
        _icone_pi = ia_integridade.ICONE_MATURIDADE.get(_nivel_pi, "⚪")
        st.markdown(
            f"<div style='background:{_cor_pi};padding:16px;border-radius:8px;"
            f"color:white;font-size:20px;font-weight:bold;text-align:center'>"
            f"{_icone_pi} {html.escape(_nivel_pi)} — {_score_pi:.0f}/100"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.markdown("")

        # Scores por dimensão
        _por_dim = _sc_pi.get("por_dimensao") or {}
        st.markdown("**Score por Dimensão:**")
        for _dim_key, (_dim_label, _) in ia_pi_empresas.DIMENSOES_PI.items():
            _s = _por_dim.get(_dim_key, 0.0)
            st.write(f"• **{_dim_label}:** {_s:.0f}/100")

        # Conclusão para a hipótese
        _conc_pi = str(_pr_pi.get("conclusao_hipotese") or "")
        if _conc_pi:
            st.info(_safe_md(_conc_pi))

        # Pontos críticos
        _crit_pi = _pr_pi.get("pontos_criticos") or []
        if _crit_pi:
            st.markdown("**Pontos Críticos**")
            for _i, _c in enumerate(_crit_pi, 1):
                if _c:
                    st.error(f"{_i}. {_safe_md(_c)}")

        # Análise por dimensão
        _dims_pi = _pr_pi.get("dimensoes") or {}
        for _dim_key, (_dim_label, _params_d) in ia_pi_empresas.DIMENSOES_PI.items():
            _dim_d = _dims_pi.get(_dim_key) or {}
            _sintese_d = str(_dim_d.get("sintese") or "-")
            _score_d = _por_dim.get(_dim_key, 0.0)
            with st.expander(f"**{_dim_label}** — {_score_d:.0f}/100"):
                st.write(_safe_md(_sintese_d))
                _params_q = _dim_d.get("parametros") or {}
                for _p in _params_d:
                    _pdata = _params_q.get(_p) or {}
                    for _ach in (_pdata.get("achados") or []):
                        if _ach:
                            st.warning(f"**{ia_pi_empresas.QUESTOES_PI[_p]}:** {_safe_md(_ach)}")
                    for _rec in (_pdata.get("recomendacoes") or []):
                        if _rec:
                            st.info(f"→ {_safe_md(_rec)}")

        # Recomendações gerais
        _recs_pi = _pr_pi.get("recomendacoes") or []
        if _recs_pi:
            with st.expander("**Recomendações ao Gestor**"):
                for _i, _r in enumerate(_recs_pi, 1):
                    if _r:
                        st.write(f"{_i}. {_safe_md(_r)}")

        # Base legal
        with st.expander("Base Legal"):
            for _bl in (_pr_pi.get("base_legal") or []):
                if _bl:
                    st.write(f"• {_safe_md(_bl)}")

        # Download PDF
        if "pi_pdf" in st.session_state:
            _razao_final = (st.session_state.get("pi_dados") or {}).get("razao_social") or "PI"
            _nome_pdf_pi = f"PI_{_razao_final.replace(' ', '_')[:30]}.pdf"
            st.download_button(
                label="⬇️ Baixar Relatório PDF",
                data=st.session_state["pi_pdf"],
                file_name=_nome_pdf_pi,
                mime="application/pdf",
            )

def _render_bloco_recv(bloco_key: str, titulo: str, pr: dict, icones: dict, cores: dict) -> None:
    _bloco = (pr.get(bloco_key) or {})
    _pval = str(_bloco.get("parecer") or "INAPTO").strip().upper()
    _pval = ia_recebimento.NORM_PARECER_RECV.get(_pval, _pval)
    st.markdown(
        f"<div style='background:{cores.get(_pval, '#888888')};"
        f"padding:12px;border-radius:8px;color:white;font-size:16px;"
        f"font-weight:bold;text-align:center'>"
        f"{icones.get(_pval, '⚪')} {html.escape(_pval)}</div>",
        unsafe_allow_html=True,
    )
    st.caption(titulo)
    _sint = str(_bloco.get("sintese") or "")
    if _sint:
        st.info(_safe_md(_sint))
    _conds = _bloco.get("condicoes")
    _conds = _conds if isinstance(_conds, list) else []
    if _conds:
        st.markdown("**Condições Verificadas:**")
        _icone_cond = {"ATENDIDA": "✅", "PARCIAL": "⚠️", "AUSENTE": "❌"}
        for _cond in _conds:
            if not isinstance(_cond, dict) or not _cond:
                continue
            _st_c = str(_cond.get("status") or "AUSENTE").strip().upper()
            _ic_c = _icone_cond.get(_st_c, "ℹ️")
            _obs_c = " ".join(str(_cond.get("observacao") or "").split())
            _desc_c = " ".join(str(_cond.get("descricao") or "").split())
            _linha_c = f"{_ic_c} **{_safe_md(_desc_c)}**"
            if _obs_c:
                _linha_c += f" — {_safe_md(_obs_c)}"
            st.markdown(_linha_c)
    _pends = _bloco.get("pendencias")
    _pends = _pends if isinstance(_pends, list) else []
    for _p in _pends:
        if _p:
            st.warning(_safe_md(_p))


with aba6:
    st.subheader("Monitor de Contratos")
    _sub_aba_alt, _sub_aba_recv = st.tabs([
        "⚖️ Alterações Contratuais",
        "📦 Recebimento Contratual",
    ])

    with _sub_aba_alt:
        st.subheader("Analisador de Alterações Contratuais")
        st.caption(
            "Art. 124 II 'd' · Art. 25 §8º · Art. 137 §2º — Lei 14.133/2021 · Art. 37 XXI CF/88"
        )

        _api_key_cont = _get_api_key()
        _modelo_cont = os.environ.get("IA_LICITA_MODELO", "claude-haiku-4-5-20251001")

        _tipos_cont_chaves = list(ia_contratos.TIPOS_ALTERACAO.keys())
        _tipos_cont_labels = list(ia_contratos.TIPOS_ALTERACAO.values())
        _tipo_cont_idx = st.selectbox(
            "Tipo de alteração contratual",
            options=range(len(_tipos_cont_chaves)),
            format_func=lambda i: _tipos_cont_labels[i],
            key="cont_tipo_select",
        )
        _tipo_cont = _tipos_cont_chaves[_tipo_cont_idx]

        _col_num_cont, _col_data_cont = st.columns(2)
        _num_cont = _col_num_cont.text_input(
            "Número do contrato", key="cont_numero", placeholder="001/2024"
        )
        _data_cont = _col_data_cont.text_input(
            "Data de assinatura", key="cont_data", placeholder="DD/MM/AAAA"
        )
        _objeto_cont = st.text_input(
            "Objeto do contrato (resumido)", key="cont_objeto"
        )
        _valor_cont = st.number_input(
            "Valor atual do contrato (R$)",
            min_value=0.0, format="%.2f", step=10_000.0, key="cont_valor",
        )

        _arqs_cont = st.file_uploader(
            "Documentos do pedido (opcional — PDF ou Word): requerimento, memória de cálculo, CCT, planilhas etc.",
            type=["pdf", "docx"],
            accept_multiple_files=True,
            key="cont_docs",
        )

        if st.button("Analisar Pedido", type="primary", key="btn_cont"):
            if not _api_key_cont:
                st.error(
                    "ANTHROPIC_API_KEY não configurada — "
                    "configure via variável de ambiente ou secrets.toml."
                )
            else:
                for _k in ("cont_parecer", "cont_pdf", "cont_dados"):
                    st.session_state.pop(_k, None)
                _dados_cont = {
                    "numero_contrato": _num_cont or "não informado",
                    "objeto": _objeto_cont or "não informado",
                    "data_assinatura": _data_cont or "não informada",
                    "valor_atual": _valor_cont,
                }
                try:
                    with st.spinner(
                        "Analisando pedido de alteração contratual com IA (pode levar 1-2 minutos)..."
                    ):
                        _texto_cont, _avisos_cont = (
                            etp_extrator.extrair_texto(_arqs_cont)
                            if _arqs_cont
                            else (None, [])
                        )
                        for _av_cont in _avisos_cont:
                            st.warning(_safe_md(_av_cont))
                        if _texto_cont and len(_texto_cont) > 30_000:
                            st.warning(
                                "Documentos muito extensos: apenas os primeiros 30 000 "
                                "caracteres serão analisados."
                            )
                        _parecer_cont = ia_contratos.analisar(
                            _tipo_cont,
                            _dados_cont,
                            _texto_cont,
                            _api_key_cont,
                            _modelo_cont,
                        )
                    st.session_state["cont_parecer"] = _parecer_cont
                    st.session_state["cont_dados"] = _dados_cont
                    try:
                        st.session_state["cont_pdf"] = relatorio_contratos.gerar_pdf(
                            dados_contrato=_dados_cont,
                            tipo=_tipo_cont,
                            parecer=_parecer_cont,
                        )
                    except Exception as _pdf_e:
                        st.session_state.pop("cont_pdf", None)
                        st.warning(f"Não foi possível gerar o PDF: {_pdf_e}")
                except Exception as _e:
                    st.error(str(_e))

        if "cont_parecer" in st.session_state:
            _pr_cont = st.session_state["cont_parecer"]

            st.divider()
            _parecer_val_cont = str(_pr_cont.get("parecer") or "INDEFERÍVEL").strip().upper()
            _parecer_val_cont = ia_contratos.NORM_PARECER_CONT.get(_parecer_val_cont, _parecer_val_cont)
            _icone_parecer_cont = {
                "DEFERÍVEL":               "🟢",
                "DEFERÍVEL COM RESSALVAS": "🟡",
                "INDEFERÍVEL":             "🔴",
            }
            _cor_parecer_cont = {
                "DEFERÍVEL":               "#27AE60",
                "DEFERÍVEL COM RESSALVAS": "#F39C12",
                "INDEFERÍVEL":             "#C0392B",
            }
            st.markdown(
                f"<div style='background:{_cor_parecer_cont.get(_parecer_val_cont, '#888888')};"
                f"padding:16px;border-radius:8px;color:white;font-size:20px;"
                f"font-weight:bold;text-align:center'>"
                f"{_icone_parecer_cont.get(_parecer_val_cont, '⚪')} {html.escape(_parecer_val_cont)}"
                f"</div>",
                unsafe_allow_html=True,
            )
            st.markdown("")

            _sintese_cont = str(_pr_cont.get("sintese") or "")
            if _sintese_cont:
                st.info(_safe_md(_sintese_cont))

            _requisitos_cont = _pr_cont.get("requisitos")
            _requisitos_cont = _requisitos_cont if isinstance(_requisitos_cont, list) else []
            if _requisitos_cont:
                st.markdown("**Verificação de Requisitos:**")
                _icone_req_cont = {"ATENDIDO": "✅", "PARCIAL": "⚠️", "AUSENTE": "❌"}
                for _req_cont in _requisitos_cont:
                    if not isinstance(_req_cont, dict) or not _req_cont:
                        continue
                    _status_req = str(_req_cont.get("status") or "AUSENTE").strip().upper()
                    _ic_req = _icone_req_cont.get(_status_req, "ℹ️")
                    _obs_req = " ".join(str(_req_cont.get("observacao") or "").split())
                    _desc_req = " ".join(str(_req_cont.get("descricao") or "").split())
                    _linha_req = f"{_ic_req} **{_safe_md(_desc_req)}**"
                    if _obs_req:
                        _linha_req += f" — {_safe_md(_obs_req)}"
                    st.markdown(_linha_req)

            _lacunas_cont = _pr_cont.get("lacunas_documentais")
            _lacunas_cont = _lacunas_cont if isinstance(_lacunas_cont, list) else []
            if _lacunas_cont:
                with st.expander("📋 Lacunas Documentais"):
                    for _lac in _lacunas_cont:
                        if _lac:
                            st.warning(_safe_md(_lac))

            _recs_cont = _pr_cont.get("recomendacoes")
            _recs_cont = _recs_cont if isinstance(_recs_cont, list) else []
            if _recs_cont:
                with st.expander("💡 Recomendações ao Gestor"):
                    for _i_cont, _r_cont in enumerate(_recs_cont, 1):
                        if _r_cont:
                            st.info(f"{_i_cont}. {_safe_md(_r_cont)}")

            _fls_cont = _pr_cont.get("fundamentos_legais")
            _fls_cont = _fls_cont if isinstance(_fls_cont, list) else []
            if _fls_cont:
                with st.expander("⚖️ Fundamentos Legais"):
                    for _fl_cont in _fls_cont:
                        if _fl_cont:
                            st.markdown(f"• {_safe_md(_fl_cont)}")

            if "cont_pdf" in st.session_state:
                _num_pdf_cont = (
                    (st.session_state.get("cont_dados") or {}).get("numero_contrato")
                    or "contrato"
                )
                _nome_pdf_cont = f"Alteracao_{_num_pdf_cont.replace('/', '-').replace(' ', '_')}.pdf"
                st.download_button(
                    label="⬇️ Baixar Relatório PDF",
                    data=st.session_state["cont_pdf"],
                    file_name=_nome_pdf_cont,
                    mime="application/pdf",
                )

    with _sub_aba_recv:
        st.subheader("Recebimento Contratual")
        st.caption("Art. 140, I e II — Lei 14.133/2021")

        _api_key_recv = _get_api_key()
        _modelo_recv = os.environ.get("IA_LICITA_MODELO", "claude-haiku-4-5-20251001")

        _tipos_recv_chaves = list(ia_recebimento.TIPOS_OBJETO.keys())
        _tipos_recv_labels = list(ia_recebimento.TIPOS_OBJETO.values())
        _tipo_recv_idx = st.selectbox(
            "Tipo de objeto contratual",
            options=range(len(_tipos_recv_chaves)),
            format_func=lambda i: _tipos_recv_labels[i],
            key="recv_tipo_select",
        )
        _tipo_recv = _tipos_recv_chaves[_tipo_recv_idx]

        _col_num_recv, _col_data_recv = st.columns(2)
        _num_recv = _col_num_recv.text_input(
            "Número do contrato", key="recv_numero", placeholder="001/2024"
        )
        _data_recv = _col_data_recv.text_input(
            "Data de entrega/conclusão", key="recv_data", placeholder="DD/MM/AAAA"
        )
        _objeto_recv = st.text_input("Objeto do contrato (resumido)", key="recv_objeto")
        _desc_recv = st.text_area(
            "Descrição do que foi entregue/executado", key="recv_descricao"
        )
        _nao_conf_recv = st.text_area(
            "Não conformidades ou pendências identificadas (opcional)", key="recv_nao_conf"
        )
        _valor_recv = st.number_input(
            "Valor do contrato (R$)",
            min_value=0.0, format="%.2f", step=10_000.0, key="recv_valor",
        )
        _arqs_recv = st.file_uploader(
            "Documentos de suporte (opcional — PDF ou DOCX)",
            type=["pdf", "docx"],
            accept_multiple_files=True,
            key="recv_docs",
        )

        if st.button("Analisar Recebimento", type="primary", key="btn_recv"):
            if not _api_key_recv:
                st.error(
                    "ANTHROPIC_API_KEY não configurada — "
                    "configure via variável de ambiente ou secrets.toml."
                )
            elif not _desc_recv.strip():
                st.error("Preencha a descrição do que foi entregue/executado.")
            else:
                for _k in ("recv_parecer", "recv_pdf", "recv_dados"):
                    st.session_state.pop(_k, None)
                _dados_recv = {
                    "numero_contrato": _num_recv or "não informado",
                    "objeto": _objeto_recv or "não informado",
                    "data_entrega": _data_recv or "não informada",
                    "descricao_entrega": _desc_recv,
                    "nao_conformidades": _nao_conf_recv or "",
                    "valor_contrato": _valor_recv,
                }
                try:
                    with st.spinner(
                        "Analisando recebimento contratual com IA (pode levar 1-2 minutos)..."
                    ):
                        _texto_recv, _avisos_recv = (
                            etp_extrator.extrair_texto(_arqs_recv)
                            if _arqs_recv
                            else (None, [])
                        )
                        for _av_recv in _avisos_recv:
                            st.warning(_safe_md(_av_recv))
                        if _texto_recv and len(_texto_recv) > 30_000:
                            st.warning(
                                "Documentos muito extensos: apenas os primeiros 30 000 "
                                "caracteres serão analisados."
                            )
                        _parecer_recv = ia_recebimento.analisar(
                            _tipo_recv,
                            _dados_recv,
                            _texto_recv,
                            _api_key_recv,
                            _modelo_recv,
                        )
                    st.session_state["recv_parecer"] = _parecer_recv
                    st.session_state["recv_dados"] = _dados_recv
                    try:
                        st.session_state["recv_pdf"] = relatorio_recebimento.gerar_pdf(
                            dados_entrega=_dados_recv,
                            tipo_objeto=_tipo_recv,
                            parecer=_parecer_recv,
                        )
                    except Exception as _pdf_e:
                        st.session_state.pop("recv_pdf", None)
                        st.warning(f"Não foi possível gerar o PDF: {_pdf_e}")
                except Exception as _e:
                    st.error(str(_e))

        if "recv_parecer" in st.session_state:
            _pr_recv = st.session_state["recv_parecer"]
            st.divider()

            _icone_parecer_recv = {"APTO": "🟢", "APTO COM RESSALVAS": "🟡", "INAPTO": "🔴"}
            _cor_parecer_recv = {
                "APTO": "#27AE60", "APTO COM RESSALVAS": "#F39C12", "INAPTO": "#C0392B",
            }

            _col_prov, _col_def = st.columns(2)
            with _col_prov:
                _render_bloco_recv(
                    "recebimento_provisorio", "Recebimento Provisório — Art. 140, I",
                    _pr_recv, _icone_parecer_recv, _cor_parecer_recv,
                )
            with _col_def:
                _render_bloco_recv(
                    "recebimento_definitivo", "Recebimento Definitivo — Art. 140, II",
                    _pr_recv, _icone_parecer_recv, _cor_parecer_recv,
                )

            _recs_recv = _pr_recv.get("recomendacoes_gerais")
            _recs_recv = _recs_recv if isinstance(_recs_recv, list) else []
            if _recs_recv:
                with st.expander("💡 Recomendações ao Gestor"):
                    for _i_recv, _r_recv in enumerate(_recs_recv, 1):
                        if _r_recv:
                            st.info(f"{_i_recv}. {_safe_md(_r_recv)}")

            _bl_recv = _pr_recv.get("base_legal")
            _bl_recv = _bl_recv if isinstance(_bl_recv, list) else []
            if _bl_recv:
                with st.expander("⚖️ Base Legal"):
                    for _b_recv in _bl_recv:
                        if _b_recv:
                            st.markdown(f"• {_safe_md(_b_recv)}")

            if "recv_pdf" in st.session_state:
                _num_pdf_recv = (
                    (st.session_state.get("recv_dados") or {}).get("numero_contrato")
                    or "contrato"
                )
                _nome_pdf_recv = (
                    f"Recebimento_{_num_pdf_recv.replace('/', '-').replace(' ', '_')}.pdf"
                )
                st.download_button(
                    label="⬇️ Baixar Relatório PDF",
                    data=st.session_state["recv_pdf"],
                    file_name=_nome_pdf_recv,
                    mime="application/pdf",
                )

with aba7:
    st.subheader("Auditoria de Termo de Referência — IN SEGES 81/2022")
    st.caption("Lei 14.133/2021, Art. 6º, XXIII · IN SEGES/MGI 81/2022 · IN SGD/ME 21/2024 (TIC)")

    _api_key_tr = _get_api_key()
    _modelo_tr = os.environ.get("IA_LICITA_MODELO", "claude-haiku-4-5-20251001")

    _tipo_tr_opcoes = {"Serviço": "servico", "Bem / Material": "bem", "Serviço de TIC": "tic"}
    _tipo_tr_label = st.radio(
        "Tipo de objeto",
        list(_tipo_tr_opcoes.keys()),
        horizontal=True,
        key="tr_tipo",
    )
    _tipo_tr = _tipo_tr_opcoes[_tipo_tr_label]

    _arq_tr = st.file_uploader(
        "Envie o TR em PDF ou DOCX",
        type=["pdf", "docx"],
        accept_multiple_files=True,
        key="tr_arquivo",
    )

    if st.button("Analisar TR", type="primary", key="btn_tr", disabled=not _arq_tr):
        if not _api_key_tr:
            st.error("ANTHROPIC_API_KEY não configurada — configure via variável de ambiente ou secrets.toml.")
        else:
            try:
                with st.spinner("Extraindo texto e analisando com IA (pode levar 1-2 minutos)..."):
                    _texto_tr, _avisos_tr = etp_extrator.extrair_texto(_arq_tr)
                    _parecer_tr = ia_tr.analisar_tr(_texto_tr, _tipo_tr, _api_key_tr, _modelo_tr)
                st.session_state["tr_parecer"] = _parecer_tr
                st.session_state["tr_avisos"] = _avisos_tr
                st.session_state["tr_tipo_selecionado"] = _tipo_tr
                st.session_state["tr_nome"] = _arq_tr[0].name if _arq_tr else "TR"
                st.session_state.pop("tr_pdf", None)
                st.session_state.pop("tr_pdf_falhou", None)
            except ValueError as e:
                st.error(str(e))
            except RuntimeError as e:
                st.error(str(e))

    if "tr_parecer" in st.session_state:
        _pr_tr = st.session_state["tr_parecer"]
        _av_tr = st.session_state["tr_avisos"]
        _tipo_tr_saved = st.session_state["tr_tipo_selecionado"]
        _nome_tr = st.session_state["tr_nome"]

        for _aviso in _av_tr:
            st.warning(_safe_md(_aviso))

        st.divider()
        _adeq_tr = str(_pr_tr.get("adequacao_geral") or "INADEQUADO").strip().upper()
        _icone_adeq_tr = {"ADEQUADO": "🟢", "ADEQUADO COM RESSALVAS": "🟡", "INADEQUADO": "🔴"}
        st.subheader(f"{_icone_adeq_tr.get(_adeq_tr, '⚪')} Adequação Geral: {_safe_md(_adeq_tr)}")

        _dims_tr = _pr_tr.get("dimensoes") or {}
        _labels_tr = relatorio_tr.LABEL_DIMENSAO_POR_TIPO.get(_tipo_tr_saved, {})
        _ic_st_tr = {"ok": "✅", "alerta": "⚠️", "critico": "❌"}
        for _ch_tr, _lb_tr in _labels_tr.items():
            _d_tr = _dims_tr.get(_ch_tr) or {}
            _ic_tr = _ic_st_tr.get((_d_tr.get("status") or "ok").lower(), "ℹ️")
            with st.expander(f"{_ic_tr} {_lb_tr}"):
                st.write(_safe_md(_d_tr.get("descricao") or "—"))

        _criticos_tr = _pr_tr.get("pontos_criticos") or []
        if _criticos_tr:
            st.subheader("Pontos Críticos")
            for _c_tr in _criticos_tr:
                if _c_tr:
                    st.error(_safe_md(_c_tr))

        _recs_tr = _pr_tr.get("recomendacoes") or []
        if _recs_tr:
            st.subheader("Recomendações ao Gestor")
            for _r_tr in _recs_tr:
                if _r_tr:
                    st.info(_safe_md(_r_tr))

        with st.expander("Base Legal"):
            for _bl_tr in (_pr_tr.get("base_legal") or []):
                if _bl_tr:
                    st.write(f"• {_safe_md(_bl_tr)}")

        if "tr_pdf" not in st.session_state and not st.session_state.get("tr_pdf_falhou"):
            try:
                st.session_state["tr_pdf"] = relatorio_tr.gerar_pdf(_nome_tr, _tipo_tr_saved, _pr_tr)
            except Exception as _e_tr:
                st.session_state["tr_pdf_falhou"] = str(_e_tr) or "Erro desconhecido"
        if st.session_state.get("tr_pdf_falhou") and "tr_pdf" not in st.session_state:
            st.warning(f"PDF indisponível ({st.session_state['tr_pdf_falhou']}). Reanalise o TR para tentar novamente.")
        if "tr_pdf" in st.session_state:
            st.download_button(
                label="Baixar Relatório PDF",
                data=st.session_state["tr_pdf"],
                file_name="TR_auditoria.pdf",
                mime="application/pdf",
                key="tr_download",
            )

with aba8:
    st.subheader("Dosimetria de Sanções Administrativas")
    st.caption("Arts. 156-159 e 178 — Lei 14.133/2021")

    _api_key_sanc = _get_api_key()
    _modelo_sanc = os.environ.get("IA_LICITA_MODELO", "claude-haiku-4-5-20251001")

    _col_sanc1, _col_sanc2 = st.columns(2)
    with _col_sanc1:
        _cnpj_sanc = st.text_input(
            "CNPJ do Fornecedor",
            placeholder="00000000000000",
            key="sanc_cnpj",
        )
        _contrato_sanc = st.text_input(
            "Número do Contrato",
            placeholder="001/2024",
            key="sanc_contrato",
        )
        _valor_sanc = st.number_input(
            "Valor do Contrato (R$)",
            min_value=0.0,
            value=0.0,
            step=1000.0,
            format="%.2f",
            key="sanc_valor",
        )
    with _col_sanc2:
        _reincidencia_sanc = st.radio(
            "Reincidência do Fornecedor?",
            list(ia_sancoes.REINCIDENCIA_OPCOES.keys()),
            horizontal=True,
            key="sanc_reincidencia",
        )
        _autoridade_sanc = st.text_input(
            "Autoridade Competente",
            placeholder="ex: Secretário Municipal de Obras",
            key="sanc_autoridade",
        )
        _orgao_sanc = st.text_input(
            "Órgão / Entidade",
            placeholder="ex: Prefeitura de São Paulo",
            key="sanc_orgao",
        )

    _arq_sanc = st.file_uploader(
        "Envie o relatório / termo de ocorrência (PDF ou DOCX)",
        type=["pdf", "docx"],
        accept_multiple_files=True,
        key="sanc_arquivo",
    )

    if st.button(
        "Analisar Infração",
        type="primary",
        key="btn_sanc",
        disabled=not _arq_sanc,
    ):
        if not _api_key_sanc:
            st.error(
                "ANTHROPIC_API_KEY não configurada — "
                "configure via variável de ambiente ou secrets.toml."
            )
        else:
            try:
                with st.spinner(
                    "Analisando infração e gerando dosimetria (pode levar 2-3 minutos)..."
                ):
                    _texto_sanc, _avisos_sanc = etp_extrator.extrair_texto(_arq_sanc)

                    _dados_sanc = {
                        "cnpj":            _cnpj_sanc,
                        "numero_contrato": _contrato_sanc,
                        "valor_contrato":  _valor_sanc,
                        "reincidencia":    _reincidencia_sanc,
                        "autoridade":      _autoridade_sanc,
                        "orgao":           _orgao_sanc,
                    }

                    _parecer_sanc = ia_sancoes.analisar_dosimetria(
                        _dados_sanc, _texto_sanc, _api_key_sanc, _modelo_sanc
                    )

                    _minuta_sanc = ""
                    try:
                        _minuta_sanc = ia_sancoes.gerar_minuta(
                            _parecer_sanc, _dados_sanc, _api_key_sanc, _modelo_sanc
                        )
                    except (ValueError, RuntimeError) as _e_minuta:
                        st.warning(
                            f"Minuta não pôde ser gerada ({_e_minuta}). "
                            "O parecer de dosimetria está disponível normalmente."
                        )

                    st.session_state["sanc_parecer"]    = _parecer_sanc
                    st.session_state["sanc_minuta"]     = _minuta_sanc
                    st.session_state["sanc_dados"]      = _dados_sanc
                    st.session_state["sanc_avisos"]     = _avisos_sanc
                    st.session_state.pop("sanc_pdf", None)
                    st.session_state.pop("sanc_pdf_falhou", None)
            except (ValueError, RuntimeError) as _e_sanc:
                _msg_sanc = str(_e_sanc)
                if isinstance(_e_sanc, ValueError):
                    _msg_sanc += " Verifique se o arquivo não é uma imagem sem OCR."
                st.error(_msg_sanc)

    if "sanc_parecer" in st.session_state:
        _pr_sanc   = st.session_state["sanc_parecer"]
        _min_sanc  = st.session_state["sanc_minuta"]
        _dad_sanc  = st.session_state["sanc_dados"]
        _av_sanc   = st.session_state["sanc_avisos"]

        for _aviso_sanc in _av_sanc:
            st.warning(_safe_md(_aviso_sanc))

        st.divider()

        _enq_sanc  = _pr_sanc.get("enquadramento") or {}
        _dos_sanc  = _pr_sanc.get("dosimetria") or {}
        _alerta_sanc = _pr_sanc.get("alerta_criminal") or {}
        _tipo_sanc = str(_enq_sanc.get("tipo_sancao") or "multa")
        if _tipo_sanc == "multa" and not (_dad_sanc.get("valor_contrato") or 0):
            st.info(
                "Valor do contrato não informado — a estimativa monetária da multa não foi calculada."
            )
        _label_sanc = ia_sancoes.LABEL_SANCAO.get(_tipo_sanc, _tipo_sanc.title())

        _icone_sanc = {
            "advertencia":  "🟡",
            "multa":        "🟠",
            "impedimento":  "🔴",
            "inidoneidade": "⛔",
        }.get(_tipo_sanc, "⚪")

        _cor_badge_sanc = {
            "advertencia":  "#F39C12",
            "multa":        "#E67E22",
            "impedimento":  "#C0392B",
            "inidoneidade": "#8E44AD",
        }.get(_tipo_sanc, "#888888")

        st.markdown(
            f"<div style='background:{_cor_badge_sanc};padding:16px;border-radius:8px;"
            f"color:white;font-size:20px;font-weight:bold;text-align:center'>"
            f"{_icone_sanc} {html.escape(_label_sanc.upper())}</div>",
            unsafe_allow_html=True,
        )
        st.caption(
            f"Enquadramento: {_safe_md(_enq_sanc.get('artigo') or '')} — "
            f"{_safe_md(_enq_sanc.get('justificativa') or '')}"
        )
        st.divider()

        _fatos_sanc = str(_pr_sanc.get("fatos_apurados") or "—")
        st.info(f"**Fatos Apurados:** {_safe_md(_fatos_sanc)}")

        _condutas_sanc = _pr_sanc.get("condutas_identificadas") or []
        if _condutas_sanc and isinstance(_condutas_sanc, list):
            st.markdown("**Condutas Identificadas:**")
            for _c_sanc in _condutas_sanc:
                if _c_sanc:
                    st.markdown(f"• {_safe_md(_c_sanc)}")

        st.divider()
        st.markdown("**Dosimetria**")
        _nivel_sanc = str(_dos_sanc.get("nivel_gravidade") or "MÉDIO").strip().upper()
        _cor_nivel_sanc = {"LEVE": "#27AE60", "MÉDIO": "#F39C12", "GRAVE": "#C0392B"}.get(
            _nivel_sanc, "#888888"
        )
        st.markdown(
            f"<span style='background:{_cor_nivel_sanc};color:white;padding:4px 10px;"
            f"border-radius:4px;font-weight:bold'>{html.escape(_nivel_sanc)}</span>",
            unsafe_allow_html=True,
        )

        _agrav_sanc = [str(a) for a in (_dos_sanc.get("agravantes") or []) if a]
        _aten_sanc  = [str(a) for a in (_dos_sanc.get("atenuantes") or []) if a]

        _linhas_dos_sanc = [["Campo", "Valor"]]
        _linhas_dos_sanc.append(["Nível de Gravidade", _nivel_sanc])
        _linhas_dos_sanc.append(["Agravantes", ", ".join(_agrav_sanc) or "—"])
        _linhas_dos_sanc.append(["Atenuantes", ", ".join(_aten_sanc) or "—"])
        if _tipo_sanc == "multa":
            _pct_sanc = _dos_sanc.get("percentual_multa") or 0.5
            _val_sanc = _dos_sanc.get("valor_multa_estimado") or 0.0
            _linhas_dos_sanc.append(["% da Multa", f"{_pct_sanc:.1f}%"])
            if _val_sanc > 0:
                _linhas_dos_sanc.append(["Valor Estimado", f"R$ {_val_sanc:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")])
        elif _tipo_sanc in ("impedimento", "inidoneidade"):
            _prazo_sanc = _dos_sanc.get("prazo_sancao")
            _linhas_dos_sanc.append(["Prazo", f"{_prazo_sanc} ano(s)" if _prazo_sanc else "—"])

        st.table(_linhas_dos_sanc)

        if _alerta_sanc.get("configura_crime"):
            st.error(
                f"⚠️ **ALERTA CRIMINAL — Art. 178, Lei 14.133/2021**\n\n"
                f"**Artigo:** {_safe_md(_alerta_sanc.get('artigo_178') or '—')}\n\n"
                f"**Conduta:** {_safe_md(_alerta_sanc.get('descricao_conduta') or '—')}\n\n"
                f"**Recomendação:** {_safe_md(_alerta_sanc.get('recomendacao') or '—')}"
            )

        with st.expander("Base Legal"):
            for _bl_sanc in (_pr_sanc.get("base_legal") or []):
                if _bl_sanc:
                    st.write(f"• {_safe_md(_bl_sanc)}")

        if _min_sanc:
            with st.expander("Minuta do Ato Administrativo"):
                st.text(_min_sanc)

        if "sanc_pdf" not in st.session_state and not st.session_state.get("sanc_pdf_falhou"):
            try:
                st.session_state["sanc_pdf"] = relatorio_sancoes.gerar_pdf(
                    _dad_sanc, _pr_sanc, _min_sanc
                )
            except Exception as _e_sanc_pdf:
                st.session_state["sanc_pdf_falhou"] = str(_e_sanc_pdf) or "Erro desconhecido"
        if st.session_state.get("sanc_pdf_falhou") and "sanc_pdf" not in st.session_state:
            st.warning(
                f"PDF indisponível ({st.session_state['sanc_pdf_falhou']}). "
                "Reanalise para tentar novamente."
            )
        if "sanc_pdf" in st.session_state:
            st.download_button(
                label="⬇️ Baixar Relatório PDF",
                data=st.session_state["sanc_pdf"],
                file_name="sancoes_dosimetria.pdf",
                mime="application/pdf",
                key="sanc_download",
            )

with aba9:
    st.subheader("Reabilitação de Fornecedor")
    st.caption("Art. 163, Par. Único, Lei 14.133/2021")

    _api_key_reab = _get_api_key()
    _modelo_reab  = os.environ.get("IA_LICITA_MODELO", "claude-haiku-4-5-20251001")

    # ── Etapa 1: Identificação e Dados da Sanção ─────────────────────────────
    _col_reab1, _col_reab2 = st.columns(2)
    with _col_reab1:
        _cnpj_reab = st.text_input(
            "CNPJ do Fornecedor",
            placeholder="00.000.000/0000-00",
            key="reab_cnpj_input",
        )
    with _col_reab2:
        _tipo_sancao_opcoes = list(ia_reabilitacao.TIPOS_SANCAO.keys())
        _tipo_sancao_labels = list(ia_reabilitacao.TIPOS_SANCAO.values())
        _tipo_sancao_idx    = st.selectbox(
            "Tipo de Sanção",
            options=range(len(_tipo_sancao_opcoes)),
            format_func=lambda i: _tipo_sancao_labels[i],
            key="reab_tipo_sancao_select",
        )
    _tipo_sancao_reab = _tipo_sancao_opcoes[_tipo_sancao_idx]

    _col_reab3, _col_reab4 = st.columns(2)
    with _col_reab3:
        _data_sancao_reab = st.date_input(
            "Data de aplicação da sanção",
            value=None,
            key="reab_data_sancao",
        )
    with _col_reab4:
        _orgao_reab = st.text_input(
            "Órgão/Entidade sancionadora",
            placeholder="Ex.: Ministério da Gestão",
            key="reab_orgao",
        )

    _multa_aplicada_reab = st.radio(
        "Multa foi aplicada?",
        options=["Não", "Sim"],
        horizontal=True,
        key="reab_multa_aplicada",
    ) == "Sim"

    _multa_valor_reab = 0.0
    _multa_quitada_reab = False
    if _multa_aplicada_reab:
        _col_mv, _col_mq = st.columns(2)
        with _col_mv:
            _multa_valor_reab = st.number_input(
                "Valor da multa (R$)",
                min_value=0.0,
                value=0.0,
                step=100.0,
                format="%.2f",
                key="reab_multa_valor",
            )
        with _col_mq:
            _multa_quitada_reab = st.radio(
                "Multa quitada?",
                options=["Não", "Sim"],
                horizontal=True,
                key="reab_multa_quitada",
            ) == "Sim"

    _conds_ato_reab = st.text_area(
        "Condições definidas no ato punitivo (Condição IV)",
        placeholder="Descreva as condições impostas pelo ato que aplicou a sanção...",
        key="reab_conds_ato",
    )

    if st.button(
        "Verificar Elegibilidade →",
        type="primary",
        key="btn_reab_etapa1",
        disabled=not _cnpj_reab,
    ):
        for _k in ("reab_etapa", "reab_dados_empresa", "reab_prazo",
                   "reab_dados_sancao", "reab_respostas", "reab_parecer",
                   "reab_pdf_tecnico", "reab_pdf_requerimento",
                   "reab_data_referencia",
                   "reab_reparacao", "reab_reparacao_desc",
                   "reab_cond_ato_cumpridas", "reab_analise_juridica",
                   "reab_docs"):
            st.session_state.pop(_k, None)
        try:
            with st.spinner("Consultando CEIS/CNEP..."):
                _dados_empresa_reab = ddi_consultas.consultar(_cnpj_reab, 0.0)
            _dados_sancao_reab = {
                "tipo_sancao":            _tipo_sancao_reab,
                "data_aplicacao":         _data_sancao_reab,
                "orgao":                  _orgao_reab,
                "multa_aplicada":         _multa_aplicada_reab,
                "multa_valor":            _multa_valor_reab,
                "multa_quitada":          _multa_quitada_reab,
                "condicoes_ato_punitivo": _conds_ato_reab,
            }
            _data_ref_reab = _date_today.today()
            _prazo_reab = None
            if _data_sancao_reab:
                _prazo_reab = ia_reabilitacao.calcular_prazo(
                    _tipo_sancao_reab, _data_sancao_reab, _data_ref_reab
                )
            st.session_state["reab_dados_empresa"]   = _dados_empresa_reab
            st.session_state["reab_dados_sancao"]    = _dados_sancao_reab
            st.session_state["reab_prazo"]           = _prazo_reab
            st.session_state["reab_data_referencia"] = _data_ref_reab
            st.session_state["reab_etapa"]           = 2
        except ValueError as _e:
            st.error(str(_e))
        except Exception as _e:
            st.error(f"Erro ao consultar: {_e}")

    # Resultado CEIS/CNEP (Etapa 1)
    if st.session_state.get("reab_etapa", 0) >= 2:
        _de_reab = st.session_state["reab_dados_empresa"]
        _ds_reab = st.session_state["reab_dados_sancao"]
        _pr_reab = st.session_state.get("reab_prazo")

        st.divider()
        st.markdown(
            f"**Empresa:** {_safe_md(_de_reab.get('razao_social') or '-')} &nbsp;|&nbsp; "
            f"**CNPJ:** {_safe_md(_de_reab.get('cnpj') or '-')} &nbsp;|&nbsp; "
            f"**Situação:** {_safe_md(_de_reab.get('situacao') or '-')}"
        )

        _ceis_reab = _de_reab.get("ceis") or []
        _cnep_reab = _de_reab.get("cnep") or []
        if _ceis_reab:
            with st.expander(f"CEIS — {len(_ceis_reab)} registro(s)"):
                for _r in _ceis_reab:
                    st.write(
                        f"• **{_safe_md(_r.get('orgaoSancionador',''))}** — "
                        f"{_safe_md(_r.get('fundamentacaoLegal',''))} — "
                        f"Situação: {_safe_md(_r.get('situacaoAtual',''))}"
                    )
        else:
            st.info("Nenhum registro encontrado no CEIS para este CNPJ.")

        if _cnep_reab:
            with st.expander(f"CNEP — {len(_cnep_reab)} registro(s)"):
                for _r in _cnep_reab:
                    st.write(
                        f"• **{_safe_md(_r.get('orgaoSancionador',''))}** — "
                        f"{_safe_md(_r.get('tipoPenalidade',''))} — "
                        f"Situação: {_safe_md(_r.get('situacaoAtual',''))}"
                    )

        # ── Etapa 2: Questionário ──────────────────────────────────────────
        st.divider()
        st.markdown("### Etapa 2 — Avaliação das Condições (Art. 163, Par. Único)")

        if _pr_reab:
            if _pr_reab["atendido"]:
                st.success(
                    f"✅ **Condição III — Prazo mínimo: Decorrido** — "
                    f"{_pr_reab['anos_decorridos']}a {_pr_reab['meses_decorridos']}m "
                    f"(mínimo: {_pr_reab['prazo_minimo_anos']} ano(s))"
                )
            else:
                st.error(
                    f"❌ **Condição III — Prazo mínimo: NÃO decorrido** — "
                    f"Decorrido: {_pr_reab['anos_decorridos']}a {_pr_reab['meses_decorridos']}m. "
                    f"Mínimo exigido: {_pr_reab['prazo_minimo_anos']} ano(s). "
                    "Reabilitação ainda não é possível."
                )
        else:
            st.warning("Data de aplicação não informada — prazo não calculado.")

        _reparacao_reab = st.radio(
            "Condição I — Reparação integral do dano à Administração:",
            options=["Sim (integral)", "Parcial", "Não", "N.A. (sem dano apurado)"],
            horizontal=True,
            key="reab_reparacao",
        )
        _reparacao_desc_reab = st.text_input(
            "Descrição/comprovação da reparação:",
            placeholder="Ex.: ressarcimento comprovado via depósito identificado",
            key="reab_reparacao_desc",
        )
        _cond_ato_cumpridas_reab = st.radio(
            "Condição IV — Condições do ato punitivo foram cumpridas?",
            options=["Sim", "Parcial", "Não", "N.A. (sem condições no ato)"],
            horizontal=True,
            key="reab_cond_ato_cumpridas",
        )
        _analise_juridica_reab = st.radio(
            "Condição V — Análise jurídica prévia:",
            options=["Realizada", "Em andamento", "Não realizada"],
            horizontal=True,
            key="reab_analise_juridica",
        )

        _arqs_reab = st.file_uploader(
            "Documentos comprobatórios (opcional — PDF/DOCX)",
            type=["pdf", "docx"],
            accept_multiple_files=True,
            key="reab_docs",
        )

        if st.button(
            "Analisar Elegibilidade →",
            type="primary",
            key="btn_reab_etapa2",
        ):
            if not _api_key_reab:
                st.error(
                    "ANTHROPIC_API_KEY não configurada — "
                    "configure via variável de ambiente ou secrets.toml."
                )
            else:
                try:
                    _texto_reab = None
                    _avisos_reab = []
                    if _arqs_reab:
                        with st.spinner("Extraindo documentos..."):
                            _texto_reab, _avisos_reab = etp_extrator.extrair_texto(_arqs_reab)
                    for _av in _avisos_reab:
                        st.warning(_safe_md(_av))

                    _respostas_reab = {
                        "reparacao":           _reparacao_reab,
                        "reparacao_descricao": _reparacao_desc_reab,
                        "cond_ato_cumpridas":  _cond_ato_cumpridas_reab,
                        "analise_juridica":    _analise_juridica_reab,
                    }
                    with st.spinner("Analisando elegibilidade com IA..."):
                        _parecer_reab = ia_reabilitacao.analisar(
                            _ds_reab["tipo_sancao"],
                            _de_reab,
                            _ds_reab,
                            _respostas_reab,
                            _texto_reab,
                            _api_key_reab,
                            _modelo_reab,
                            data_referencia=st.session_state.get("reab_data_referencia"),
                        )
                    st.session_state["reab_respostas"]  = _respostas_reab
                    st.session_state["reab_parecer"]    = _parecer_reab
                    st.session_state["reab_etapa"]      = 3

                    try:
                        st.session_state["reab_pdf_tecnico"] = (
                            relatorio_reabilitacao.gerar_relatorio_tecnico(
                                _de_reab["cnpj"], _de_reab, _ds_reab, _parecer_reab
                            )
                        )
                    except Exception as _e_pdf:
                        st.session_state.pop("reab_pdf_tecnico", None)
                        st.warning(f"Relatório técnico indisponível: {_e_pdf}")

                    try:
                        st.session_state["reab_pdf_requerimento"] = (
                            relatorio_reabilitacao.gerar_minuta_requerimento(
                                _de_reab["cnpj"], _de_reab, _ds_reab, _parecer_reab
                            )
                        )
                    except Exception as _e_pdf:
                        st.session_state.pop("reab_pdf_requerimento", None)
                        st.warning(f"Minuta do requerimento indisponível: {_e_pdf}")

                except Exception as _e:
                    _msg = str(_e)
                    if isinstance(_e, ValueError):
                        _msg += " Verifique se o arquivo não é uma imagem sem OCR."
                    st.error(_msg)

    # ── Etapa 3: Resultado ────────────────────────────────────────────────────
    if st.session_state.get("reab_etapa", 0) >= 3:
        _pr3_reab = st.session_state.get("reab_parecer") or {}
        if not _pr3_reab:
            st.error("Resultado não encontrado. Por favor, refaça a análise.")
        else:
            st.divider()
            st.markdown("### Resultado da Análise de Elegibilidade")

            _pval_reab = str(_pr3_reab.get("parecer") or "INELEGÍVEL").strip().upper()
            _icone_reab = {
                "ELEGÍVEL":               "🟢",
                "ELEGÍVEL COM RESSALVAS": "🟡",
                "INELEGÍVEL":             "🔴",
            }
            st.subheader(f"{_icone_reab.get(_pval_reab, '⚪')} {_safe_md(_pval_reab)}")

            _conds_reab = _pr3_reab.get("condicoes_avaliadas") or []
            _ic_st_reab = {"ATENDIDA": "✅", "PARCIAL": "⚠️", "AUSENTE": "❌", "N.A.": "—"}
            for _c in _conds_reab:
                if not _c:
                    continue
                _st_c = str(_c.get("status") or "AUSENTE").strip().upper()
                _ic_c = _ic_st_reab.get(_st_c, "ℹ️")
                with st.expander(
                    f"{_ic_c} Condição {_safe_md(_c.get('numero','?'))}: "
                    f"{_safe_md(_c.get('descricao',''))}"
                ):
                    st.write(_safe_md(_c.get("observacao") or "—"))

            if _pr3_reab.get("sintese"):
                st.info(_safe_md(_pr3_reab["sintese"]))

            with st.expander("Base Legal"):
                for _bl in (_pr3_reab.get("base_legal") or []):
                    if _bl:
                        st.write(f"• {_safe_md(_bl)}")

            _col_dl1, _col_dl2 = st.columns(2)
            with _col_dl1:
                if "reab_pdf_tecnico" in st.session_state:
                    st.download_button(
                        label="⬇ Relatório Técnico (PDF)",
                        data=st.session_state["reab_pdf_tecnico"],
                        file_name="reabilitacao_relatorio_tecnico.pdf",
                        mime="application/pdf",
                        key="reab_dl_tecnico",
                    )
            with _col_dl2:
                if "reab_pdf_requerimento" in st.session_state:
                    st.download_button(
                        label="⬇ Minuta do Requerimento (PDF)",
                        data=st.session_state["reab_pdf_requerimento"],
                        file_name="reabilitacao_minuta_requerimento.pdf",
                        mime="application/pdf",
                        key="reab_dl_requerimento",
                    )

with aba10:
    st.subheader("Pesquisa de Preços de Mercado")
    st.caption("Art. 23, Lei 14.133/2021 + IN SEGES/MGI 65/2021")

    _api_key_pm = _get_api_key()

    _objeto_pm = st.text_input(
        "Objeto da pesquisa (descrição curta)",
        placeholder="ex.: Contratação de serviços de consultoria em tecnologia da informação",
        key="pm_objeto_input",
    )
    _tr_pm = st.file_uploader(
        "Termo de Referência (PDF ou DOCX)",
        type=["pdf", "docx"],
        key="pm_tr_arquivo",
    )

    if st.button(
        "Extrair Itens →",
        type="primary",
        key="btn_pm_extrair",
        disabled=not (_objeto_pm and _tr_pm),
    ):
        for _k in ("pm_etapa", "pm_objeto", "pm_itens_tr",
                   "pm_resultado", "pm_pdf_mapa", "pm_pdf_relatorio"):
            st.session_state.pop(_k, None)
        if not _api_key_pm:
            st.error("ANTHROPIC_API_KEY não configurada. Configure a variável de ambiente.")
        else:
            try:
                with st.spinner("Extraindo texto do TR..."):
                    _texto_tr_pm, _avisos_tr_pm = etp_extrator.extrair_texto([_tr_pm])
                for _av in _avisos_tr_pm:
                    st.warning(_safe_md(_av))
                with st.spinner("Identificando itens com IA..."):
                    _itens_pm = ia_pesquisa_mercado.extrair_itens_tr(
                        _texto_tr_pm, _api_key_pm
                    )
                st.session_state["pm_objeto"]   = _objeto_pm
                st.session_state["pm_itens_tr"] = _itens_pm
                st.session_state["pm_etapa"]    = 1
            except Exception as _e_pm:
                _msg_pm = str(_e_pm)
                if isinstance(_e_pm, ValueError):
                    _msg_pm += " Verifique se o arquivo não é uma imagem sem OCR."
                st.error(_msg_pm)

    if st.session_state.get("pm_etapa", 0) >= 1:
        st.divider()
        st.markdown("#### Itens identificados no TR")
        _itens_extr = st.session_state.get("pm_itens_tr") or []
        if _itens_extr:
            _tbl_header = "| # | Descrição | Unidade | Qtd estimada |\n|---|-----------|---------|-------------|\n"
            _tbl_rows   = "\n".join(
                f"| {i.get('id', idx + 1)} | {_safe_md(i.get('descricao', ''))} "
                f"| {_safe_md(i.get('unidade', 'un'))} "
                f"| {i.get('quantidade_estimada', '—')} |"
                for idx, i in enumerate(_itens_extr)
            )
            st.markdown(_tbl_header + _tbl_rows)
        else:
            st.warning("Nenhum item identificado. Verifique se o TR contém lista de itens.")

        _orcamentos_pm = st.file_uploader(
            "Orçamentos dos fornecedores (PDF ou DOCX, múltiplos arquivos)",
            type=["pdf", "docx"],
            accept_multiple_files=True,
            key="pm_orcamentos",
        )

        if st.button(
            "Analisar Pesquisa de Mercado →",
            type="primary",
            key="btn_pm_analisar",
            disabled=not _orcamentos_pm,
        ):
            if not _api_key_pm:
                st.error("ANTHROPIC_API_KEY não configurada. Configure a variável de ambiente.")
            else:
                try:
                    with st.spinner("Extraindo texto dos orçamentos..."):
                        _texto_orc_pm, _avisos_orc_pm = etp_extrator.extrair_texto(
                            _orcamentos_pm
                        )
                    for _av in _avisos_orc_pm:
                        st.warning(_safe_md(_av))
                    with st.spinner("Analisando pesquisa de mercado com IA..."):
                        _resultado_pm = ia_pesquisa_mercado.analisar(
                            st.session_state["pm_itens_tr"],
                            _texto_orc_pm,
                            _api_key_pm,
                        )
                    st.session_state["pm_resultado"] = _resultado_pm
                    st.session_state["pm_etapa"]     = 3
                    try:
                        st.session_state["pm_pdf_mapa"] = (
                            relatorio_pesquisa_mercado.gerar_mapa_precos(
                                st.session_state["pm_objeto"],
                                _resultado_pm["itens_avaliados"],
                                _resultado_pm["fornecedores"],
                                _resultado_pm["valor_total_estimado"],
                            )
                        )
                    except Exception as _e_mapa:
                        st.session_state.pop("pm_pdf_mapa", None)
                        st.warning(f"Mapa de Preços indisponível: {_e_mapa}")
                    try:
                        st.session_state["pm_pdf_relatorio"] = (
                            relatorio_pesquisa_mercado.gerar_relatorio_pesquisa(
                                st.session_state["pm_objeto"],
                                _resultado_pm["itens_avaliados"],
                                _resultado_pm["fornecedores"],
                                _resultado_pm["parecer_narrativo"],
                                _resultado_pm["status_geral"],
                                _resultado_pm["valor_total_estimado"],
                            )
                        )
                    except Exception as _e_rel:
                        st.session_state.pop("pm_pdf_relatorio", None)
                        st.warning(f"Relatório de Pesquisa indisponível: {_e_rel}")
                except Exception as _e_pm2:
                    _msg_pm2 = str(_e_pm2)
                    if isinstance(_e_pm2, ValueError):
                        _msg_pm2 += " Verifique se o arquivo não é uma imagem sem OCR."
                    st.error(_msg_pm2)

    if st.session_state.get("pm_etapa", 0) >= 3:
        _res_pm = st.session_state.get("pm_resultado") or {}
        if _res_pm:
            st.divider()
            st.markdown("### Resultado da Pesquisa de Mercado")

            _status_pm = str(_res_pm.get("status_geral") or "").strip().upper()
            _icone_pm = {
                "VÁLIDA":        "🟢",
                "COM RESSALVAS": "🟡",
                "INVÁLIDA":      "🔴",
            }
            st.subheader(
                f"{_icone_pm.get(_status_pm, '⚪')} {_safe_md(_status_pm)}"
            )

            for _item_pm in (_res_pm.get("itens_avaliados") or []):
                _desc_i = _safe_md(_item_pm.get("descricao") or "")
                _un_i   = _safe_md(_item_pm.get("unidade") or "un")
                _qtd_i  = _item_pm.get("quantidade_estimada")
                _qtd_str = f" — Qtd: {_qtd_i}" if _qtd_i else ""
                st.markdown(f"**Item {_item_pm['item_id']} — {_desc_i}** ({_un_i}){_qtd_str}")

                if _item_pm.get("preco_referencia") is not None:
                    st.markdown(
                        f"Preço de referência: **{_fmt_brl(_item_pm['preco_referencia'])}/{_un_i}**"
                    )
                    if _item_pm.get("subtotal_estimado"):
                        st.caption(
                            f"Subtotal estimado: {_fmt_brl(_item_pm['subtotal_estimado'])}"
                        )
                else:
                    st.warning(
                        f"⚠ Apenas {len(_item_pm.get('cotacoes_validas', []))} cotação(ões) "
                        "válida(s) — insuficiente (mínimo: 3)"
                    )

                for _exc_pm in (_item_pm.get("cotacoes_excluidas") or []):
                    st.caption(f"❌ Excluída: {_safe_md(_exc_pm.get('motivo', ''))}")

            if _res_pm.get("valor_total_estimado") is not None:
                st.metric(
                    "Valor Total Estimado",
                    _fmt_brl(_res_pm["valor_total_estimado"]),
                )

            if _res_pm.get("parecer_narrativo"):
                st.info(_safe_md(_res_pm["parecer_narrativo"]))

            _col_pm1, _col_pm2 = st.columns(2)
            with _col_pm1:
                if "pm_pdf_mapa" in st.session_state:
                    st.download_button(
                        label="⬇ Mapa de Preços (PDF)",
                        data=st.session_state["pm_pdf_mapa"],
                        file_name="pesquisa_mercado_mapa_precos.pdf",
                        mime="application/pdf",
                        key="pm_dl_mapa",
                    )
            with _col_pm2:
                if "pm_pdf_relatorio" in st.session_state:
                    st.download_button(
                        label="⬇ Relatório de Pesquisa (PDF)",
                        data=st.session_state["pm_pdf_relatorio"],
                        file_name="pesquisa_mercado_relatorio.pdf",
                        mime="application/pdf",
                        key="pm_dl_relatorio",
                    )
