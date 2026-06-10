from __future__ import annotations
import pytest
import ia_utils


class TestSafeFloat:
    def test_none_retorna_zero(self):
        assert ia_utils.safe_float(None) == 0.0

    def test_zero_retorna_zero(self):
        assert ia_utils.safe_float(0.0) == 0.0

    def test_valor_positivo(self):
        assert ia_utils.safe_float(150_000.0) == 150_000.0

    def test_string_vazia_retorna_zero(self):
        assert ia_utils.safe_float("") == 0.0

    def test_string_nao_numerica_retorna_zero(self):
        assert ia_utils.safe_float("abc") == 0.0

    def test_string_numerica_convertida(self):
        assert ia_utils.safe_float("1234.56") == 1234.56


class TestOptionalFloat:
    def test_none_retorna_none(self):
        assert ia_utils.optional_float(None) is None

    def test_zero_retorna_zero(self):
        assert ia_utils.optional_float(0.0) == 0.0

    def test_valor_positivo(self):
        assert ia_utils.optional_float(150_000.0) == 150_000.0

    def test_string_nao_numerica_retorna_zero(self):
        assert ia_utils.optional_float("abc") == 0.0

    def test_distingue_none_de_zero(self):
        assert ia_utils.optional_float(None) is None
        assert ia_utils.optional_float(0.0) == 0.0


class TestFmtBrl:
    def test_formata_valor_simples(self):
        assert ia_utils.fmt_brl(1234.56) == "R$ 1.234,56"

    def test_formata_zero(self):
        assert ia_utils.fmt_brl(0.0) == "R$ 0,00"

    def test_formata_valor_grande(self):
        assert ia_utils.fmt_brl(1_000_000.0) == "R$ 1.000.000,00"

    def test_formata_centavos(self):
        assert ia_utils.fmt_brl(0.01) == "R$ 0,01"


class TestFmtBrlOpcional:
    def test_none_retorna_default(self):
        assert ia_utils.fmt_brl_opcional(None) == "-"

    def test_none_com_default_customizado(self):
        assert ia_utils.fmt_brl_opcional(None, default="não informado") == "não informado"

    def test_zero_formata_normalmente(self):
        assert ia_utils.fmt_brl_opcional(0.0) == "R$ 0,00"

    def test_valor_positivo_formata_normalmente(self):
        assert ia_utils.fmt_brl_opcional(1234.56) == "R$ 1.234,56"

    def test_valor_grande(self):
        assert ia_utils.fmt_brl_opcional(1_000_000.0) == "R$ 1.000.000,00"
