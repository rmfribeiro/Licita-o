# -*- coding: utf-8 -*-
"""
IA-Licita — demo web (Streamlit).
Sobe um edital em PDF e mostra a auditoria na hora. Para publicar, ver DEPLOY.md.
Rodar localmente:  streamlit run app.py
"""
import os, io, json, html, tempfile
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

AQUI = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(AQUI, "regras_14133.json"), encoding="utf-8") as _f:
    REGRAS = json.load(_f)["regras"]
BASE_RAG = os.path.join(AQUI, "base_juridica.json")
COR = {"inconformidade": "#C0392B", "alerta": "#E67E22", "revisar": "#2E75B6", "ok": "#27AE60"}
ROTULO = {"inconformidade": "Inconformidade", "alerta": "Alerta", "revisar": "Revisar", "ok": "Conforme"}


def _safe_md(s: object) -> str:
    return str(s).replace('[', '&#91;')


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

aba1, aba2, aba3, aba4, aba5, aba6 = st.tabs([
    "📄 Auditoria de Edital",
    "🔍 Due Diligence de Integridade",
    "📋 Auditoria de ETP",
    "🏛️ Diagnóstico de Integridade",
    "🏢 Avaliação de PI",
    "⚖️ Alterações Contratuais",
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
                try:
                    _val = st.secrets.get("ANTHROPIC_API_KEY")
                    if _val:
                        os.environ["ANTHROPIC_API_KEY"] = str(_val)
                except _SecretsNotFound:
                    pass
                except Exception as _e:
                    st.warning(f"Erro ao carregar chave de API: {_e}")

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
        st.subheader(f"{_icone_risco.get(risco, '⚪')} Risco Geral: {risco}")

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

    _api_key_etp = os.environ.get("ANTHROPIC_API_KEY")
    if not _api_key_etp:
        try:
            _val = st.secrets.get("ANTHROPIC_API_KEY")
            if _val:
                _api_key_etp = str(_val)
        except _SecretsNotFound:
            pass
        except Exception as _e:
            st.warning(f"Erro ao ler configurações (secrets.toml): {_e}")
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
            st.warning(_aviso)

        st.divider()
        _adeq = str(_pr.get("adequacao_geral") or "INADEQUADO").strip().upper()
        _icone_adeq = {"ADEQUADO": "🟢", "ADEQUADO COM RESSALVAS": "🟡", "INADEQUADO": "🔴"}
        st.subheader(f"{_icone_adeq.get(_adeq, '⚪')} Adequação Geral: {_adeq}")

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

    _api_key_pip = os.environ.get("ANTHROPIC_API_KEY")
    if not _api_key_pip:
        try:
            _val = st.secrets.get("ANTHROPIC_API_KEY")
            if _val:
                _api_key_pip = str(_val)
        except _SecretsNotFound:
            pass
        except Exception as _e:
            st.warning(f"Erro ao ler configurações (secrets.toml): {_e}")
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
            st.warning(_aviso)

        st.divider()
        _mat_pip = str(_pr_pip.get("maturidade_geral") or "INEXISTENTE").strip().upper()
        st.subheader(f"{ia_integridade.ICONE_MATURIDADE.get(_mat_pip, '⚪')} Maturidade Geral: {_mat_pip}")

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

    _api_key_pi = os.environ.get("ANTHROPIC_API_KEY")
    if not _api_key_pi:
        try:
            _val = st.secrets.get("ANTHROPIC_API_KEY")
            if _val:
                _api_key_pi = str(_val)
        except _SecretsNotFound:
            pass
        except Exception as _e:
            st.warning(f"Erro ao ler configurações (secrets.toml): {_e}")
    _modelo_pi = os.environ.get("IA_LICITA_MODELO", "claude-haiku-4-5-20251001")

    # ── Etapa 1: Identificação ─────────────────────────────────────────────
    st.markdown("### Etapa 1 — Identificação da Empresa")
    _col_cnpj, _col_hip = st.columns([2, 3])
    _cnpj_pi = _col_cnpj.text_input("CNPJ da empresa", key="pi_cnpj_input",
                                     placeholder="00.000.000/0000-00")
    _hip_opcoes = {k: v for k, v in ia_pi_empresas.HIPOTESES.items()}
    _hip_chaves = list(_hip_opcoes.keys())
    _hip_labels = list(_hip_opcoes.values())
    _hip_idx = _col_hip.selectbox(
        "Hipótese legal",
        options=range(len(_hip_chaves)),
        format_func=lambda i: _hip_labels[i],
        key="pi_hipotese_select",
    )
    _hipotese_pi = _hip_chaves[_hip_idx]

    if st.button("Consultar empresa", key="btn_pi_etapa1", disabled=not _cnpj_pi):
        for _k in ("pi_etapa", "pi_dados", "pi_cnpj", "pi_hipotese",
                   "pi_respostas", "pi_parecer", "pi_pdf"):
            st.session_state.pop(_k, None)
        try:
            with st.spinner("Consultando Receita Federal..."):
                _dados_pi = ddi_consultas.consultar(_cnpj_pi, 0.0)
            st.session_state["pi_dados"] = _dados_pi
            st.session_state["pi_cnpj"] = _dados_pi["cnpj"]
            st.session_state["pi_hipotese"] = _hipotese_pi
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
        if _hip_pi == "grande_vulto" and "GRANDE" not in str(_d_pi.get("porte") or "").upper():
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
                        _parecer_pi = ia_pi_empresas.avaliar(
                            _respostas_pi,
                            st.session_state["pi_hipotese"],
                            _texto_pi,
                            _api_key_pi,
                            _modelo_pi,
                        )
                    st.session_state["pi_respostas"] = _respostas_pi
                    st.session_state["pi_parecer"] = _parecer_pi
                    st.session_state["pi_etapa"] = 3
                    _razao_pi = st.session_state["pi_dados"].get("razao_social") or ""
                    try:
                        st.session_state["pi_pdf"] = relatorio_pi_empresas.gerar_pdf(
                            cnpj=st.session_state["pi_cnpj"],
                            razao_social=_razao_pi,
                            hipotese=st.session_state["pi_hipotese"],
                            parecer=_parecer_pi,
                        )
                    except Exception as _pdf_e:
                        st.session_state.pop("pi_pdf", None)
                        st.warning(f"Não foi possível gerar o PDF: {_pdf_e}")
                except (ValueError, RuntimeError) as _e:
                    st.error(str(_e))

    # ── Etapa 3: Resultado ─────────────────────────────────────────────────
    if st.session_state.get("pi_etapa", 0) >= 3:
        _pr_pi = st.session_state["pi_parecer"]
        _sc_pi = _pr_pi.get("scores") or {}

        st.divider()
        st.markdown("### Resultado da Avaliação")

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

with aba6:
    st.subheader("Analisador de Alterações Contratuais")
    st.caption(
        "Art. 124 II 'd' · Art. 25 §8º · Art. 137 §2º — Lei 14.133/2021 · Art. 37 XXI CF/88"
    )

    _api_key_cont = os.environ.get("ANTHROPIC_API_KEY")
    if not _api_key_cont:
        try:
            _val = st.secrets.get("ANTHROPIC_API_KEY")
            if _val:
                _api_key_cont = str(_val)
        except _SecretsNotFound:
            pass
        except Exception as _e:
            st.warning(f"Erro ao ler configurações (secrets.toml): {_e}")
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
                        st.warning(_av_cont)
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
        _parecer_val_cont = {
            "DEFERIVEL":               "DEFERÍVEL",
            "DEFERIVEL COM RESSALVAS": "DEFERÍVEL COM RESSALVAS",
            "INDEFERIVEL":             "INDEFERÍVEL",
        }.get(_parecer_val_cont, _parecer_val_cont)
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
