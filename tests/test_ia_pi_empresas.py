from __future__ import annotations
import pytest
import ia_pi_empresas
import json
import urllib.error
from unittest.mock import patch, MagicMock


class TestNivelMaturidade:
    def test_score_0_retorna_inexistente(self):
        assert ia_pi_empresas.nivel_maturidade(0) == "INEXISTENTE"

    def test_score_24_retorna_inexistente(self):
        assert ia_pi_empresas.nivel_maturidade(24) == "INEXISTENTE"

    def test_score_25_retorna_inicial(self):
        assert ia_pi_empresas.nivel_maturidade(25) == "INICIAL"

    def test_score_49_retorna_inicial(self):
        assert ia_pi_empresas.nivel_maturidade(49) == "INICIAL"

    def test_score_50_retorna_em_desenvolvimento(self):
        assert ia_pi_empresas.nivel_maturidade(50) == "EM DESENVOLVIMENTO"

    def test_score_74_retorna_em_desenvolvimento(self):
        assert ia_pi_empresas.nivel_maturidade(74) == "EM DESENVOLVIMENTO"

    def test_score_75_retorna_consolidado(self):
        assert ia_pi_empresas.nivel_maturidade(75) == "CONSOLIDADO"

    def test_score_100_retorna_consolidado(self):
        assert ia_pi_empresas.nivel_maturidade(100) == "CONSOLIDADO"


def _respostas_todos_implementados() -> dict:
    return {p: "Implementado" for p in ia_pi_empresas.QUESTOES_PI}


def _respostas_todos_nao_existem() -> dict:
    return {p: "Não existe" for p in ia_pi_empresas.QUESTOES_PI}


def _respostas_todos_parcialmente() -> dict:
    return {p: "Parcialmente" for p in ia_pi_empresas.QUESTOES_PI}


class TestCalcularScores:
    def test_todos_implementados_score_geral_100(self):
        r = _respostas_todos_implementados()
        s = ia_pi_empresas.calcular_scores(r)
        assert s["geral"] == 100.0

    def test_todos_nao_existem_score_geral_0(self):
        r = _respostas_todos_nao_existem()
        s = ia_pi_empresas.calcular_scores(r)
        assert s["geral"] == 0.0

    def test_todos_parcialmente_score_geral_50(self):
        r = _respostas_todos_parcialmente()
        s = ia_pi_empresas.calcular_scores(r)
        assert s["geral"] == 50.0

    def test_retorna_por_parametro_com_17_chaves(self):
        r = _respostas_todos_implementados()
        s = ia_pi_empresas.calcular_scores(r)
        assert len(s["por_parametro"]) == 17

    def test_retorna_por_dimensao_com_5_chaves(self):
        r = _respostas_todos_implementados()
        s = ia_pi_empresas.calcular_scores(r)
        assert len(s["por_dimensao"]) == 5

    def test_nivel_derivado_do_score(self):
        r = _respostas_todos_implementados()
        s = ia_pi_empresas.calcular_scores(r)
        assert s["nivel"] == "CONSOLIDADO"

    def test_resposta_ausente_conta_como_nao_existe(self):
        r = {}  # nenhuma resposta
        s = ia_pi_empresas.calcular_scores(r)
        assert s["geral"] == 0.0

    def test_score_por_dimensao_media_simples_dos_parametros(self):
        # Comprometimento (p1, p2, p3): p1=100, p2=0, p3=0 → media=33.3
        r = _respostas_todos_nao_existem()
        r["p1"] = "Implementado"
        s = ia_pi_empresas.calcular_scores(r)
        assert abs(s["por_dimensao"]["comprometimento_alta_direcao"] - (100 / 3)) < 0.1

    def test_pesos_somam_1(self):
        total = sum(ia_pi_empresas.PESOS_DIMENSAO.values())
        assert abs(total - 1.0) < 1e-9

    def test_resposta_desconhecida_conta_como_zero(self):
        r = _respostas_todos_nao_existem()
        r["p1"] = "IMPLEMENTADO"  # wrong case — not in _VALORES_RESPOSTA
        s = ia_pi_empresas.calcular_scores(r)
        assert s["por_parametro"]["p1"] == 0


