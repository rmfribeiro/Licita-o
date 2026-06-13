from __future__ import annotations
import io
import json
import pytest
import urllib.error
from unittest.mock import patch, MagicMock
import ia_tr
from .helpers import mock_urlopen as _mock_urlopen


def _parecer_servico() -> dict:
    return {
        "adequacao_geral": "ADEQUADO COM RESSALVAS",
        "dimensoes": {
            "descricao_objeto":          {"status": "ok",     "descricao": "Objeto bem descrito."},
            "fundamentacao":             {"status": "ok",     "descricao": "Necessidade justificada."},
            "requisitos_tecnicos":       {"status": "alerta", "descricao": "Incompleto."},
            "modelo_execucao":           {"status": "ok",     "descricao": "Definido."},
            "modelo_gestao":             {"status": "ok",     "descricao": "Fiscalização prevista."},
            "criterio_medicao":          {"status": "ok",     "descricao": "Unidade definida."},
            "criterio_julgamento":       {"status": "ok",     "descricao": "Menor preço."},
            "estimativa_preco":          {"status": "alerta", "descricao": "Fontes insuficientes."},
            "qualificacao_habilitacao":  {"status": "ok",     "descricao": "Proporcional."},
        },
        "pontos_criticos": ["Requisitos técnicos incompletos."],
        "recomendacoes": ["Detalhar especificações técnicas."],
        "base_legal": ["IN SEGES/MGI 81/2022", "Lei 14.133/2021, Art. 6º, XXIII"],
    }


def _parecer_bem() -> dict:
    return {
        "adequacao_geral": "ADEQUADO",
        "dimensoes": {
            "especificacao_tecnica":    {"status": "ok", "descricao": "Especificação completa."},
            "justificativa_quantidade": {"status": "ok", "descricao": "Histórico presente."},
            "qualificacao_tecnica":     {"status": "ok", "descricao": "INMETRO citado."},
            "garantia_assistencia":     {"status": "ok", "descricao": "Prazo definido."},
            "condicoes_entrega":        {"status": "ok", "descricao": "Local definido."},
            "criterio_julgamento":      {"status": "ok", "descricao": "Menor preço."},
            "estimativa_preco":         {"status": "ok", "descricao": "Pesquisa válida."},
            "sustentabilidade":         {"status": "ok", "descricao": "Critérios presentes."},
        },
        "pontos_criticos": [],
        "recomendacoes": [],
        "base_legal": ["IN SEGES/MGI 81/2022"],
    }


def _parecer_tic() -> dict:
    return {
        "adequacao_geral": "INADEQUADO",
        "dimensoes": {
            "alinhamento_pdtic":    {"status": "critico", "descricao": "PDTIC ausente."},
            "analise_viabilidade":  {"status": "critico", "descricao": "AVC ausente."},
            "solucao_ti":           {"status": "alerta",  "descricao": "Incompleta."},
            "criterios_aceite_ans": {"status": "ok",      "descricao": "ANS definidos."},
            "equipe_tecnica":       {"status": "ok",      "descricao": "INTECTI prevista."},
            "seguranca_lgpd":       {"status": "alerta",  "descricao": "LGPD incompleta."},
            "modelo_execucao":      {"status": "ok",      "descricao": "Metodologia ágil."},
            "transicao_contratual": {"status": "critico", "descricao": "Plano ausente."},
            "estimativa_preco":     {"status": "ok",      "descricao": "Benchmark presente."},
        },
        "pontos_criticos": ["PDTIC ausente.", "AVC não elaborada."],
        "recomendacoes": ["Elaborar PDTIC.", "Realizar AVC completa."],
        "base_legal": ["IN SGD/ME 21/2024", "IN SEGES/MGI 81/2022"],
    }


