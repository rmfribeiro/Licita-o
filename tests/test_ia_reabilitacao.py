from __future__ import annotations
import json
import pytest
import urllib.error
from datetime import date
from unittest.mock import patch, MagicMock
import ia_reabilitacao


class TestConstantes:
    def test_tipos_sancao_tem_impedimento_e_inidoneidade(self):
        assert set(ia_reabilitacao.TIPOS_SANCAO.keys()) == {"impedimento", "inidoneidade"}

    def test_prazos_minimos_anos(self):
        assert ia_reabilitacao.PRAZOS_MINIMOS_ANOS["impedimento"] == 1
        assert ia_reabilitacao.PRAZOS_MINIMOS_ANOS["inidoneidade"] == 3

    def test_parecer_options_tem_3_opcoes(self):
        assert set(ia_reabilitacao.PARECER_OPTIONS.keys()) == {
            "ELEGÍVEL", "ELEGÍVEL COM RESSALVAS", "INELEGÍVEL"
        }

    def test_constantes_sao_mapping_proxy(self):
        import types
        assert isinstance(ia_reabilitacao.TIPOS_SANCAO, types.MappingProxyType)
        assert isinstance(ia_reabilitacao.PRAZOS_MINIMOS_ANOS, types.MappingProxyType)
        assert isinstance(ia_reabilitacao.PARECER_OPTIONS, types.MappingProxyType)
        assert isinstance(ia_reabilitacao.NORM_PARECER_REAB, types.MappingProxyType)

    def test_norm_parecer_reab_mapeia_para_canonico(self):
        assert ia_reabilitacao.NORM_PARECER_REAB["ELEGIVEL"] == "ELEGÍVEL"
        assert ia_reabilitacao.NORM_PARECER_REAB["ELEGIVEL COM RESSALVAS"] == "ELEGÍVEL COM RESSALVAS"
        assert ia_reabilitacao.NORM_PARECER_REAB["INELEGIVEL"] == "INELEGÍVEL"


class TestCalcularPrazo:
    def test_prazo_atendido_impedimento_2_anos(self):
        ref = date(2026, 6, 8)
        aplicacao = date(2024, 6, 8)  # 2 anos antes
        r = ia_reabilitacao.calcular_prazo("impedimento", aplicacao, data_referencia=ref)
        assert r["atendido"] is True
        assert r["anos_decorridos"] == 2
        assert r["prazo_minimo_anos"] == 1

    def test_prazo_nao_atendido_inidoneidade_1_ano(self):
        ref = date(2026, 6, 8)
        aplicacao = date(2025, 6, 8)  # 1 ano antes, mas precisa 3
        r = ia_reabilitacao.calcular_prazo("inidoneidade", aplicacao, data_referencia=ref)
        assert r["atendido"] is False
        assert r["prazo_minimo_anos"] == 3

    def test_exatamente_no_limite_atendido(self):
        ref = date(2026, 6, 8)
        aplicacao = date(2025, 6, 8)  # exatamente 1 ano antes
        r = ia_reabilitacao.calcular_prazo("impedimento", aplicacao, data_referencia=ref)
        assert r["atendido"] is True  # >= prazo mínimo

    def test_um_dia_antes_do_limite_nao_atendido(self):
        ref = date(2026, 6, 8)
        aplicacao = date(2025, 6, 9)  # 1 dia a mais que 1 ano
        r = ia_reabilitacao.calcular_prazo("impedimento", aplicacao, data_referencia=ref)
        assert r["atendido"] is False

    def test_tipo_invalido_levanta_value_error(self):
        with pytest.raises(ValueError, match="tipo_sancao inválido"):
            ia_reabilitacao.calcular_prazo("inexistente", date(2024, 1, 1))


def _dados_empresa_mock() -> dict:
    return {
        "razao_social": "EMPRESA TESTE LTDA",
        "cnpj": "11222333000181",
        "ceis": [],
        "cnep": [],
    }


def _dados_sancao_mock(tipo: str = "impedimento") -> dict:
    return {
        "tipo_sancao":            tipo,
        "data_aplicacao":         date(2024, 1, 1),
        "orgao":                  "Ministério da Gestão",
        "multa_aplicada":         True,
        "multa_valor":            5000.0,
        "multa_quitada":          True,
        "condicoes_ato_punitivo": "Implementar programa de compliance.",
    }


def _respostas_mock() -> dict:
    return {
        "reparacao":            "Sim (integral)",
        "reparacao_descricao":  "Ressarcimento comprovado via depósito.",
        "cond_ato_cumpridas":   "Sim",
        "analise_juridica":     "Realizada",
    }


