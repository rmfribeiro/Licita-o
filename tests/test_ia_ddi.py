from __future__ import annotations
import io
import json as _json
import urllib.error
import pytest
from unittest.mock import patch, MagicMock
import ia_ddi


def _dados_base():
    return {
        "razao_social": "EMPRESA TESTE LTDA",
        "cnpj": "11222333000181",
        "situacao": "ATIVA",
        "ceis": [],
        "cnep": [],
        "pro_etica": False,
        "grande_vulto": False,
        "valor_contrato": 100_000.0,
    }


class TestAplicarPiso:
    def test_sem_ocorrencias_sem_risco(self):
        assert ia_ddi._aplicar_piso(_dados_base()) == "SEM RISCO IDENTIFICADO"

    def test_ceis_ativo_resulta_alto(self):
        dados = {**_dados_base(), "ceis": [{"situacaoAtual": "Ativo"}]}
        assert ia_ddi._aplicar_piso(dados) == "ALTO"

    def test_ceis_inativo_nao_eleva_risco(self):
        dados = {**_dados_base(), "ceis": [{"situacaoAtual": "Inativo"}]}
        assert ia_ddi._aplicar_piso(dados) == "SEM RISCO IDENTIFICADO"

    def test_cnep_ativo_resulta_medio(self):
        dados = {**_dados_base(), "cnep": [{"situacaoAtual": "Ativo"}]}
        assert ia_ddi._aplicar_piso(dados) == "MÉDIO"

    def test_situacao_suspensa_resulta_medio(self):
        dados = {**_dados_base(), "situacao": "SUSPENSA"}
        assert ia_ddi._aplicar_piso(dados) == "MÉDIO"

    def test_situacao_baixada_resulta_medio(self):
        dados = {**_dados_base(), "situacao": "BAIXADA"}
        assert ia_ddi._aplicar_piso(dados) == "MÉDIO"

    def test_ceis_prevalece_sobre_cnep(self):
        dados = {
            **_dados_base(),
            "ceis": [{"situacaoAtual": "Ativo"}],
            "cnep": [{"situacaoAtual": "Ativo"}],
        }
        assert ia_ddi._aplicar_piso(dados) == "ALTO"

    def test_grande_vulto_sem_pi_resulta_medio(self):
        dados = {**_dados_base(), "grande_vulto": True, "pro_etica": False}
        fid = {"q1": "Não", "q2": "Não", "q3": "Não", "q4": "Não", "q5": "Não"}
        assert ia_ddi._aplicar_piso(dados, fid) == "MÉDIO"

    def test_grande_vulto_com_pro_etica_nao_eleva(self):
        dados = {**_dados_base(), "grande_vulto": True, "pro_etica": True}
        fid = {"q1": "Sim", "q2": "Sim", "q3": "Sim", "q4": "Sim", "q5": "Sim"}
        assert ia_ddi._aplicar_piso(dados, fid) == "SEM RISCO IDENTIFICADO"

    def test_grande_vulto_com_fid_positivo_nao_eleva(self):
        dados = {**_dados_base(), "grande_vulto": True, "pro_etica": False}
        fid = {"q1": "Sim", "q2": "Sim", "q3": "Sim", "q4": "Não", "q5": "Não"}
        assert ia_ddi._aplicar_piso(dados, fid) == "SEM RISCO IDENTIFICADO"

    def test_grande_vulto_none_nao_aciona_piso_pi(self):
        dados = {**_dados_base(), "grande_vulto": None}
        fid = {"q1": "Não", "q2": "Não", "q3": "Não", "q4": "Não", "q5": "Não"}
        assert ia_ddi._aplicar_piso(dados, fid) == "SEM RISCO IDENTIFICADO"

    def test_grande_vulto_true_fid_none_resulta_medio(self):
        dados = {**_dados_base(), "grande_vulto": True, "pro_etica": False}
        assert ia_ddi._aplicar_piso(dados) == "MÉDIO"