class TestAnalisarTr:
    @patch("ia_utils.urllib.request.urlopen")
    def test_retorna_estrutura_correta_servico(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen(_parecer_servico())
        resultado = ia_tr.analisar_tr("Texto do TR de serviço.", "servico", "sk-test")
        assert "adequacao_geral" in resultado
        assert "dimensoes" in resultado
        assert "pontos_criticos" in resultado
        assert "recomendacoes" in resultado
        assert "base_legal" in resultado
        assert set(resultado["dimensoes"].keys()) == {
            "descricao_objeto", "fundamentacao", "requisitos_tecnicos",
            "modelo_execucao", "modelo_gestao", "criterio_medicao",
            "criterio_julgamento", "estimativa_preco", "qualificacao_habilitacao",
        }

    @patch("ia_utils.urllib.request.urlopen")
    def test_retorna_estrutura_correta_bem(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen(_parecer_bem())
        resultado = ia_tr.analisar_tr("Texto do TR de bem.", "bem", "sk-test")
        assert "adequacao_geral" in resultado
        assert "dimensoes" in resultado
        assert "pontos_criticos" in resultado
        assert "recomendacoes" in resultado
        assert "base_legal" in resultado
        assert set(resultado["dimensoes"].keys()) == {
            "especificacao_tecnica", "justificativa_quantidade", "qualificacao_tecnica",
            "garantia_assistencia", "condicoes_entrega", "criterio_julgamento",
            "estimativa_preco", "sustentabilidade",
        }

    @patch("ia_utils.urllib.request.urlopen")
    def test_retorna_estrutura_correta_tic(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen(_parecer_tic())
        resultado = ia_tr.analisar_tr("Texto do TR de TIC.", "tic", "sk-test")
        assert "adequacao_geral" in resultado
        assert "dimensoes" in resultado
        assert "pontos_criticos" in resultado
        assert "recomendacoes" in resultado
        assert "base_legal" in resultado
        assert set(resultado["dimensoes"].keys()) == {
            "alinhamento_pdtic", "analise_viabilidade", "solucao_ti",
            "criterios_aceite_ans", "equipe_tecnica", "seguranca_lgpd",
            "modelo_execucao", "transicao_contratual", "estimativa_preco",
        }

    @patch("ia_utils.urllib.request.urlopen")
    def test_base_legal_vazia_recebe_fallback(self, mock_urlopen):
        parecer_sem_base = {**_parecer_servico(), "base_legal": []}
        mock_urlopen.return_value = _mock_urlopen(parecer_sem_base)
        resultado = ia_tr.analisar_tr("Texto", "servico", "sk-test")
        assert len(resultado["base_legal"]) > 0
        assert any("81/2022" in item for item in resultado["base_legal"])

    def test_tipo_invalido_levanta_value_error(self):
        with pytest.raises(ValueError, match="Tipo de objeto inválido"):
            ia_tr.analisar_tr("Texto", "invalido", "sk-test")

    @patch("ia_utils.urllib.request.urlopen")
    def test_adequacao_invalida_normalizada_para_inadequado(self, mock_urlopen):
        parecer = {**_parecer_servico(), "adequacao_geral": "PARCIALMENTE ADEQUADO"}
        mock_urlopen.return_value = _mock_urlopen(parecer)
        resultado = ia_tr.analisar_tr("Texto", "servico", "sk-test")
        assert resultado["adequacao_geral"] == "INADEQUADO"

    @patch("ia_utils.urllib.request.urlopen")
    def test_httperror_inclui_body_na_mensagem(self, mock_urlopen):
        fp = io.BytesIO(b'{"error": "invalid_api_key"}')
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "https://api.anthropic.com/v1/messages", 401, "Unauthorized", {}, fp
        )
        with pytest.raises(RuntimeError) as exc_info:
            ia_tr.analisar_tr("Texto", "servico", "sk-test")
        assert "401" in str(exc_info.value)
        assert "invalid_api_key" in str(exc_info.value)

    @patch("ia_utils.urllib.request.urlopen")
    def test_resposta_sem_json_levanta_runtime_error(self, mock_urlopen):
        resposta = json.dumps({"content": [{"text": "Não consigo analisar este documento."}]}).encode("utf-8")
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=resposta)))
        mock_cm.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_cm
        with pytest.raises(RuntimeError, match="JSON"):
            ia_tr.analisar_tr("Texto", "servico", "sk-test")

    @patch("ia_utils.urllib.request.urlopen")
    def test_content_null_nao_quebra(self, mock_urlopen):
        resposta = json.dumps({"content": None}).encode("utf-8")
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=resposta)))
        mock_cm.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_cm
        with pytest.raises(RuntimeError):
            ia_tr.analisar_tr("Texto", "servico", "sk-test")