def _parecer_api_mock() -> dict:
    return {
        "parecer": "ELEGÍVEL",
        "condicoes_avaliadas": [
            {"numero": "I",   "descricao": "Reparação do dano",   "status": "ATENDIDA", "observacao": ""},
            {"numero": "II",  "descricao": "Pagamento de multa",  "status": "ATENDIDA", "observacao": ""},
            {"numero": "III", "descricao": "Prazo mínimo",        "status": "ATENDIDA", "observacao": ""},
            {"numero": "IV",  "descricao": "Cond. ato punitivo",  "status": "ATENDIDA", "observacao": ""},
            {"numero": "V",   "descricao": "Análise jurídica",    "status": "ATENDIDA", "observacao": ""},
        ],
        "sintese":    "Todas as condições do Art. 163 estão atendidas.",
        "base_legal": ["Art. 163, Par. Único, Lei 14.133/2021"],
    }


def _mock_urlopen(payload: dict):
    data = json.dumps({"content": [{"text": json.dumps(payload)}]}).encode("utf-8")
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=data)))
    cm.__exit__ = MagicMock(return_value=False)
    return cm


class TestAnalisar:
    def test_tipo_invalido_levanta_value_error(self):
        with pytest.raises(ValueError, match="tipo_sancao inválido"):
            ia_reabilitacao.analisar(
                "inexistente", {}, {}, {}, None, "key"
            )

    def test_prazo_nao_decorrido_retorna_inelegivel_sem_chamar_api(self):
        dados_sancao = {
            **_dados_sancao_mock("inidoneidade"),
            "data_aplicacao": date(2025, 6, 8),  # apenas 1 ano atrás, precisa 3
        }
        with patch("urllib.request.urlopen") as mock_url:
            r = ia_reabilitacao.analisar(
                "inidoneidade", _dados_empresa_mock(), dados_sancao, _respostas_mock(), None, "key"
            )
        mock_url.assert_not_called()
        assert r["parecer"] == "INELEGÍVEL"

    def test_retorna_elegivel_com_api_mock(self):
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(_parecer_api_mock())):
            r = ia_reabilitacao.analisar(
                "impedimento",
                _dados_empresa_mock(),
                _dados_sancao_mock(),
                _respostas_mock(),
                None,
                "key",
            )
        assert r["parecer"] == "ELEGÍVEL"
        assert "dados_empresa" in r
        assert "dados_sancao" in r

    def test_alias_sem_acento_normalizado(self):
        payload = {**_parecer_api_mock(), "parecer": "ELEGIVEL"}
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(payload)):
            r = ia_reabilitacao.analisar(
                "impedimento", _dados_empresa_mock(), _dados_sancao_mock(), _respostas_mock(), None, "key"
            )
        assert r["parecer"] == "ELEGÍVEL"

    def test_json_malformado_levanta_runtime_error(self):
        data = json.dumps({"content": [{"text": "não é json"}]}).encode("utf-8")
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=data)))
        cm.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=cm):
            with pytest.raises(RuntimeError, match="JSON válido"):
                ia_reabilitacao.analisar(
                    "impedimento", _dados_empresa_mock(), _dados_sancao_mock(), _respostas_mock(), None, "key"
                )

    def test_api_retorna_nao_dict_levanta_runtime_error(self):
        payload = json.dumps({"content": [{"text": json.dumps([1, 2, 3])}]}).encode("utf-8")
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=payload)))
        cm.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=cm):
            with pytest.raises(RuntimeError, match="objeto JSON esperado"):
                ia_reabilitacao.analisar(
                    "impedimento", _dados_empresa_mock(), _dados_sancao_mock(), _respostas_mock(), None, "key"
                )

    def test_http_error_levanta_runtime_error(self):
        err = urllib.error.HTTPError(
            url="https://api.anthropic.com/v1/messages",
            code=401, msg="Unauthorized", hdrs=None,
            fp=MagicMock(read=MagicMock(return_value=b'{"error":"invalid"}')),
        )
        with patch("urllib.request.urlopen", side_effect=err):
            with pytest.raises(RuntimeError, match="HTTP 401"):
                ia_reabilitacao.analisar(
                    "impedimento", _dados_empresa_mock(), _dados_sancao_mock(), _respostas_mock(), None, "key"
                )

    def test_url_error_levanta_runtime_error(self):
        err = urllib.error.URLError("Connection refused")
        with patch("urllib.request.urlopen", side_effect=err):
            with pytest.raises(RuntimeError):
                ia_reabilitacao.analisar(
                    "impedimento", _dados_empresa_mock(), _dados_sancao_mock(), _respostas_mock(), None, "key"
                )
