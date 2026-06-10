from __future__ import annotations
import json
import pytest
import urllib.error
from unittest.mock import patch, MagicMock
import ia_pesquisa_mercado


class TestConstantes:
    def test_status_item_tem_chaves_esperadas(self):
        assert set(ia_pesquisa_mercado.STATUS_ITEM.keys()) == {
            "VALIDO", "INSUFICIENTE"
        }

    def test_status_pesquisa_tem_chaves_esperadas(self):
        assert set(ia_pesquisa_mercado.STATUS_PESQUISA.keys()) == {
            "VÁLIDA", "COM RESSALVAS", "INVÁLIDA"
        }

    def test_min_cotacoes_validas_e_3(self):
        assert ia_pesquisa_mercado.MIN_COTACOES_VALIDAS == 3

    def test_desvio_max_percentual_e_50_porcento(self):
        assert ia_pesquisa_mercado.DESVIO_MAX_PERCENTUAL == 0.50

    def test_constantes_sao_mapping_proxy(self):
        import types
        assert isinstance(ia_pesquisa_mercado.STATUS_ITEM, types.MappingProxyType)
        assert isinstance(ia_pesquisa_mercado.STATUS_PESQUISA, types.MappingProxyType)


class TestCalcularReferencia:
    def test_tres_cotacoes_validas_retorna_mediana_correta(self):
        # [120, 130, 135]: mediana=130
        r = ia_pesquisa_mercado.calcular_referencia([120.0, 130.0, 135.0])
        assert r["status"] == "VALIDO"
        assert r["preco_referencia"] == 130.0
        assert len(r["cotacoes_validas"]) == 3
        assert r["cotacoes_excluidas"] == []

    def test_cotacao_acima_desvio_excluida_tres_validas_restam(self):
        # [120, 130, 140, 310]: mediana_prov=135, limite=202.5, 310 excluída
        # validas=[120,130,140], mediana_final=130
        r = ia_pesquisa_mercado.calcular_referencia([120.0, 130.0, 140.0, 310.0])
        assert r["status"] == "VALIDO"
        assert r["preco_referencia"] == 130.0
        assert len(r["cotacoes_excluidas"]) == 1
        assert r["cotacoes_excluidas"][0]["preco"] == 310.0

    def test_apos_exclusao_menos_de_3_retorna_insuficiente(self):
        # [120, 135, 310]: mediana_prov=135, limite=202.5, 310 excluída → 2 válidas < 3
        r = ia_pesquisa_mercado.calcular_referencia([120.0, 135.0, 310.0])
        assert r["status"] == "INSUFICIENTE"
        assert r["preco_referencia"] is None

    def test_lista_vazia_retorna_insuficiente(self):
        r = ia_pesquisa_mercado.calcular_referencia([])
        assert r["status"] == "INSUFICIENTE"
        assert r["preco_referencia"] is None

    def test_menos_de_3_cotacoes_retorna_insuficiente(self):
        r = ia_pesquisa_mercado.calcular_referencia([100.0, 110.0])
        assert r["status"] == "INSUFICIENTE"
        assert r["preco_referencia"] is None

    def test_exatamente_3_cotacoes_iguais_retorna_valido(self):
        r = ia_pesquisa_mercado.calcular_referencia([100.0, 100.0, 100.0])
        assert r["status"] == "VALIDO"
        assert r["preco_referencia"] == 100.0


def _mock_urlopen(payload: dict):
    data = json.dumps({"content": [{"text": json.dumps(payload)}]}).encode("utf-8")
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=data)))
    cm.__exit__ = MagicMock(return_value=False)
    return cm


class TestExtrairItensTR:
    def test_retorna_lista_com_campos_esperados(self):
        payload = {"itens": [
            {"id": 1, "descricao": "Consultoria TI", "unidade": "hora",
             "quantidade_estimada": 500.0},
            {"id": 2, "descricao": "Licença SW", "unidade": "un",
             "quantidade_estimada": 10.0},
        ]}
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(payload)):
            result = ia_pesquisa_mercado.extrair_itens_tr("texto do TR", "key")
        assert len(result) == 2
        assert result[0]["descricao"] == "Consultoria TI"
        assert result[1]["unidade"] == "un"

    def test_json_malformado_levanta_runtime_error(self):
        data = json.dumps({"content": [{"text": "não é json"}]}).encode("utf-8")
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=data)))
        cm.__exit__ = MagicMock(return_value=False)
        with patch("ia_utils.urllib.request.urlopen", return_value=cm):
            with pytest.raises(RuntimeError, match="JSON válido"):
                ia_pesquisa_mercado.extrair_itens_tr("texto", "key")

    def test_http_error_levanta_runtime_error_com_codigo(self):
        err = urllib.error.HTTPError(
            url="https://api.anthropic.com/v1/messages",
            code=401, msg="Unauthorized", hdrs=None,
            fp=MagicMock(read=MagicMock(return_value=b'{"error":"invalid"}')),
        )
        with patch("ia_utils.urllib.request.urlopen", side_effect=err):
            with pytest.raises(RuntimeError, match="HTTP 401"):
                ia_pesquisa_mercado.extrair_itens_tr("texto", "key")