def _qualitativo_mock() -> dict:
    return {
        "dimensoes": {
            "comprometimento_alta_direcao": {
                "sintese": "Alta direção comprometida.",
                "parametros": {
                    "p1": {"achados": ["Política publicada."], "recomendacoes": []},
                    "p2": {"achados": [], "recomendacoes": ["Designar CCO."]},
                    "p3": {"achados": [], "recomendacoes": []},
                },
            },
            "analise_riscos": {
                "sintese": "Mapeamento básico existente.",
                "parametros": {
                    "p4": {"achados": [], "recomendacoes": []},
                    "p5": {"achados": [], "recomendacoes": []},
                },
            },
            "estrutura_controles": {
                "sintese": "Controles parcialmente implantados.",
                "parametros": {
                    "p6": {"achados": [], "recomendacoes": []},
                    "p7": {"achados": [], "recomendacoes": []},
                    "p8": {"achados": [], "recomendacoes": []},
                    "p9": {"achados": [], "recomendacoes": []},
                    "p10": {"achados": [], "recomendacoes": []},
                    "p11": {"achados": [], "recomendacoes": []},
                    "p12": {"achados": [], "recomendacoes": []},
                },
            },
            "monitoramento_melhoria": {
                "sintese": "Monitoramento inexistente.",
                "parametros": {
                    "p13": {"achados": [], "recomendacoes": []},
                    "p14": {"achados": [], "recomendacoes": []},
                    "p15": {"achados": [], "recomendacoes": []},
                },
            },
            "transparencia": {
                "sintese": "Transparência adequada.",
                "parametros": {
                    "p16": {"achados": [], "recomendacoes": []},
                    "p17": {"achados": [], "recomendacoes": []},
                },
            },
        },
        "pontos_criticos": ["Canal de denúncias sem garantia de anonimato."],
        "conclusao_hipotese": "Empresa apta para desempate por PI.",
        "recomendacoes": ["Formalizar orçamento do PI."],
        "base_legal": ["Decreto 12.304/2024, Art. 4º"],
    }


def _mock_urlopen(qualitativo: dict):
    payload = json.dumps(
        {"content": [{"text": json.dumps(qualitativo)}]}
    ).encode("utf-8")
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(
        return_value=MagicMock(read=MagicMock(return_value=payload))
    )
    mock_cm.__exit__ = MagicMock(return_value=False)
    return mock_cm


class TestAvaliar:
    def test_retorna_dict_com_scores_e_qualitativo(self):
        respostas = _respostas_todos_implementados()
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(_qualitativo_mock())):
            resultado = ia_pi_empresas.avaliar(respostas, "desempate", None, "key_teste")
        assert "scores" in resultado
        assert "dimensoes" in resultado
        assert "conclusao_hipotese" in resultado

    def test_scores_calculados_localmente(self):
        respostas = _respostas_todos_implementados()
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(_qualitativo_mock())):
            resultado = ia_pi_empresas.avaliar(respostas, "desempate", None, "key_teste")
        assert resultado["scores"]["geral"] == 100.0

    def test_hipotese_gravada_no_resultado(self):
        respostas = _respostas_todos_nao_existem()
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(_qualitativo_mock())):
            resultado = ia_pi_empresas.avaliar(respostas, "grande_vulto", None, "key_teste")
        assert resultado["hipotese"] == "grande_vulto"

    def test_http_error_levanta_runtime_error(self):
        respostas = _respostas_todos_implementados()
        http_err = urllib.error.HTTPError(
            url="https://api.anthropic.com/v1/messages",
            code=401, msg="Unauthorized", hdrs=None,
            fp=MagicMock(read=MagicMock(return_value=b'{"error":"invalid key"}')),
        )
        with patch("ia_utils.urllib.request.urlopen", side_effect=http_err):
            with pytest.raises(RuntimeError, match="HTTP 401"):
                ia_pi_empresas.avaliar(respostas, "desempate", None, "key_invalida")

    def test_api_retorna_nao_dict_levanta_runtime_error(self):
        respostas = _respostas_todos_implementados()
        payload = json.dumps({"content": [{"text": "[1, 2, 3]"}]}).encode("utf-8")
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(
            return_value=MagicMock(read=MagicMock(return_value=payload))
        )
        mock_cm.__exit__ = MagicMock(return_value=False)
        with patch("ia_utils.urllib.request.urlopen", return_value=mock_cm):
            with pytest.raises(RuntimeError, match="objeto JSON esperado"):
                ia_pi_empresas.avaliar(respostas, "desempate", None, "key_teste")

    def test_url_error_levanta_runtime_error(self):
        respostas = _respostas_todos_implementados()
        url_err = urllib.error.URLError(reason="Connection refused")
        with patch("ia_utils.urllib.request.urlopen", side_effect=url_err):
            with pytest.raises(RuntimeError):
                ia_pi_empresas.avaliar(respostas, "desempate", None, "key_teste")

    def test_resposta_nao_json_levanta_runtime_error(self):
        respostas = _respostas_todos_implementados()
        # extrair_json will fail on plain text response
        payload = json.dumps({"content": [{"text": "Desculpe, não posso ajudar."}]}).encode("utf-8")
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(
            return_value=MagicMock(read=MagicMock(return_value=payload))
        )
        mock_cm.__exit__ = MagicMock(return_value=False)
        with patch("ia_utils.urllib.request.urlopen", return_value=mock_cm):
            with pytest.raises(RuntimeError):
                ia_pi_empresas.avaliar(respostas, "desempate", None, "key_teste")


