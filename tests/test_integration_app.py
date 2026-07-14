# -*- coding: utf-8 -*-
"""
Integration tests using Streamlit AppTest.

Validates that the app renders without unhandled exceptions, exposes the
expected UI structure (11 tabs, title), and rejects invalid inputs with
appropriate error messages — without making real API calls.

The conftest.py autouse fixture sets ANTHROPIC_API_KEY and CGU_API_KEY in
os.environ before each test, so all _get_api_key() calls return a dummy key.
"""
from __future__ import annotations

import json
import os
from unittest.mock import patch, MagicMock

import pytest
from streamlit.testing.v1 import AppTest

_APP_PATH = os.path.join(os.path.dirname(__file__), "..", "app.py")
_TIMEOUT = 30  # segundos


def _make_at() -> AppTest:
    return AppTest.from_file(_APP_PATH, default_timeout=_TIMEOUT)


# ---------------------------------------------------------------------------
# _safe_md
# ---------------------------------------------------------------------------

class TestSafeMd:
    """Verifica a ordem correta dos escapes em _safe_md."""

    def _import(self):
        import importlib, sys
        # importa app sem executar o Streamlit top-level
        spec = importlib.util.spec_from_file_location("app", _APP_PATH)
        mod = importlib.util.module_from_spec(spec)
        sys.modules.setdefault("app", mod)
        spec.loader.exec_module(mod)
        return mod._safe_md

    def test_ampersand_escapado(self):
        safe = self._import()
        assert safe("AT&T") == "AT&amp;T"

    def test_ampersand_primeiro_evita_duplo_encode(self):
        safe = self._import()
        # '#' vira '&#35;'; o '&' em '&#35;' NÃO deve ser re-escapado
        assert safe("#") == "&#35;"

    def test_ampersand_pre_escapado_duplo_encode(self):
        safe = self._import()
        # input já contém '&amp;' — deve virar '&amp;amp;' (comportamento correto: não passamos HTML pré-escapado)
        assert safe("&amp;") == "&amp;amp;"


# ---------------------------------------------------------------------------
# Inicialização
# ---------------------------------------------------------------------------

class TestAppInicialization:
    def test_app_carrega_sem_excecao(self):
        at = _make_at()
        at.run()
        assert not at.exception, f"App levantou exceção: {at.exception}"

    def test_titulo_ia_licita_visivel(self):
        at = _make_at()
        at.run()
        all_text = " ".join(str(e.value) for e in at.title)
        assert "IA-Licita" in all_text

    def test_onze_abas_existem(self):
        at = _make_at()
        at.run()
        # 11 abas principais + 2 sub-abas em aba6 (Alterações + Recebimento) = 13 total
        assert len(at.tabs) == 13, (
            f"Esperado 13 tabs (11 principais + 2 sub-abas), encontrado {len(at.tabs)}: "
            f"{[t.label for t in at.tabs]}"
        )
        main_labels = {t.label for t in at.tabs}
        assert "🔎 Instituto da Diligência" in main_labels
        assert "🔍 Due Diligence de Integridade" in main_labels

    def test_sem_excecao_importando_todos_os_modulos_ia(self):
        """Garante que nenhuma importação de ia_* falha na inicialização do app."""
        at = _make_at()
        at.run()
        # Se algum módulo levantasse exceção no import, at.exception não estaria vazio
        assert not at.exception


# ---------------------------------------------------------------------------
# Validação de entrada — Aba DDI (aba2)
# ---------------------------------------------------------------------------

class TestDDIValidacao:
    def test_botao_consultar_sem_cnpj_mostra_erro(self):
        at = _make_at()
        at.run()
        # CNPJ em branco → deve mostrar erro ao clicar
        at.button(key="btn_ddi_consultar").click().run()
        erros = [str(e.value) for e in at.error]
        avisos = [str(e.value) for e in at.warning]
        mensagens = erros + avisos
        assert any("CNPJ" in m or "cnpj" in m.lower() for m in mensagens), (
            f"Esperado aviso/erro sobre CNPJ vazio, mensagens encontradas: {mensagens}"
        )

    def test_botao_parecer_sem_api_key_mostra_erro(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        at = _make_at()
        # Simula estado pós-consulta para que btn_ddi_parecer apareça
        at.session_state["ddi_etapa"] = 2
        at.session_state["ddi_dados"] = {"razao_social": "Empresa X", "cnpj": "12345678000195"}
        at.session_state["ddi_cnpj"] = "12345678000195"
        at.session_state["ddi_valor"] = 100_000.0
        at.run()
        at.button(key="btn_ddi_parecer").click().run()
        erros = [str(e.value) for e in at.error]
        assert any("ANTHROPIC_API_KEY" in e or "ausente" in e.lower() for e in erros), (
            f"Esperado erro sobre API key ausente, erros encontrados: {erros}"
        )


# ---------------------------------------------------------------------------
# Validação de entrada — Aba ETP (aba3)
# ---------------------------------------------------------------------------

class TestETPValidacao:
    def test_botao_analisar_etp_sem_arquivo_mostra_erro(self):
        at = _make_at()
        at.run()
        at.button(key="btn_etp").click().run()
        erros = [str(e.value) for e in at.error]
        assert any(
            "arquivo" in e.lower() or "etp" in e.lower() or "upload" in e.lower()
            for e in erros
        ), f"Esperado erro sobre arquivo ausente, erros: {erros}"

    def test_botao_analisar_etp_sem_api_key_mostra_erro(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        at = _make_at()
        at.run()
        at.button(key="btn_etp").click().run()
        erros = [str(e.value) for e in at.error]
        assert any("ANTHROPIC_API_KEY" in e or "API" in e for e in erros), (
            f"Esperado erro sobre API key ausente, erros: {erros}"
        )


# ---------------------------------------------------------------------------
# Validação de entrada — Aba FID (aba11)
# ---------------------------------------------------------------------------

class TestFIDValidacao:
    def test_botao_analisar_fid_sem_situacao_mostra_erro(self):
        at = _make_at()
        at.run()
        # Razão social, CNPJ e situação em branco — deve mostrar erro
        at.button(key="btn_fid_analisar").click().run()
        erros = [str(e.value) for e in at.error]
        assert erros, f"Esperado pelo menos um erro ao clicar sem dados, erros: {erros}"

    def test_botao_analisar_fid_sem_api_key_mostra_erro(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        at = _make_at()
        # Preenche os campos mínimos via session_state
        at.session_state["fid_situacao"] = "Certidão FGTS vencida."
        at.run()
        at.button(key="btn_fid_analisar").click().run()
        erros = [str(e.value) for e in at.error]
        assert any("ANTHROPIC_API_KEY" in e or "API" in e for e in erros), (
            f"Esperado erro sobre API key ausente, erros: {erros}"
        )


# ---------------------------------------------------------------------------
# Persistência de estado — resultados ficam após reruns
# ---------------------------------------------------------------------------

class TestEstadoSessao:
    def test_session_state_fid_etapa_persiste_apos_run(self):
        at = _make_at()
        at.session_state["fid_etapa"] = "resultado"
        at.run()
        assert at.session_state["fid_etapa"] == "resultado"

    def test_session_state_ddi_etapa_persiste_apos_run(self):
        at = _make_at()
        at.session_state["ddi_etapa"] = 2
        at.session_state["ddi_dados"] = {"razao_social": "Empresa Z", "cnpj": "00000000000191"}
        at.session_state["ddi_cnpj"] = "00000000000191"
        at.session_state["ddi_valor"] = None
        at.run()
        assert at.session_state["ddi_etapa"] == 2
