from __future__ import annotations
import json
import types
import urllib.error
import pytest
from unittest.mock import patch, MagicMock
import ia_recebimento


class TestConstantes:
    def test_tipos_objeto_tem_3_entradas(self):
        assert len(ia_recebimento.TIPOS_OBJETO) == 3

    def test_tipos_objeto_chaves(self):
        assert set(ia_recebimento.TIPOS_OBJETO.keys()) == {"servico", "bem", "obra"}

    def test_parecer_options_tem_3_entradas(self):
        assert len(ia_recebimento.PARECER_OPTIONS) == 3

    def test_parecer_options_chaves(self):
        assert set(ia_recebimento.PARECER_OPTIONS.keys()) == {
            "APTO", "APTO COM RESSALVAS", "INAPTO"
        }

    def test_status_condicao_tem_3_entradas(self):
        assert len(ia_recebimento.STATUS_CONDICAO) == 3

    def test_status_condicao_chaves(self):
        assert set(ia_recebimento.STATUS_CONDICAO.keys()) == {
            "ATENDIDA", "PARCIAL", "AUSENTE"
        }

    def test_constantes_sao_mapping_proxy(self):
        assert isinstance(ia_recebimento.TIPOS_OBJETO, types.MappingProxyType)
        assert isinstance(ia_recebimento.PARECER_OPTIONS, types.MappingProxyType)
        assert isinstance(ia_recebimento.STATUS_CONDICAO, types.MappingProxyType)