class TestTiposEHipoteses:
    def test_hipoteses_por_tipo_tem_tres_tipos(self):
        assert set(ia_pi_empresas.HIPOTESES_POR_TIPO.keys()) == {
            "empresa_privada", "administracao_publica", "osc"
        }

    def test_cada_tipo_tem_pelo_menos_tres_hipoteses(self):
        for tipo, hipoteses in ia_pi_empresas.HIPOTESES_POR_TIPO.items():
            assert len(hipoteses) >= 3, f"{tipo} tem menos de 3 hipóteses"

    def test_tipos_entidade_tem_tres_chaves(self):
        assert set(ia_pi_empresas.TIPOS_ENTIDADE.keys()) == {
            "empresa_privada", "administracao_publica", "osc"
        }


class TestAvaliarTipoEntidade:
    def test_tipo_administracao_publica_usa_sistema_correto(self):
        respostas = {p: "Implementado" for p in ia_pi_empresas.QUESTOES_PI}
        qualitativo = _qualitativo_mock()
        with patch(
            "ia_pi_empresas._chamar_anthropic",
            return_value=json.dumps(qualitativo),
        ) as mock_call:
            ia_pi_empresas.avaliar(
                respostas, "grande_vulto", None, "key",
                tipo_entidade="administracao_publica",
            )
        sistema = mock_call.call_args[0][3]
        assert "Administração Pública" in sistema

    def test_tipo_osc_usa_sistema_correto(self):
        respostas = {p: "Implementado" for p in ia_pi_empresas.QUESTOES_PI}
        qualitativo = _qualitativo_mock()
        with patch(
            "ia_pi_empresas._chamar_anthropic",
            return_value=json.dumps(qualitativo),
        ) as mock_call:
            ia_pi_empresas.avaliar(
                respostas, "termo_fomento", None, "key",
                tipo_entidade="osc",
            )
        sistema = mock_call.call_args[0][3]
        assert "OSC" in sistema

    def test_tipo_entidade_gravado_no_resultado(self):
        respostas = {p: "Implementado" for p in ia_pi_empresas.QUESTOES_PI}
        with patch(
            "ia_utils.urllib.request.urlopen",
            return_value=_mock_urlopen(_qualitativo_mock()),
        ):
            resultado = ia_pi_empresas.avaliar(
                respostas, "grande_vulto", None, "key",
                tipo_entidade="administracao_publica",
            )
        assert resultado["tipo_entidade"] == "administracao_publica"

    def test_tipo_desconhecido_levanta_runtime_error(self):
        respostas = {p: "Não existe" for p in ia_pi_empresas.QUESTOES_PI}
        with pytest.raises(RuntimeError, match="tipo_entidade desconhecido"):
            ia_pi_empresas.avaliar(
                respostas, "grande_vulto", None, "key",
                tipo_entidade="tipo_invalido",
            )
