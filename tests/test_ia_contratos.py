from __future__ import annotations
import json
import types
import urllib.error
import pytest
from unittest.mock import patch, MagicMock
import ia_contratos
from .helpers import mock_urlopen as _mock_urlopen


class TestConstantes:
    def test_tipos_alteracao_tem_3_tipos(self):
        assert len(ia_contratos.TIPOS_ALTERACAO) == 3

    def test_chaves_tipos_sao_corretas(self):
        assert set(ia_contratos.TIPOS_ALTERACAO.keys()) == {
            "reajuste", "repactuacao", "reequilibrio"
        }

    def test_requisitos_cobre_todos_tipos(self):
        for tipo in ia_contratos.TIPOS_ALTERACAO:
            assert tipo in ia_contratos.REQUISITOS_POR_TIPO

    def test_reajuste_tem_ao_menos_3_requisitos(self):
        assert len(ia_contratos.REQUISITOS_POR_TIPO["reajuste"]) >= 3

    def test_repactuacao_tem_ao_menos_4_requisitos(self):
        assert len(ia_contratos.REQUISITOS_POR_TIPO["repactuacao"]) >= 4

    def test_reequilibrio_tem_ao_menos_4_requisitos(self):
        assert len(ia_contratos.REQUISITOS_POR_TIPO["reequilibrio"]) >= 4

    def test_status_requisito_contem_atendido_parcial_ausente(self):
        assert set(ia_contratos.STATUS_REQUISITO.keys()) == {
            "ATENDIDO", "PARCIAL", "AUSENTE"
        }

    def test_parecer_options_tem_3_opcoes(self):
        assert len(ia_contratos.PARECER_OPTIONS) == 3

    def test_constantes_sao_mapping_proxy(self):
        assert isinstance(ia_contratos.TIPOS_ALTERACAO, types.MappingProxyType)
        assert isinstance(ia_contratos.REQUISITOS_POR_TIPO, types.MappingProxyType)
        assert isinstance(ia_contratos.STATUS_REQUISITO, types.MappingProxyType)
        assert isinstance(ia_contratos.PARECER_OPTIONS, types.MappingProxyType)
        assert isinstance(ia_contratos._SISTEMA_POR_TIPO, types.MappingProxyType)


def _dados_contrato_mock() -> dict:
    return {
        "numero_contrato": "001/2024",
        "objeto": "Prestação de serviços de limpeza",
        "data_assinatura": "15/01/2024",
        "valor_atual": 500000.0,
    }


def _parecer_api_mock() -> dict:
    return {
        "parecer": "DEFERÍVEL COM RESSALVAS",
        "tipo_alteracao": "reajuste",
        "requisitos": [
            {
                "descricao": "Cláusula de reajuste expressa",
                "status": "ATENDIDO",
                "observacao": "",
            },
            {
                "descricao": "Intervalo mínimo 12 meses",
                "status": "PARCIAL",
                "observacao": "Apenas 11 meses decorridos",
            },
        ],
        "lacunas_documentais": ["Planilha IPCA não anexada"],
        "fundamentos_legais": ["Art. 25 §8º, Lei 14.133/2021"],
        "recomendacoes": ["Aguardar completar 12 meses da data-base"],
        "sintese": "Pedido atende parcialmente os requisitos legais.",
    }


