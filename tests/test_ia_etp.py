from __future__ import annotations
import io
import json
import pytest
import urllib.error
from unittest.mock import patch, MagicMock
import ia_etp


def _parecer_mock() -> dict:
    return {
        "adequacao_geral": "ADEQUADO COM RESSALVAS",
        "dimensoes": {
            "descricao_necessidade":       {"status": "ok",     "descricao": "Necessidade bem descrita."},
            "alinhamento_estrategico":     {"status": "ok",     "descricao": "Alinhado ao PPA."},
            "requisitos_contratacao":      {"status": "alerta", "descricao": "Requisitos incompletos."},
            "levantamento_mercado":        {"status": "ok",     "descricao": "Mercado pesquisado."},
            "estimativa_quantidade_valor": {"status": "alerta", "descricao": "Metodologia ausente."},
            "sustentabilidade":            {"status": "ok",     "descricao": "Critérios presentes."},
            "parcelamento":                {"status": "ok",     "descricao": "Justificado."},
            "posicionamento_conclusivo":   {"status": "ok",     "descricao": "Favorável."},
        },
        "pontos_criticos": ["Requisitos técnicos incompletos."],
        "recomendacoes": ["Detalhar especificações técnicas."],
        "base_legal": ["IN SEGES/MGI 58/2022", "Lei 14.133/2021, art. 18, I"],
    }


def _mock_urlopen(parecer: dict):
    resposta = json.dumps({"content": [{"text": json.dumps(parecer)}]}).encode("utf-8")
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=resposta)))
    mock_cm.__exit__ = MagicMock(return_value=False)
    return mock_cm


class TestAnalisarEtp:
    @patch("ia_utils.urllib.request.urlopen")
    def test_retorna_estrutura_correta(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen(_parecer_mock())

        resultado = ia_etp.analisar_etp("Texto do ETP", "sk-test", "claude-haiku-4-5-20251001")

        assert "adequacao_geral" in resultado
        assert "dimensoes" in resultado
        assert "pontos_criticos" in resultado
        assert "recomendacoes" in resultado
        assert "base_legal" in resultado

    @patch("ia_utils.urllib.request.urlopen")
    def test_todas_as_8_dimensoes_presentes(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen(_parecer_mock())

        resultado = ia_etp.analisar_etp("Texto", "sk-test", "claude-haiku-4-5-20251001")

        dims = resultado["dimensoes"]
        for esperada in [
            "descricao_necessidade", "alinhamento_estrategico", "requisitos_contratacao",
            "levantamento_mercado", "estimativa_quantidade_valor", "sustentabilidade",
            "parcelamento", "posicionamento_conclusivo",
        ]:
            assert esperada in dims, f"Dimensão ausente: {esperada}"

    @patch("ia_utils.urllib.request.urlopen")
    def test_adequacao_geral_valida(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen(_parecer_mock())

        resultado = ia_etp.analisar_etp("Texto", "sk-test", "claude-haiku-4-5-20251001")

        assert resultado["adequacao_geral"] in (
            "ADEQUADO", "ADEQUADO COM RESSALVAS", "INADEQUADO"
        )

    @patch("ia_utils.urllib.request.urlopen")
    def test_modelo_padrao_usado_se_omitido(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen(_parecer_mock())

        resultado = ia_etp.analisar_etp("Texto", "sk-test")

        assert "adequacao_geral" in resultado

    @patch("ia_utils.urllib.request.urlopen")
    def test_httperror_inclui_body_na_mensagem(self, mock_urlopen):
        fp = io.BytesIO(b'{"error": "invalid_api_key"}')
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "https://api.anthropic.com/v1/messages", 401, "Unauthorized", {}, fp
        )
        with pytest.raises(RuntimeError) as exc_info:
            ia_etp.analisar_etp("Texto do ETP", "sk-test")
        assert "401" in str(exc_info.value)
        assert "invalid_api_key" in str(exc_info.value)
