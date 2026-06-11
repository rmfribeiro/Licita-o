from __future__ import annotations
import json
import urllib.error
import pytest
from unittest.mock import patch, MagicMock
import ia_fid


def _dados_licitante_mock() -> dict:
    return {
        "cnpj":          "12345678000195",
        "razao_social":  "Empresa XPTO Ltda",
        "numero_edital": "PE 042/2024",
        "objeto":        "Contratação de serviços de TI",
        "orgao":         "Ministério da Educação",
    }


def _parecer_api_mock() -> dict:
    return {
        "necessita_diligencia": "SIM",
        "documentos_solicitados": [
            {
                "documento": "Certidão de regularidade com o FGTS",
                "situacao": "vencida",
                "fundamento_legal": "Art. 62, III, Lei 14.133/2021",
                "prazo_dias": 5,
            }
        ],
        "pontos_de_atencao": ["Certidão FGTS vencida há 15 dias."],
        "minuta_oficio": (
            "OFÍCIO DE DILIGÊNCIA Nº ___\n\n"
            "Assunto: Complementação documental.\n\n"
            "Senhor(a) Representante,\n\nSolicitamos a complementação dos documentos indicados."
        ),
        "prazo_resposta_sugerido": 5,
        "conclusao": "Necessária a complementação da documentação de habilitação.",
        "base_legal": [
            "Art. 59, §2º, Lei 14.133/2021",
            "Art. 64, I e II, Lei 14.133/2021",
        ],
    }


def _mock_urlopen(payload: dict):
    data = json.dumps({"content": [{"text": json.dumps(payload)}]}).encode("utf-8")
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=data)))
    mock_cm.__exit__ = MagicMock(return_value=False)
    return mock_cm


class TestConstantes:
    def test_fases_tem_3_opcoes(self):
        assert len(ia_fid.FASES_PROCESSO) == 3

    def test_fases_chaves_corretas(self):
        assert set(ia_fid.FASES_PROCESSO.keys()) == {
            "habilitacao", "proposta", "pos_adjudicacao"
        }

    def test_resultado_diligencia_tem_3_opcoes(self):
        assert len(ia_fid.RESULTADO_DILIGENCIA) == 3

    def test_resultado_diligencia_contem_sim_nao_parcialmente(self):
        assert "SIM" in ia_fid.RESULTADO_DILIGENCIA
        assert "NÃO" in ia_fid.RESULTADO_DILIGENCIA
        assert "PARCIALMENTE" in ia_fid.RESULTADO_DILIGENCIA

    def test_fases_sao_mapping_proxy(self):
        import types
        assert isinstance(ia_fid.FASES_PROCESSO, types.MappingProxyType)
        assert isinstance(ia_fid.RESULTADO_DILIGENCIA, types.MappingProxyType)


