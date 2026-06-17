from __future__ import annotations
import io
import json
import pytest
import urllib.error
from unittest.mock import patch, MagicMock
import ia_integridade
from .helpers import mock_urlopen as _mock_urlopen


def _nao() -> dict:
    return {k: "Não" for k, _ in ia_integridade.QUESTOES_PIP}


def _sim() -> dict:
    return {k: "Sim" for k, _ in ia_integridade.QUESTOES_PIP}


class TestAplicarPiso:
    def test_all_nao_retorna_inexistente(self):
        assert ia_integridade._aplicar_piso(_nao(), "CONSOLIDADO") == "INEXISTENTE"

    def test_regra1_tem_precedencia_sobre_regra2(self):
        # All-Não satisfies both Regra 1 and Regra 2 conditions.
        # Regra 1 must win: result must be INEXISTENTE, not INICIAL.
        result = ia_integridade._aplicar_piso(_nao(), "CONSOLIDADO")
        assert result == "INEXISTENTE"
        assert result != "INICIAL"

    def test_ato_formal_nao_responsavel_nao_cap_inicial(self):
        r = _sim()
        r["q_ato_formal"] = "Não"
        r["q_responsavel_designado"] = "Não"
        assert ia_integridade._aplicar_piso(r, "CONSOLIDADO") == "INICIAL"

    def test_ato_formal_parcialmente_responsavel_parcialmente_cap_inicial(self):
        r = _sim()
        r["q_ato_formal"] = "Parcialmente"
        r["q_responsavel_designado"] = "Parcialmente"
        assert ia_integridade._aplicar_piso(r, "CONSOLIDADO") == "INICIAL"

    def test_ato_formal_nao_responsavel_parcialmente_cap_inicial(self):
        r = _sim()
        r["q_ato_formal"] = "Não"
        r["q_responsavel_designado"] = "Parcialmente"
        assert ia_integridade._aplicar_piso(r, "CONSOLIDADO") == "INICIAL"

    def test_tudo_sim_aceita_resposta_ia(self):
        assert ia_integridade._aplicar_piso(_sim(), "CONSOLIDADO") == "CONSOLIDADO"

    def test_cap_nao_eleva_maturidade(self):
        # Piso nunca eleva — se IA já retornou INICIAL, fica INICIAL
        r = _sim()
        r["q_ato_formal"] = "Não"
        r["q_responsavel_designado"] = "Não"
        assert ia_integridade._aplicar_piso(r, "INICIAL") == "INICIAL"


def _parecer_mock(maturidade: str = "EM DESENVOLVIMENTO") -> dict:
    return {
        "maturidade_geral": maturidade,
        "dimensoes": {
            "compromisso_alta_gestao": {"nivel": maturidade, "achados": ["a"], "recomendacoes": ["r"]},
            "diretrizes_integridade":  {"nivel": maturidade, "achados": [], "recomendacoes": []},
            "base_legal_normativa":    {"nivel": maturidade, "achados": [], "recomendacoes": []},
            "responsabilizacao":       {"nivel": maturidade, "achados": [], "recomendacoes": []},
            "metodologia_gestao":      {"nivel": maturidade, "achados": [], "recomendacoes": []},
            "tres_linhas_defesa":      {"nivel": maturidade, "achados": [], "recomendacoes": []},
        },
        "prioridades": ["Ação 1", "Ação 2", "Ação 3"],
        "resumo_executivo": "Resumo para o prefeito.",
        "base_legal": ["Decreto 11.129/2022"],
    }


