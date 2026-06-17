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

    def test_string_nao_numerica_retorna_default(self):
        assert ia_utils.fmt_brl_opcional("abc") == "-"

    def test_string_nao_numerica_com_default_personalizado(self):
        assert ia_utils.fmt_brl_opcional("não informado", default="INSUF.") == "INSUF."


_NORM = {"DEFERIVEL": "DEFERÍVEL"}
_VALID = {"DEFERÍVEL", "DEFERÍVEL COM RESSALVAS", "INDEFERÍVEL"}


class TestNormalizarParecer:
    def test_valor_canonico_passa_sem_aviso(self):
        d = {"parecer": "DEFERÍVEL"}
        ia_utils.normalizar_parecer(d, _NORM, _VALID, "INDEFERÍVEL", "mod")
        assert d["parecer"] == "DEFERÍVEL"
        assert "_aviso_parecer" not in d

    def test_alias_normalizado_sem_aviso(self):
        d = {"parecer": "DEFERIVEL"}
        ia_utils.normalizar_parecer(d, _NORM, _VALID, "INDEFERÍVEL", "mod")
        assert d["parecer"] == "DEFERÍVEL"
        assert "_aviso_parecer" not in d

    def test_none_usa_fallback_sem_aviso(self):
        d = {}
        ia_utils.normalizar_parecer(d, _NORM, _VALID, "INDEFERÍVEL", "mod")
        assert d["parecer"] == "INDEFERÍVEL"
        assert "_aviso_parecer" not in d

    def test_valor_desconhecido_armazena_aviso_e_usa_fallback(self):
        d = {"parecer": "APROVADO PARCIALMENTE"}
        ia_utils.normalizar_parecer(d, _NORM, _VALID, "INDEFERÍVEL", "mod")
        assert d["parecer"] == "INDEFERÍVEL"
        assert d["_aviso_parecer"] == "APROVADO PARCIALMENTE"

    def test_string_vazia_armazena_aviso_vazio(self):
        d = {"parecer": ""}
        ia_utils.normalizar_parecer(d, _NORM, _VALID, "INDEFERÍVEL", "mod")
        assert d["parecer"] == "INDEFERÍVEL"
        assert d["_aviso_parecer"] == ""

    def test_pop_remove_aviso_injetado_anteriormente(self):
        d = {"parecer": "DEFERÍVEL", "_aviso_parecer": "valor injetado"}
        ia_utils.normalizar_parecer(d, _NORM, _VALID, "INDEFERÍVEL", "mod")
        assert d["parecer"] == "DEFERÍVEL"
        assert "_aviso_parecer" not in d

    def test_double_miss_norm_map_aponta_para_valor_invalido(self):
        # norm_map maps "FOO" → "BAR", but "BAR" is not in valid_set → fallback
        _norm_double = {"FOO": "BAR"}
        d = {"parecer": "FOO"}
        ia_utils.normalizar_parecer(d, _norm_double, _VALID, "INDEFERÍVEL", "mod")
        assert d["parecer"] == "INDEFERÍVEL"
        assert d["_aviso_parecer"] == "FOO"