class TestAnalisar:
    def test_fase_invalida_levanta_value_error(self):
        with pytest.raises(ValueError, match="Fase inválida"):
            ia_fid.analisar("inexistente", {}, "situação", None, "key")

    def test_retorna_dict_com_chaves_obrigatorias(self):
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(_parecer_api_mock())):
            r = ia_fid.analisar(
                "habilitacao", _dados_licitante_mock(), "FGTS vencido", None, "key"
            )
        assert "necessita_diligencia" in r
        assert "documentos_solicitados" in r
        assert "minuta_oficio" in r
        assert "conclusao" in r
        assert "base_legal" in r

    def test_necessita_diligencia_sim(self):
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(_parecer_api_mock())):
            r = ia_fid.analisar(
                "habilitacao", _dados_licitante_mock(), "doc ausente", None, "key"
            )
        assert r["necessita_diligencia"] == "SIM"

    def test_resultado_nao_sem_acento_normalizado(self):
        parecer = {**_parecer_api_mock(), "necessita_diligencia": "NAO"}
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(parecer)):
            r = ia_fid.analisar(
                "proposta", _dados_licitante_mock(), "tudo ok", None, "key"
            )
        assert r["necessita_diligencia"] == "NÃO"

    def test_resultado_parcial_normalizado(self):
        parecer = {**_parecer_api_mock(), "necessita_diligencia": "PARCIAL"}
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(parecer)):
            r = ia_fid.analisar(
                "habilitacao", _dados_licitante_mock(), "dúvida", None, "key"
            )
        assert r["necessita_diligencia"] == "PARCIALMENTE"

    def test_resultado_desconhecido_cai_em_parcialmente(self):
        parecer = {**_parecer_api_mock(), "necessita_diligencia": "TALVEZ"}
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(parecer)):
            r = ia_fid.analisar(
                "habilitacao", _dados_licitante_mock(), "dúvida", None, "key"
            )
        assert r["necessita_diligencia"] == "PARCIALMENTE"

    def test_prazo_clampado_maximo_30(self):
        parecer = {**_parecer_api_mock(), "prazo_resposta_sugerido": 999}
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(parecer)):
            r = ia_fid.analisar(
                "habilitacao", _dados_licitante_mock(), "teste", None, "key"
            )
        assert r["prazo_resposta_sugerido"] == 30

    def test_prazo_clampado_minimo_1(self):
        parecer = {**_parecer_api_mock(), "prazo_resposta_sugerido": 0}
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(parecer)):
            r = ia_fid.analisar(
                "habilitacao", _dados_licitante_mock(), "teste", None, "key"
            )
        assert r["prazo_resposta_sugerido"] == 1

    def test_prazo_nao_numerico_cai_em_5(self):
        parecer = {**_parecer_api_mock(), "prazo_resposta_sugerido": "não informado"}
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(parecer)):
            r = ia_fid.analisar(
                "habilitacao", _dados_licitante_mock(), "teste", None, "key"
            )
        assert r["prazo_resposta_sugerido"] == 5

    def test_prazo_none_cai_em_5(self):
        parecer = {**_parecer_api_mock(), "prazo_resposta_sugerido": None}
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(parecer)):
            r = ia_fid.analisar(
                "habilitacao", _dados_licitante_mock(), "teste", None, "key"
            )
        assert r["prazo_resposta_sugerido"] == 5

    def test_sem_documentos_nao_levanta_erro(self):
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(_parecer_api_mock())):
            r = ia_fid.analisar(
                "pos_adjudicacao", _dados_licitante_mock(), "pendência", None, "key"
            )
        assert isinstance(r, dict)

    def test_com_texto_docs_nao_levanta_erro(self):
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(_parecer_api_mock())):
            r = ia_fid.analisar(
                "habilitacao", _dados_licitante_mock(), "FGTS vencido",
                "Texto do documento de habilitação...", "key",
            )
        assert isinstance(r, dict)

    def test_todas_as_fases_funcionam(self):
        for fase in ia_fid.FASES_PROCESSO:
            with patch(
                "ia_utils.urllib.request.urlopen",
                return_value=_mock_urlopen(_parecer_api_mock()),
            ):
                r = ia_fid.analisar(fase, _dados_licitante_mock(), "teste", None, "key")
            assert isinstance(r, dict)

    def test_http_error_levanta_runtime_error(self):
        http_err = urllib.error.HTTPError(
            url="https://api.anthropic.com/v1/messages",
            code=401, msg="Unauthorized", hdrs=None,
            fp=MagicMock(read=MagicMock(return_value=b'{"error":"invalid key"}')),
        )
        with patch("ia_utils.urllib.request.urlopen", side_effect=http_err):
            with pytest.raises(RuntimeError, match="HTTP 401"):
                ia_fid.analisar(
                    "habilitacao", _dados_licitante_mock(), "teste", None, "key_invalida"
                )

    def test_url_error_levanta_runtime_error(self):
        url_err = urllib.error.URLError(reason="Connection refused")
        with patch("ia_utils.urllib.request.urlopen", side_effect=url_err):
            with pytest.raises(RuntimeError):
                ia_fid.analisar(
                    "habilitacao", _dados_licitante_mock(), "teste", None, "key"
                )

    def test_api_retorna_nao_dict_levanta_runtime_error(self):
        payload = json.dumps({"content": [{"text": "[1, 2, 3]"}]}).encode("utf-8")
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=payload)))
        mock_cm.__exit__ = MagicMock(return_value=False)
        with patch("ia_utils.urllib.request.urlopen", return_value=mock_cm):
            with pytest.raises(RuntimeError, match="objeto JSON esperado"):
                ia_fid.analisar(
                    "habilitacao", _dados_licitante_mock(), "teste", None, "key"
                )