_ITENS_TR = [
    {"id": 1, "descricao": "Consultoria TI", "unidade": "hora",
     "quantidade_estimada": 100.0},
    {"id": 2, "descricao": "Licença SW", "unidade": "un",
     "quantidade_estimada": 5.0},
]

_COTACOES_VALIDAS = {
    "fornecedores": [
        {"nome": "Empresa A", "cnpj": "11.111.111/0001-11"},
        {"nome": "Empresa B", "cnpj": "22.222.222/0001-22"},
        {"nome": "Empresa C", "cnpj": "33.333.333/0001-33"},
    ],
    "itens_cotados": [
        {"item_id": 1, "descricao_no_orcamento": "Consultoria",
         "cotacoes": [
             {"fornecedor": "Empresa A", "preco_unitario": 120.0},
             {"fornecedor": "Empresa B", "preco_unitario": 130.0},
             {"fornecedor": "Empresa C", "preco_unitario": 125.0},
         ]},
        {"item_id": 2, "descricao_no_orcamento": "Licença",
         "cotacoes": [
             {"fornecedor": "Empresa A", "preco_unitario": 500.0},
             {"fornecedor": "Empresa B", "preco_unitario": 480.0},
             {"fornecedor": "Empresa C", "preco_unitario": 490.0},
         ]},
    ],
}

_PARECER = {"parecer_narrativo": "Pesquisa válida. Cotações atendem os critérios."}


