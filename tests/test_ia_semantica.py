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
        # O achado do modelo vem acompanhado das verificacoes cruzadas fixas,
        # que saem SEMPRE (ver ia_semantica.VERIFICACOES_CRUZADAS).
        n_cruzadas = len(ia_semantica.VERIFICACOES_CRUZADAS)
        assert len(resultado) == 1 + n_cruzadas
        assert any(a["id"] == "art-9-i" for a in resultado)

    def test_resposta_sem_achados_devolve_so_as_verificacoes_cruzadas(self):
        """Modelo sem achados NAO significa edital aprovado: as verificacoes
        obrigatorias continuam saindo, marcadas como nao avaliadas."""
        payload = {"achados": []}
        with patch("ia_utils.urllib.request.urlopen", return_value=mock_urlopen(payload)):
            resultado = ia_semantica.gerar_pareceres(_TEXTO, _REGRAS, _BASE_RAG)
        ids = [a["id"] for a in resultado]
        assert ids == [c["id"] for c in ia_semantica.VERIFICACOES_CRUZADAS]
        assert all(a["status"] == "revisar" for a in resultado)
        assert all("nao foi respondida" in a["detalhe"] for a in resultado)

    def test_verificacao_cruzada_tem_titulo_normalizado(self):
        """Se o modelo reescrever o titulo, prevalece o texto oficial — e o que
        garante que dois relatorios do mesmo edital sejam comparaveis."""
        payload = {"achados": [{
            "id": "X01", "item": "Prazo de entrega batendo diferente",
            "categoria": "c", "severidade": "alta", "status": "inconformidade",
            "detalhe": "10 dias contra 10 dias uteis", "trecho": "",
        }]}
        with patch("ia_utils.urllib.request.urlopen", return_value=mock_urlopen(payload)):
            resultado = ia_semantica.gerar_pareceres(_TEXTO, _REGRAS, _BASE_RAG)
        x01 = next(a for a in resultado if a["id"] == "X01")
        oficial = next(c for c in ia_semantica.VERIFICACOES_CRUZADAS if c["id"] == "X01")
        assert x01["item"] == oficial["item"]              # titulo padronizado
        assert x01["detalhe"] == "10 dias contra 10 dias uteis"  # analise preservada
        assert x01["status"] == "inconformidade"

    def test_achados_livres_sao_limitados(self):
        payload = {"achados": [
            {"id": f"EXTRA-{i}", "item": f"livre {i}", "categoria": "c",
             "severidade": "baixa", "status": "revisar", "detalhe": "", "trecho": ""}
            for i in range(1, 9)
        ]}
        with patch("ia_utils.urllib.request.urlopen", return_value=mock_urlopen(payload)):
            resultado = ia_semantica.gerar_pareceres(_TEXTO, _REGRAS, _BASE_RAG)
        extras = [a for a in resultado if a["id"].startswith("EXTRA")]
        assert len(extras) == ia_semantica.MAX_ACHADOS_EXTRA

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