class TestAnalisar:
    def test_tipo_invalido_levanta_value_error(self):
        with pytest.raises(ValueError, match="Tipo de alteração inválido"):
            ia_contratos.analisar("inexistente", {}, None, "key")

    def test_retorna_dict_com_parecer_e_requisitos(self):
        with patch(
            "ia_utils.urllib.request.urlopen",
            return_value=_mock_urlopen(_parecer_api_mock()),
        ):
            r = ia_contratos.analisar(
                "reajuste", _dados_contrato_mock(), None, "key_teste"
            )
        assert "parecer" in r
        assert "requisitos" in r
        assert "sintese" in r

    def test_tipo_alteracao_sempre_local(self):
        api_result = {**_parecer_api_mock(), "tipo_alteracao": "repactuacao"}
        with patch(
            "ia_utils.urllib.request.urlopen",
            return_value=_mock_urlopen(api_result),
        ):
            r = ia_contratos.analisar(
                "reajuste", _dados_contrato_mock(), None, "key_teste"
            )
        assert r["tipo_alteracao"] == "reajuste"

    def test_dados_contrato_preservados_localmente(self):
        dados = _dados_contrato_mock()
        with patch(
            "ia_utils.urllib.request.urlopen",
            return_value=_mock_urlopen(_parecer_api_mock()),
        ):
            r = ia_contratos.analisar("reajuste", dados, None, "key_teste")
        assert r["dados_contrato"] == dados

    def test_sem_documentos_nao_levanta_erro(self):
        with patch(
            "ia_utils.urllib.request.urlopen",
            return_value=_mock_urlopen(_parecer_api_mock()),
        ):
            r = ia_contratos.analisar(
                "reequilibrio", _dados_contrato_mock(), None, "key_teste"
            )
        assert isinstance(r, dict)

    def test_http_error_levanta_runtime_error(self):
        http_err = urllib.error.HTTPError(
            url="https://api.anthropic.com/v1/messages",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=MagicMock(
                read=MagicMock(return_value=b'{"error":"invalid key"}')
            ),
        )
        with patch("ia_utils.urllib.request.urlopen", side_effect=http_err):
            with pytest.raises(RuntimeError, match="HTTP 401"):
                ia_contratos.analisar(
                    "reajuste", _dados_contrato_mock(), None, "key_invalida"
                )

    def test_url_error_levanta_runtime_error(self):
        url_err = urllib.error.URLError(reason="Connection refused")
        with patch("ia_utils.urllib.request.urlopen", side_effect=url_err):
            with pytest.raises(RuntimeError):
                ia_contratos.analisar(
                    "reajuste", _dados_contrato_mock(), None, "key_teste"
                )

    def test_api_retorna_nao_dict_levanta_runtime_error(self):
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen([1, 2, 3])):
            with pytest.raises(RuntimeError, match="objeto JSON esperado"):
                ia_contratos.analisar(
                    "reajuste", _dados_contrato_mock(), None, "key_teste"
                )

    def test_resposta_nao_json_levanta_runtime_error(self):
        payload = json.dumps(
            {"content": [{"text": "Desculpe, não posso ajudar com isso."}]}
        ).encode("utf-8")
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(
            return_value=MagicMock(read=MagicMock(return_value=payload))
        )
        mock_cm.__exit__ = MagicMock(return_value=False)
        with patch("ia_utils.urllib.request.urlopen", return_value=mock_cm):
            with pytest.raises(RuntimeError):
                ia_contratos.analisar(
                    "reajuste", _dados_contrato_mock(), None, "key_teste"
                )

    def test_analisar_com_texto_docs_inclui_documentos(self):
        with patch(
            "ia_utils.urllib.request.urlopen",
            return_value=_mock_urlopen(_parecer_api_mock()),
        ):
            r = ia_contratos.analisar(
                "reajuste", _dados_contrato_mock(), "Texto do requerimento de reajuste", "key_teste"
            )
        assert isinstance(r, dict)
        assert "parecer" in r

    def test_bytes_nao_json_no_envelope_levanta_runtime_error(self):
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(
            return_value=MagicMock(read=MagicMock(return_value=b"<html>Bad Gateway</html>"))
        )
        mock_cm.__exit__ = MagicMock(return_value=False)
        with patch("ia_utils.urllib.request.urlopen", return_value=mock_cm):
            with pytest.raises(RuntimeError, match="não é JSON válido"):
                ia_contratos.analisar(
                    "reajuste", _dados_contrato_mock(), None, "key_teste"
                )

    def test_parecer_desconhecido_vira_indeferivel_com_aviso(self):
        api_result = {**_parecer_api_mock(), "parecer": "DEFERÍVEL PARCIALMENTE"}
        with patch(
            "ia_utils.urllib.request.urlopen",
            return_value=_mock_urlopen(api_result),
        ):
            r = ia_contratos.analisar(
                "reajuste", _dados_contrato_mock(), "texto", "key_teste"
            )
        assert r["parecer"] == "INDEFERÍVEL"
        assert r.get("_aviso_parecer") == "DEFERÍVEL PARCIALMENTE"

    def test_parecer_reconhecido_nao_seta_aviso(self):
        with patch(
            "ia_utils.urllib.request.urlopen",
            return_value=_mock_urlopen(_parecer_api_mock()),
        ):
            r = ia_contratos.analisar(
                "reajuste", _dados_contrato_mock(), "texto", "key_teste"
            )
        assert r["parecer"] == "DEFERÍVEL COM RESSALVAS"
        assert "_aviso_parecer" not in r

    def test_parecer_none_vira_indeferivel_sem_aviso(self):
        api_result = {**_parecer_api_mock(), "parecer": None}
        with patch(
            "ia_utils.urllib.request.urlopen",
            return_value=_mock_urlopen(api_result),
        ):
            r = ia_contratos.analisar(
                "reajuste", _dados_contrato_mock(), None, "key_teste"
            )
        assert r["parecer"] == "INDEFERÍVEL"
        assert "_aviso_parecer" not in r

    def test_parecer_vazio_vira_indeferivel_com_aviso_vazio(self):
        api_result = {**_parecer_api_mock(), "parecer": ""}
        with patch(
            "ia_utils.urllib.request.urlopen",
            return_value=_mock_urlopen(api_result),
        ):
            r = ia_contratos.analisar(
                "reajuste", _dados_contrato_mock(), None, "key_teste"
            )
        assert r["parecer"] == "INDEFERÍVEL"
        assert r.get("_aviso_parecer") == ""
