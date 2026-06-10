from __future__ import annotations
import json
import urllib.error
import pytest
from unittest.mock import patch, MagicMock
import ia_sancoes


def _dados_formulario_mock() -> dict:
    return {
        "cnpj":             "12345678000195",
        "numero_contrato":  "042/2024",
        "valor_contrato":   200000.0,
        "reincidencia":     "Não",
        "autoridade":       "Secretário Municipal de Obras",
        "orgao":            "Prefeitura de São Paulo",
    }


def _parecer_api_mock() -> dict:
    return {
        "fatos_apurados": "Empresa deixou de entregar equipamentos no prazo contratado.",
        "condutas_identificadas": ["inexecução parcial do contrato", "atraso injustificado"],
        "enquadramento": {
            "tipo_sancao":   "multa",
            "artigo":        "Art. 156, II, Lei 14.133/2021",
            "justificativa": "Atraso superior a 30 dias sem justificativa.",
        },
        "dosimetria": {
            "percentual_multa":    5.0,
            "valor_multa_estimado": 10000.0,
            "prazo_sancao":        None,
            "nivel_gravidade":     "MÉDIO",
            "agravantes":          [],
            "atenuantes":          ["primeira ocorrência"],
        },
        "alerta_criminal": {
            "configura_crime":  False,
            "artigo_178":       None,
            "descricao_conduta": None,
            "recomendacao":     None,
        },
        "base_legal": ["Art. 156, II, Lei 14.133/2021", "Art. 158, Lei 14.133/2021"],
    }


def _minuta_api_mock() -> dict:
    return {"minuta": "PORTARIA Nº 001/2024\n\nCONSIDERANDO os fatos apurados..."}


def _mock_urlopen(payload: dict):
    data = json.dumps(
        {"content": [{"text": json.dumps(payload)}]}
    ).encode("utf-8")
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(
        return_value=MagicMock(read=MagicMock(return_value=data))
    )
    mock_cm.__exit__ = MagicMock(return_value=False)
    return mock_cm


class TestConstantes:
    def test_tipos_sancao_tem_4_valores(self):
        assert len(ia_sancoes.TIPOS_SANCAO) == 4

    def test_tipos_sancao_contem_esperados(self):
        assert ia_sancoes.TIPOS_SANCAO == {
            "advertencia", "multa", "impedimento", "inidoneidade"
        }

    def test_niveis_gravidade_contem_esperados(self):
        assert ia_sancoes.NIVEIS_GRAVIDADE == {"LEVE", "MÉDIO", "GRAVE"}

    def test_label_sancao_cobre_todos_tipos(self):
        for tipo in ia_sancoes.TIPOS_SANCAO:
            assert tipo in ia_sancoes.LABEL_SANCAO

    def test_reincidencia_opcoes_tem_3_valores(self):
        assert len(ia_sancoes.REINCIDENCIA_OPCOES) == 3


class TestNormalizacao:
    def test_tipo_sancao_invalido_normaliza_para_multa(self):
        parecer = {**_parecer_api_mock()}
        parecer["enquadramento"] = {**parecer["enquadramento"], "tipo_sancao": "inexistente"}
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(parecer)):
            r = ia_sancoes.analisar_dosimetria(_dados_formulario_mock(), None, "key")
        assert r["enquadramento"]["tipo_sancao"] == "multa"

    def test_tipo_sancao_case_insensitive(self):
        parecer = {**_parecer_api_mock()}
        parecer["enquadramento"] = {**parecer["enquadramento"], "tipo_sancao": "MULTA"}
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(parecer)):
            r = ia_sancoes.analisar_dosimetria(_dados_formulario_mock(), None, "key")
        assert r["enquadramento"]["tipo_sancao"] == "multa"

    def test_percentual_multa_clampado_minimo(self):
        parecer = {**_parecer_api_mock()}
        parecer["dosimetria"] = {**parecer["dosimetria"], "percentual_multa": 0.1}
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(parecer)):
            r = ia_sancoes.analisar_dosimetria(_dados_formulario_mock(), None, "key")
        assert r["dosimetria"]["percentual_multa"] == 0.5

    def test_percentual_multa_clampado_maximo(self):
        parecer = {**_parecer_api_mock()}
        parecer["dosimetria"] = {**parecer["dosimetria"], "percentual_multa": 99.9}
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(parecer)):
            r = ia_sancoes.analisar_dosimetria(_dados_formulario_mock(), None, "key")
        assert r["dosimetria"]["percentual_multa"] == 30.0

    def test_percentual_multa_dentro_do_range_preservado(self):
        parecer = {**_parecer_api_mock()}
        parecer["dosimetria"] = {**parecer["dosimetria"], "percentual_multa": 10.0}
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(parecer)):
            r = ia_sancoes.analisar_dosimetria(_dados_formulario_mock(), None, "key")
        assert r["dosimetria"]["percentual_multa"] == 10.0

    def test_configura_crime_sempre_bool_false(self):
        parecer = {**_parecer_api_mock()}
        parecer["alerta_criminal"] = {**parecer["alerta_criminal"], "configura_crime": 0}
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(parecer)):
            r = ia_sancoes.analisar_dosimetria(_dados_formulario_mock(), None, "key")
        assert isinstance(r["alerta_criminal"]["configura_crime"], bool)
        assert r["alerta_criminal"]["configura_crime"] is False

    def test_configura_crime_sempre_bool_true(self):
        parecer = {**_parecer_api_mock()}
        parecer["alerta_criminal"] = {**parecer["alerta_criminal"], "configura_crime": 1}
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(parecer)):
            r = ia_sancoes.analisar_dosimetria(_dados_formulario_mock(), None, "key")
        assert isinstance(r["alerta_criminal"]["configura_crime"], bool)
        assert r["alerta_criminal"]["configura_crime"] is True

    def test_nivel_gravidade_invalido_normaliza_para_medio(self):
        parecer = {**_parecer_api_mock()}
        parecer["dosimetria"] = {**parecer["dosimetria"], "nivel_gravidade": "ALTISSIMO"}
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(parecer)):
            r = ia_sancoes.analisar_dosimetria(_dados_formulario_mock(), None, "key")
        assert r["dosimetria"]["nivel_gravidade"] == "MÉDIO"

    def test_valor_contrato_zero_zera_estimativa_multa(self):
        parecer = {**_parecer_api_mock()}
        dados = {**_dados_formulario_mock(), "valor_contrato": 0.0}
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(parecer)):
            r = ia_sancoes.analisar_dosimetria(dados, None, "key")
        assert r["dosimetria"]["valor_multa_estimado"] == 0.0

    def test_valor_contrato_ausente_zera_estimativa_multa(self):
        dados = {k: v for k, v in _dados_formulario_mock().items() if k != "valor_contrato"}
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(_parecer_api_mock())):
            r = ia_sancoes.analisar_dosimetria(dados, None, "key")
        assert r["dosimetria"]["valor_multa_estimado"] == 0.0

    def test_valor_contrato_ausente_prompt_contem_nao_informado(self):
        dados = {k: v for k, v in _dados_formulario_mock().items() if k != "valor_contrato"}
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(_parecer_api_mock())) as mock_open:
            ia_sancoes.analisar_dosimetria(dados, None, "key")
        corpo = json.loads(mock_open.call_args.args[0].data.decode("utf-8"))
        assert "não informado" in corpo["messages"][0]["content"]

    def test_tipo_nao_multa_remove_valor_multa_estimado(self):
        parecer = {**_parecer_api_mock()}
        parecer["enquadramento"] = {**parecer["enquadramento"], "tipo_sancao": "advertencia"}
        parecer["dosimetria"] = {**parecer["dosimetria"], "valor_multa_estimado": 99999.0}
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(parecer)):
            r = ia_sancoes.analisar_dosimetria(_dados_formulario_mock(), None, "key")
        assert "valor_multa_estimado" not in r["dosimetria"]