class TestAnalisar:
    def test_todos_itens_validos_retorna_pesquisa_valida(self):
        side_effects = [_mock_urlopen(_COTACOES_VALIDAS), _mock_urlopen(_PARECER)]
        with patch("ia_utils.urllib.request.urlopen", side_effect=side_effects):
            r = ia_pesquisa_mercado.analisar(_ITENS_TR, "texto orçamentos", "key")
        assert r["status_geral"] == "VÁLIDA"
        assert len(r["itens_avaliados"]) == 2
        assert r["itens_avaliados"][0]["status"] == "VALIDO"
        assert r["parecer_narrativo"] == "Pesquisa válida. Cotações atendem os critérios."

    def test_item_insuficiente_gera_com_ressalvas(self):
        cotacoes_insuf = {
            **_COTACOES_VALIDAS,
            "itens_cotados": [
                # item 1: só 2 cotações → INSUFICIENTE
                {"item_id": 1, "descricao_no_orcamento": "Consultoria",
                 "cotacoes": [
                     {"fornecedor": "Empresa A", "preco_unitario": 120.0},
                     {"fornecedor": "Empresa B", "preco_unitario": 130.0},
                 ]},
                _COTACOES_VALIDAS["itens_cotados"][1],  # item 2 válido
            ],
        }
        side_effects = [_mock_urlopen(cotacoes_insuf), _mock_urlopen(_PARECER)]
        with patch("ia_utils.urllib.request.urlopen", side_effect=side_effects):
            r = ia_pesquisa_mercado.analisar(_ITENS_TR, "texto", "key")
        assert r["status_geral"] == "COM RESSALVAS"
        assert r["itens_avaliados"][0]["status"] == "INSUFICIENTE"

    def test_maioria_insuficiente_gera_invalida(self):
        cotacoes_insuf = {
            **_COTACOES_VALIDAS,
            "itens_cotados": [
                {"item_id": 1, "descricao_no_orcamento": "Consultoria",
                 "cotacoes": [{"fornecedor": "Empresa A", "preco_unitario": 120.0}]},
                {"item_id": 2, "descricao_no_orcamento": "Licença",
                 "cotacoes": [{"fornecedor": "Empresa B", "preco_unitario": 480.0}]},
            ],
        }
        side_effects = [_mock_urlopen(cotacoes_insuf), _mock_urlopen(_PARECER)]
        with patch("ia_utils.urllib.request.urlopen", side_effect=side_effects):
            r = ia_pesquisa_mercado.analisar(_ITENS_TR, "texto", "key")
        assert r["status_geral"] == "INVÁLIDA"

    def test_json_malformado_levanta_runtime_error(self):
        data = json.dumps({"content": [{"text": "não é json"}]}).encode("utf-8")
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=data)))
        cm.__exit__ = MagicMock(return_value=False)
        with patch("ia_utils.urllib.request.urlopen", return_value=cm):
            with pytest.raises(RuntimeError, match="JSON válido"):
                ia_pesquisa_mercado.analisar(_ITENS_TR, "texto", "key")

    def test_url_error_levanta_runtime_error(self):
        err = urllib.error.URLError("Connection refused")
        with patch("ia_utils.urllib.request.urlopen", side_effect=err):
            with pytest.raises(RuntimeError):
                ia_pesquisa_mercado.analisar(_ITENS_TR, "texto", "key")

    def test_lista_de_itens_vazia_retorna_invalida_sem_api(self):
        with patch("ia_utils.urllib.request.urlopen") as mock_url:
            r = ia_pesquisa_mercado.analisar([], "texto", "key")
        mock_url.assert_not_called()
        assert r["status_geral"] == "INVÁLIDA"
        assert r["itens_avaliados"] == []

    def test_quantidade_estimada_zero_produz_subtotal_zero_nao_none(self):
        """quantidade_estimada=0 deve gerar subtotal=0.0, não None (falsy-zero guard)."""
        itens_tr_zero = [{"id": 1, "descricao": "Item Zero", "unidade": "un",
                          "quantidade_estimada": 0}]
        cotacoes_zero = {
            "fornecedores": [{"nome": "A", "cnpj": ""}],
            "itens_cotados": [{"item_id": 1, "descricao_no_orcamento": "Item Zero",
                               "cotacoes": [
                                   {"fornecedor": "A", "preco_unitario": 100.0},
                                   {"fornecedor": "B", "preco_unitario": 110.0},
                                   {"fornecedor": "C", "preco_unitario": 105.0},
                               ]}],
        }
        side_effects = [_mock_urlopen(cotacoes_zero), _mock_urlopen(_PARECER)]
        with patch("ia_utils.urllib.request.urlopen", side_effect=side_effects):
            r = ia_pesquisa_mercado.analisar(itens_tr_zero, "texto", "key")
        assert r["itens_avaliados"][0]["subtotal_estimado"] == 0.0
        assert r["valor_total_estimado"] == 0.0

    def test_item_id_string_numerico_e_aceito(self):
        """item_id retornado como string '1' deve ser parseado sem crash."""
        cotacoes_str_id = {
            **_COTACOES_VALIDAS,
            "itens_cotados": [
                {**_COTACOES_VALIDAS["itens_cotados"][0], "item_id": "1"},
                {**_COTACOES_VALIDAS["itens_cotados"][1], "item_id": "2"},
            ],
        }
        side_effects = [_mock_urlopen(cotacoes_str_id), _mock_urlopen(_PARECER)]
        with patch("ia_utils.urllib.request.urlopen", side_effect=side_effects):
            r = ia_pesquisa_mercado.analisar(_ITENS_TR, "texto", "key")
        assert r["status_geral"] == "VÁLIDA"

    def test_item_id_nao_numerico_nao_crasha(self):
        """item_id='item_1' deve ser silenciosamente ignorado sem ValueError."""
        cotacoes_bad_id = {
            **_COTACOES_VALIDAS,
            "itens_cotados": [
                {**_COTACOES_VALIDAS["itens_cotados"][0], "item_id": "item_1"},
            ],
        }
        side_effects = [_mock_urlopen(cotacoes_bad_id), _mock_urlopen(_PARECER)]
        with patch("ia_utils.urllib.request.urlopen", side_effect=side_effects):
            r = ia_pesquisa_mercado.analisar(_ITENS_TR, "texto", "key")
        # O item não é associado → ambos INSUFICIENTE, mas não crasha
        assert r["status_geral"] in ("INVÁLIDA", "COM RESSALVAS")

    def test_preco_unitario_como_string_e_coercido_para_float(self):
        """preco_unitario retornado como string deve ser convertido, não causar TypeError."""
        cotacoes_str_preco = {
            **_COTACOES_VALIDAS,
            "itens_cotados": [
                {**_COTACOES_VALIDAS["itens_cotados"][0],
                 "cotacoes": [
                     {"fornecedor": "Empresa A", "preco_unitario": "120.0"},
                     {"fornecedor": "Empresa B", "preco_unitario": "130.0"},
                     {"fornecedor": "Empresa C", "preco_unitario": "125.0"},
                 ]},
                _COTACOES_VALIDAS["itens_cotados"][1],
            ],
        }
        side_effects = [_mock_urlopen(cotacoes_str_preco), _mock_urlopen(_PARECER)]
        with patch("ia_utils.urllib.request.urlopen", side_effect=side_effects):
            r = ia_pesquisa_mercado.analisar(_ITENS_TR, "texto", "key")
        assert r["itens_avaliados"][0]["status"] == "VALIDO"
        assert r["itens_avaliados"][0]["preco_referencia"] == 125.0
