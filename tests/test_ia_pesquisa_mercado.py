from __future__ import annotations
import json
import pytest
import urllib.error
from unittest.mock import patch, MagicMock
import ia_pesquisa_mercado


class TestConstantes:
    def test_status_item_tem_chaves_esperadas(self):
        assert set(ia_pesquisa_mercado.STATUS_ITEM.keys()) == {
            "VALIDO", "INSUFICIENTE", "INEXEQUIVEL"
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
