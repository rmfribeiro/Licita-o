import pytest
import ddi_consultas


class TestValidarCnpj:
    def test_cnpj_valido(self):
        assert ddi_consultas._validar_cnpj("11222333000181") is True

    def test_cnpj_com_mascara(self):
        assert ddi_consultas._validar_cnpj("11.222.333/0001-81") is True

    def test_cnpj_digitos_errados(self):
        assert ddi_consultas._validar_cnpj("11222333000100") is False

    def test_cnpj_todos_iguais(self):
        assert ddi_consultas._validar_cnpj("11111111111111") is False

    def test_cnpj_curto(self):
        assert ddi_consultas._validar_cnpj("1234567") is False

    def test_cnpj_vazio(self):
        assert ddi_consultas._validar_cnpj("") is False