class TestDiagnosticar:
    @patch("ia_utils.urllib.request.urlopen")
    def test_retorna_estrutura_correta(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen(_parecer_mock())
        resultado = ia_integridade.diagnosticar(_sim(), None, "sk-test")
        for campo in ("maturidade_geral", "dimensoes", "prioridades", "resumo_executivo", "base_legal"):
            assert campo in resultado, f"Campo ausente: {campo}"

    @patch("ia_utils.urllib.request.urlopen")
    def test_6_dimensoes_presentes(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen(_parecer_mock())
        resultado = ia_integridade.diagnosticar(_sim(), None, "sk-test")
        for dim in (
            "compromisso_alta_gestao", "diretrizes_integridade", "base_legal_normativa",
            "responsabilizacao", "metodologia_gestao", "tres_linhas_defesa",
        ):
            assert dim in resultado["dimensoes"], f"Dimensão ausente: {dim}"

    @patch("ia_utils.urllib.request.urlopen")
    def test_maturidade_valida(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen(_parecer_mock())
        resultado = ia_integridade.diagnosticar(_sim(), None, "sk-test")
        assert resultado["maturidade_geral"] in (
            "INEXISTENTE", "INICIAL", "EM DESENVOLVIMENTO", "CONSOLIDADO"
        )

    @patch("ia_utils.urllib.request.urlopen")
    def test_piso_rebaixa_maturidade_seta_aviso_piso_maturidade(self, mock_urlopen):
        # IA diz CONSOLIDADO, piso rebaixa para INEXISTENTE → _aviso_piso_maturidade gravado
        mock_urlopen.return_value = _mock_urlopen(_parecer_mock("CONSOLIDADO"))
        resultado = ia_integridade.diagnosticar(_nao(), None, "sk-test")
        assert resultado["maturidade_geral"] == "INEXISTENTE"
        assert resultado.get("_aviso_piso_maturidade") == "CONSOLIDADO"

    @patch("ia_utils.urllib.request.urlopen")
    def test_texto_docs_incluido_no_prompt(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen(_parecer_mock())
        ia_integridade.diagnosticar(_sim(), "DOCUMENTO_MARCADOR_XYZ", "sk-test")
        corpo = json.loads(mock_urlopen.call_args[0][0].data.decode("utf-8"))
        assert "DOCUMENTO_MARCADOR_XYZ" in corpo["messages"][0]["content"]

    @patch("ia_utils.urllib.request.urlopen")
    def test_ddi_context_incluido_se_fornecido(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen(_parecer_mock())
        parecer_ddi = {
            "dimensoes": {
                "programa_integridade": {
                    "status": "critico",
                    "descricao": "Sem programa formal",
                    "obrigatorio": True,
                    "pro_etica": False,
                }
            }
        }
        ia_integridade.diagnosticar(_sim(), None, "sk-test", parecer_ddi=parecer_ddi)
        corpo = json.loads(mock_urlopen.call_args[0][0].data.decode("utf-8"))
        prompt = corpo["messages"][0]["content"]
        assert "critico" in prompt

    @patch("ia_utils.urllib.request.urlopen")
    def test_ddi_none_nao_quebra(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen(_parecer_mock())
        resultado = ia_integridade.diagnosticar(_sim(), None, "sk-test", parecer_ddi=None)
        assert "maturidade_geral" in resultado

    @patch("ia_utils.urllib.request.urlopen")
    def test_maturidade_invalida_da_ia_normalizada_para_inexistente(self, mock_urlopen):
        parecer_ruim = _parecer_mock()
        parecer_ruim["maturidade_geral"] = "DESCONHECIDO"
        mock_urlopen.return_value = _mock_urlopen(parecer_ruim)
        resultado = ia_integridade.diagnosticar(_sim(), None, "sk-test")
        assert resultado["maturidade_geral"] == "INEXISTENTE"

    @patch("ia_utils.urllib.request.urlopen")
    def test_maturidade_invalida_seta_aviso_maturidade(self, mock_urlopen):
        parecer_ruim = _parecer_mock()
        parecer_ruim["maturidade_geral"] = "ÓTIMO"
        mock_urlopen.return_value = _mock_urlopen(parecer_ruim)
        resultado = ia_integridade.diagnosticar(_sim(), None, "sk-test")
        assert resultado["maturidade_geral"] == "INEXISTENTE"
        assert resultado.get("_aviso_maturidade") == "ÓTIMO"

    @patch("ia_utils.urllib.request.urlopen")
    def test_maturidade_none_nao_seta_aviso(self, mock_urlopen):
        parecer_ruim = _parecer_mock()
        parecer_ruim["maturidade_geral"] = None
        mock_urlopen.return_value = _mock_urlopen(parecer_ruim)
        resultado = ia_integridade.diagnosticar(_sim(), None, "sk-test")
        assert resultado["maturidade_geral"] == "INEXISTENTE"
        assert "_aviso_maturidade" not in resultado

    @patch("ia_utils.urllib.request.urlopen")
    def test_maturidade_vazia_seta_aviso_vazio(self, mock_urlopen):
        parecer_ruim = _parecer_mock()
        parecer_ruim["maturidade_geral"] = ""
        mock_urlopen.return_value = _mock_urlopen(parecer_ruim)
        resultado = ia_integridade.diagnosticar(_sim(), None, "sk-test")
        assert resultado["maturidade_geral"] == "INEXISTENTE"
        assert resultado.get("_aviso_maturidade") == ""

    @patch("ia_utils.urllib.request.urlopen")
    def test_pop_remove_aviso_piso_maturidade_injetado_pelo_llm(self, mock_urlopen):
        # Pop defensivo deve apagar _aviso_piso_maturidade injetado pelo LLM quando piso não dispara
        parecer_injetado = _parecer_mock("EM DESENVOLVIMENTO")
        parecer_injetado["_aviso_piso_maturidade"] = "FORJADO"
        mock_urlopen.return_value = _mock_urlopen(parecer_injetado)
        resultado = ia_integridade.diagnosticar(_sim(), None, "sk-test")
        assert resultado["maturidade_geral"] == "EM DESENVOLVIMENTO"
        assert "_aviso_piso_maturidade" not in resultado

    @patch("ia_utils.urllib.request.urlopen")
    def test_pop_remove_aviso_maturidade_injetado_pelo_llm(self, mock_urlopen):
        # Pop defensivo deve apagar _aviso_maturidade injetado pelo LLM quando maturidade é válida
        parecer_injetado = _parecer_mock("CONSOLIDADO")
        parecer_injetado["_aviso_maturidade"] = "FORJADO"
        mock_urlopen.return_value = _mock_urlopen(parecer_injetado)
        resultado = ia_integridade.diagnosticar(_sim(), None, "sk-test")
        assert resultado["maturidade_geral"] == "CONSOLIDADO"
        assert "_aviso_maturidade" not in resultado

    @patch("ia_utils.urllib.request.urlopen")
    def test_httperror_inclui_body_na_mensagem(self, mock_urlopen):
        fp = io.BytesIO(b'{"error": "invalid_api_key"}')
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "https://api.anthropic.com/v1/messages", 401, "Unauthorized", {}, fp
        )
        with pytest.raises(RuntimeError) as exc_info:
            ia_integridade.diagnosticar(_sim(), None, "sk-test")
        assert "401" in str(exc_info.value)
        assert "invalid_api_key" in str(exc_info.value)