def _parecer_ia_mock():
    return {
        "risco_geral": "BAIXO",
        "dimensoes": {
            "situacao_cadastral": {"status": "ok", "descricao": "Empresa ativa."},
            "sancoes": {"status": "ok", "achados": []},
            "programa_integridade": {
                "status": "alerta", "obrigatorio": False,
                "pro_etica": False, "descricao": "Sem PI declarado.",
            },
            "fid": {"status": "ok", "inconsistencias": [], "descricao": "Consistente."},
            "contexto_contrato": {
                "status": "ok", "grande_vulto": False,
                "descricao": "Abaixo do limite.",
            },
        },
        "resumo": "Empresa sem ocorrências graves.",
        "recomendacao": "Contratação pode prosseguir.",
        "base_legal": ["Portaria SEGES/ME 8.678/2021, art. 2º, III"],
        "validade_fid": "12 meses a partir da data desta consulta",
    }


class TestAnalisar:
    @patch('ia_utils.urllib.request.urlopen')
    def test_grande_vulto_none_nao_quebra_analisar(self, mock_urlopen):
        resposta = _json.dumps({
            "content": [{"text": _json.dumps(_parecer_ia_mock())}]
        }).encode("utf-8")
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=resposta)))
        mock_cm.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_cm

        dados = {**_dados_base(), "grande_vulto": None}
        fid = {"q1": "Sim", "q2": "Sim", "q3": "Não", "q4": "Não sei", "q5": "Não"}
        resultado = ia_ddi.analisar(dados, fid)

        assert "risco_geral" in resultado
        assert "dimensoes" in resultado

    @patch('ia_utils.urllib.request.urlopen')
    def test_retorna_estrutura_correta(self, mock_urlopen):
        resposta = _json.dumps({
            "content": [{"text": _json.dumps(_parecer_ia_mock())}]
        }).encode("utf-8")
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=resposta)))
        mock_cm.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_cm

        fid = {"q1": "Sim", "q2": "Sim", "q3": "Não", "q4": "Não sei", "q5": "Não"}
        resultado = ia_ddi.analisar(_dados_base(), fid)

        assert "risco_geral" in resultado
        assert "dimensoes" in resultado
        assert "resumo" in resultado
        assert "recomendacao" in resultado
        assert "base_legal" in resultado
        assert "validade_fid" in resultado

    @patch('ia_utils.urllib.request.urlopen')
    def test_piso_prevalece_sobre_ia(self, mock_urlopen):
        parecer_baixo = _parecer_ia_mock()
        parecer_baixo["risco_geral"] = "BAIXO"
        resposta = _json.dumps({
            "content": [{"text": _json.dumps(parecer_baixo)}]
        }).encode("utf-8")
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=resposta)))
        mock_cm.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_cm

        dados = {**_dados_base(), "ceis": [{"situacaoAtual": "Ativo"}]}
        fid = {"q1": "Sim", "q2": "Sim", "q3": "Sim", "q4": "Sim", "q5": "Sim"}

        resultado = ia_ddi.analisar(dados, fid)

        assert resultado["risco_geral"] == "ALTO"

    @patch('ia_ddi._get_api_key', return_value=None)
    def test_sem_api_key_levanta_runtime_error(self, mock_key):
        fid = {"q1": "Sim", "q2": "Não", "q3": "Não", "q4": "Não", "q5": "Não"}

        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            ia_ddi.analisar(_dados_base(), fid)

    @patch('ia_utils.urllib.request.urlopen')
    @patch('ia_ddi._get_api_key', return_value="sk-test")
    def test_alias_sem_risco_normalizado(self, mock_key, mock_urlopen):
        parecer = {**_parecer_ia_mock(), "risco_geral": "SEM RISCO"}
        resposta = _json.dumps({"content": [{"text": _json.dumps(parecer)}]}).encode("utf-8")
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=resposta)))
        mock_cm.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_cm
        resultado = ia_ddi.analisar(_dados_base(), {})
        assert resultado["risco_geral"] == "SEM RISCO IDENTIFICADO"

    @patch('ia_utils.urllib.request.urlopen')
    @patch('ia_ddi._get_api_key', return_value="sk-test")
    def test_httperror_inclui_body_na_mensagem(self, mock_key, mock_urlopen):
        fp = io.BytesIO(b'{"error": "invalid_api_key"}')
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "https://api.anthropic.com/v1/messages", 401, "Unauthorized", {}, fp
        )
        fid = {"q1": "Sim", "q2": "Não", "q3": "Não", "q4": "Não", "q5": "Não"}
        with pytest.raises(RuntimeError) as exc_info:
            ia_ddi.analisar(_dados_base(), fid)
        assert "401" in str(exc_info.value)
        assert "invalid_api_key" in str(exc_info.value)