class TestAnalisarDosimetria:
    def test_retorna_dict_com_chaves_obrigatorias(self):
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(_parecer_api_mock())):
            r = ia_sancoes.analisar_dosimetria(_dados_formulario_mock(), None, "key")
        assert "fatos_apurados" in r
        assert "enquadramento" in r
        assert "dosimetria" in r
        assert "alerta_criminal" in r
        assert "base_legal" in r

    def test_sem_documento_nao_levanta_erro(self):
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(_parecer_api_mock())):
            r = ia_sancoes.analisar_dosimetria(_dados_formulario_mock(), None, "key")
        assert isinstance(r, dict)

    def test_com_texto_docs_nao_levanta_erro(self):
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(_parecer_api_mock())):
            r = ia_sancoes.analisar_dosimetria(
                _dados_formulario_mock(), "Relatório de fiscalização...", "key"
            )
        assert isinstance(r, dict)

    def test_http_error_levanta_runtime_error(self):
        http_err = urllib.error.HTTPError(
            url="https://api.anthropic.com/v1/messages",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=MagicMock(read=MagicMock(return_value=b'{"error":"invalid key"}')),
        )
        with patch("urllib.request.urlopen", side_effect=http_err):
            with pytest.raises(RuntimeError, match="HTTP 401"):
                ia_sancoes.analisar_dosimetria(_dados_formulario_mock(), None, "key_invalida")

    def test_url_error_levanta_runtime_error(self):
        url_err = urllib.error.URLError(reason="Connection refused")
        with patch("urllib.request.urlopen", side_effect=url_err):
            with pytest.raises(RuntimeError):
                ia_sancoes.analisar_dosimetria(_dados_formulario_mock(), None, "key")

    def test_api_retorna_nao_dict_levanta_runtime_error(self):
        payload = json.dumps({"content": [{"text": "[1, 2, 3]"}]}).encode("utf-8")
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(
            return_value=MagicMock(read=MagicMock(return_value=payload))
        )
        mock_cm.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_cm):
            with pytest.raises(RuntimeError, match="objeto JSON esperado"):
                ia_sancoes.analisar_dosimetria(_dados_formulario_mock(), None, "key")


class TestGerarMinuta:
    def test_retorna_string(self):
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(_minuta_api_mock())):
            r = ia_sancoes.gerar_minuta(_parecer_api_mock(), _dados_formulario_mock(), "key")
        assert isinstance(r, str)
        assert len(r) > 0

    def test_api_sem_minuta_retorna_string_vazia(self):
        with patch("urllib.request.urlopen", return_value=_mock_urlopen({"minuta": ""})):
            r = ia_sancoes.gerar_minuta(_parecer_api_mock(), _dados_formulario_mock(), "key")
        assert r == ""

    def test_http_error_levanta_runtime_error(self):
        http_err = urllib.error.HTTPError(
            url="https://api.anthropic.com/v1/messages",
            code=500,
            msg="Internal Server Error",
            hdrs=None,
            fp=MagicMock(read=MagicMock(return_value=b"")),
        )
        with patch("urllib.request.urlopen", side_effect=http_err):
            with pytest.raises(RuntimeError, match="HTTP 500"):
                ia_sancoes.gerar_minuta(_parecer_api_mock(), _dados_formulario_mock(), "key")
