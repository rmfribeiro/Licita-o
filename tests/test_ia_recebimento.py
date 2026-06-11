from __future__ import annotations
import json
import types
import urllib.error
import pytest
from unittest.mock import patch, MagicMock
import ia_recebimento
from .helpers import mock_urlopen as _mock_urlopen


class TestConstantes:
    def test_tipos_objeto_tem_3_entradas(self):
        assert len(ia_recebimento.TIPOS_OBJETO) == 3

    def test_tipos_objeto_chaves(self):
        assert set(ia_recebimento.TIPOS_OBJETO.keys()) == {"servico", "bem", "obra"}

    def test_parecer_options_tem_3_entradas(self):
        assert len(ia_recebimento.PARECER_OPTIONS) == 3

    def test_parecer_options_chaves(self):
        assert set(ia_recebimento.PARECER_OPTIONS.keys()) == {
            "APTO", "APTO COM RESSALVAS", "INAPTO"
        }

    def test_status_condicao_tem_3_entradas(self):
        assert len(ia_recebimento.STATUS_CONDICAO) == 3

    def test_status_condicao_chaves(self):
        assert set(ia_recebimento.STATUS_CONDICAO.keys()) == {
            "ATENDIDA", "PARCIAL", "AUSENTE"
        }

    def test_constantes_sao_mapping_proxy(self):
        assert isinstance(ia_recebimento.TIPOS_OBJETO, types.MappingProxyType)
        assert isinstance(ia_recebimento.PARECER_OPTIONS, types.MappingProxyType)
        assert isinstance(ia_recebimento.STATUS_CONDICAO, types.MappingProxyType)

    def test_condicoes_cobre_todos_tipos_com_duas_fases(self):
        for tipo in ia_recebimento.TIPOS_OBJETO:
            conds = ia_recebimento._CONDICOES_POR_TIPO[tipo]
            assert "provisorio" in conds
            assert "definitivo" in conds
            assert len(conds["provisorio"]) >= 1
            assert len(conds["definitivo"]) >= 1


def _dados_entrega_mock() -> dict:
    return {
        "numero_contrato": "010/2024",
        "objeto": "Serviços de manutenção predial",
        "data_entrega": "30/05/2025",
        "descricao_entrega": "Manutenção preventiva realizada em todos os andares",
        "nao_conformidades": "",
        "valor_contrato": 120000.0,
    }


def _parecer_api_mock() -> dict:
    return {
        "tipo_objeto": "servico",
        "recebimento_provisorio": {
            "parecer": "APTO",
            "condicoes": [
                {
                    "descricao": "Serviço prestado conforme TR",
                    "status": "ATENDIDA",
                    "observacao": "",
                }
            ],
            "pendencias": [],
            "sintese": "Condições de recebimento provisório atendidas.",
        },
        "recebimento_definitivo": {
            "parecer": "APTO COM RESSALVAS",
            "condicoes": [
                {
                    "descricao": "Qualidade confirmada após verificação",
                    "status": "PARCIAL",
                    "observacao": "Revisão técnica pendente",
                }
            ],
            "pendencias": ["Revisão técnica agendada para 30 dias"],
            "sintese": "Recebimento definitivo condicionado à revisão técnica.",
        },
        "recomendacoes_gerais": ["Agendar revisão técnica em 30 dias"],
        "base_legal": ["Art. 140, I, Lei 14.133/2021", "Art. 140, II, Lei 14.133/2021"],
    }


