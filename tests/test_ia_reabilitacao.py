from __future__ import annotations
import pytest
from datetime import date
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
