from __future__ import annotations
import io
import pytest
import urllib.error
import ia_integridade


def _nao() -> dict:
    return {k: "Não" for k in ia_integridade._CHAVES_QUESTIONARIO}


def _sim() -> dict:
    return {k: "Sim" for k in ia_integridade._CHAVES_QUESTIONARIO}


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


import json
from unittest.mock import patch, MagicMock


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


def _mock_urlopen(parecer: dict):
    payload = json.dumps({"content": [{"text": json.dumps(parecer)}]}).encode("utf-8")
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(
        return_value=MagicMock(read=MagicMock(return_value=payload))
    )
    mock_cm.__exit__ = MagicMock(return_value=False)
    return mock_cm


class TestDiagnosticar:
    @patch("ia_integridade.urllib.request.urlopen")
    def test_retorna_estrutura_correta(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen(_parecer_mock())
        resultado = ia_integridade.diagnosticar(_sim(), None, "sk-test")
        for campo in ("maturidade_geral", "dimensoes", "prioridades", "resumo_executivo", "base_legal"):
            assert campo in resultado, f"Campo ausente: {campo}"

    @patch("ia_integridade.urllib.request.urlopen")
    def test_6_dimensoes_presentes(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen(_parecer_mock())
        resultado = ia_integridade.diagnosticar(_sim(), None, "sk-test")
        for dim in (
            "compromisso_alta_gestao", "diretrizes_integridade", "base_legal_normativa",
            "responsabilizacao", "metodologia_gestao", "tres_linhas_defesa",
        ):
            assert dim in resultado["dimensoes"], f"Dimensão ausente: {dim}"

    @patch("ia_integridade.urllib.request.urlopen")
    def test_maturidade_valida(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen(_parecer_mock())
        resultado = ia_integridade.diagnosticar(_sim(), None, "sk-test")
        assert resultado["maturidade_geral"] in (
            "INEXISTENTE", "INICIAL", "EM DESENVOLVIMENTO", "CONSOLIDADO"
        )

    @patch("ia_integridade.urllib.request.urlopen")
    def test_piso_aplicado_all_nao(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen(_parecer_mock("CONSOLIDADO"))
        resultado = ia_integridade.diagnosticar(_nao(), None, "sk-test")
        assert resultado["maturidade_geral"] == "INEXISTENTE"

    @patch("ia_integridade.urllib.request.urlopen")
    def test_texto_docs_incluido_no_prompt(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen(_parecer_mock())
        ia_integridade.diagnosticar(_sim(), "DOCUMENTO_MARCADOR_XYZ", "sk-test")
        corpo = json.loads(mock_urlopen.call_args[0][0].data.decode("utf-8"))
        assert "DOCUMENTO_MARCADOR_XYZ" in corpo["messages"][0]["content"]

    @patch("ia_integridade.urllib.request.urlopen")
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

    @patch("ia_integridade.urllib.request.urlopen")
    def test_ddi_none_nao_quebra(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen(_parecer_mock())
        resultado = ia_integridade.diagnosticar(_sim(), None, "sk-test", parecer_ddi=None)
        assert "maturidade_geral" in resultado

    @patch("ia_integridade.urllib.request.urlopen")
    def test_maturidade_invalida_da_ia_normalizada_para_inexistente(self, mock_urlopen):
        parecer_ruim = _parecer_mock()
        parecer_ruim["maturidade_geral"] = "DESCONHECIDO"
        mock_urlopen.return_value = _mock_urlopen(parecer_ruim)
        resultado = ia_integridade.diagnosticar(_sim(), None, "sk-test")
        assert resultado["maturidade_geral"] == "INEXISTENTE"

    @patch("ia_integridade.urllib.request.urlopen")
    def test_httperror_inclui_body_na_mensagem(self, mock_urlopen):
        fp = io.BytesIO(b'{"error": "invalid_api_key"}')
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "https://api.anthropic.com/v1/messages", 401, "Unauthorized", {}, fp
        )
        with pytest.raises(RuntimeError) as exc_info:
            ia_integridade.diagnosticar(_sim(), None, "sk-test")
        assert "401" in str(exc_info.value)
        assert "invalid_api_key" in str(exc_info.value)