class TestAnalisar:
    def test_tipo_invalido_levanta_value_error(self):
        with pytest.raises(ValueError, match="Tipo de objeto inválido"):
            ia_recebimento.analisar("inexistente", {}, None, "key")

    def test_retorno_tem_recebimento_provisorio_e_definitivo(self):
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(_parecer_api_mock())):
            r = ia_recebimento.analisar("servico", _dados_entrega_mock(), None, "key")
        assert "recebimento_provisorio" in r
        assert "recebimento_definitivo" in r

    def test_cada_bloco_tem_campos_obrigatorios(self):
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(_parecer_api_mock())):
            r = ia_recebimento.analisar("servico", _dados_entrega_mock(), None, "key")
        for bloco_key in ("recebimento_provisorio", "recebimento_definitivo"):
            bloco = r[bloco_key]
            assert "parecer" in bloco
            assert "condicoes" in bloco
            assert "pendencias" in bloco
            assert "sintese" in bloco

    def test_tipo_objeto_local_prevalece(self):
        api_result = {**_parecer_api_mock(), "tipo_objeto": "bem"}
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(api_result)):
            r = ia_recebimento.analisar("servico", _dados_entrega_mock(), None, "key")
        assert r["tipo_objeto"] == "servico"

    def test_dados_entrega_preservados(self):
        dados = _dados_entrega_mock()
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(_parecer_api_mock())):
            r = ia_recebimento.analisar("servico", dados, None, "key")
        assert r["dados_entrega"] == dados

    def test_tipo_bem_funciona(self):
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(_parecer_api_mock())):
            r = ia_recebimento.analisar("bem", _dados_entrega_mock(), None, "key")
        assert isinstance(r, dict)

    def test_tipo_obra_funciona(self):
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(_parecer_api_mock())):
            r = ia_recebimento.analisar("obra", _dados_entrega_mock(), None, "key")
        assert isinstance(r, dict)

    def test_com_texto_docs_nao_levanta(self):
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(_parecer_api_mock())):
            r = ia_recebimento.analisar(
                "servico", _dados_entrega_mock(), "Texto do relatório fiscal", "key"
            )
        assert isinstance(r, dict)

    def test_http_error_levanta_runtime_error(self):
        http_err = urllib.error.HTTPError(
            url="https://api.anthropic.com/v1/messages",
            code=401, msg="Unauthorized", hdrs=None,
            fp=MagicMock(read=MagicMock(return_value=b'{"error":"invalid key"}')),
        )
        with patch("ia_utils.urllib.request.urlopen", side_effect=http_err):
            with pytest.raises(RuntimeError, match="HTTP 401"):
                ia_recebimento.analisar("servico", _dados_entrega_mock(), None, "key_invalida")

    def test_url_error_levanta_runtime_error(self):
        with patch("ia_utils.urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
            with pytest.raises(RuntimeError):
                ia_recebimento.analisar("servico", _dados_entrega_mock(), None, "key")

    def test_envelope_nao_json_levanta_runtime_error(self):
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(
            return_value=MagicMock(read=MagicMock(return_value=b"<html>Bad Gateway</html>"))
        )
        mock_cm.__exit__ = MagicMock(return_value=False)
        with patch("ia_utils.urllib.request.urlopen", return_value=mock_cm):
            with pytest.raises(RuntimeError, match="não é JSON válido"):
                ia_recebimento.analisar("servico", _dados_entrega_mock(), None, "key")

    def test_resposta_nao_dict_levanta_runtime_error(self):
        payload = json.dumps({"content": [{"text": "[1, 2, 3]"}]}).encode("utf-8")
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(
            return_value=MagicMock(read=MagicMock(return_value=payload))
        )
        mock_cm.__exit__ = MagicMock(return_value=False)
        with patch("ia_utils.urllib.request.urlopen", return_value=mock_cm):
            with pytest.raises(RuntimeError, match="objeto JSON esperado"):
                ia_recebimento.analisar("servico", _dados_entrega_mock(), None, "key")

    def test_content_null_levanta_runtime_error(self):
        payload = json.dumps({"content": None}).encode("utf-8")
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(
            return_value=MagicMock(read=MagicMock(return_value=payload))
        )
        mock_cm.__exit__ = MagicMock(return_value=False)
        with patch("ia_utils.urllib.request.urlopen", return_value=mock_cm):
            with pytest.raises(RuntimeError):
                ia_recebimento.analisar("servico", _dados_entrega_mock(), None, "key")

    def test_item_nao_dict_em_content_ignorado(self):
        payload = json.dumps(
            {"content": ["string_invalida", {"text": json.dumps(_parecer_api_mock())}]}
        ).encode("utf-8")
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(
            return_value=MagicMock(read=MagicMock(return_value=payload))
        )
        mock_cm.__exit__ = MagicMock(return_value=False)
        with patch("ia_utils.urllib.request.urlopen", return_value=mock_cm):
            r = ia_recebimento.analisar("servico", _dados_entrega_mock(), None, "key")
        assert "recebimento_provisorio" in r
