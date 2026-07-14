from __future__ import annotations
import json
import pytest
from unittest.mock import patch, MagicMock

import ia_semantica
from tests.helpers import mock_urlopen



def _mock_urlopen_text(text: str):
    """Wrap a raw text string as Anthropic API response (simulates non-JSON body)."""
    data = json.dumps({"content": [{"text": text}]}).encode("utf-8")
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=data)))
    cm.__exit__ = MagicMock(return_value=False)
    return cm


_BASE_RAG = "base_juridica.json"
_TEXTO = "Edital de teste para licitação pública."

# At least one "semantica" rule is required so gerar_pareceres doesn't short-circuit at line 172.
_REGRAS = [
    {
        "tipo": "semantica",
        "id": "art-9-i",
        "item": "Vedação de cláusula restritiva",
        "o_que_checar": "Verificar se há cláusula que restrinja competição.",
        "base_legal": "Art. 9º, I, Lei 14.133/2021",
        "severidade": "alta",
    }
]

_ACHADO_VALIDO = {
    "id": "art-9-i",
    "item": "1.1",
    "categoria": "habilitacao",
    "status": "inconformidade",
    "severidade": "alta",
    "detalhe": "Cláusula restritiva identificada.",
    "trecho": "o licitante deve ter experiência prévia",
}


@pytest.fixture(autouse=True)
def mock_base_rag():
    """Prevent BaseRAG from opening base_juridica.json during tests."""
    rag_mock = MagicMock()
    rag_mock.buscar.return_value = []
    with patch("rag.BaseRAG", return_value=rag_mock):
        yield


class TestGeradorParecer:
    def test_resposta_valida_retorna_lista_achados(self):
        payload = {"achados": [_ACHADO_VALIDO]}
        with patch("ia_utils.urllib.request.urlopen", return_value=mock_urlopen(payload)):
            resultado = ia_semantica.gerar_pareceres(_TEXTO, _REGRAS, _BASE_RAG)
        assert isinstance(resultado, list)
        assert len(resultado) == 1
        assert resultado[0]["id"] == "art-9-i"

    def test_resposta_sem_achados_retorna_lista_vazia(self):
        payload = {"achados": []}
        with patch("ia_utils.urllib.request.urlopen", return_value=mock_urlopen(payload)):
            resultado = ia_semantica.gerar_pareceres(_TEXTO, _REGRAS, _BASE_RAG)
        assert resultado == []

    def test_api_retorna_lista_levanta_runtime_error(self):
        # extrair_json finds '{' inside [{}], so use a plain string-list to force a true list parse
        with patch("ia_utils.urllib.request.urlopen", return_value=mock_urlopen(["inconformidade", "alta"])):
            with pytest.raises(RuntimeError, match="objeto JSON esperado"):
                ia_semantica.gerar_pareceres(_TEXTO, _REGRAS, _BASE_RAG)

    def test_api_retorna_string_levanta_runtime_error(self):
        with patch("ia_utils.urllib.request.urlopen", return_value=mock_urlopen("erro")):
            with pytest.raises(RuntimeError, match="objeto JSON esperado"):
                ia_semantica.gerar_pareceres(_TEXTO, _REGRAS, _BASE_RAG)

    def test_api_retorna_json_invalido_levanta_runtime_error(self):
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen_text("não é json")):
            with pytest.raises(RuntimeError, match="JSON válido"):
                ia_semantica.gerar_pareceres(_TEXTO, _REGRAS, _BASE_RAG)
