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


from unittest.mock import patch


class TestBuscarReceita:
    @patch('ddi_consultas.requests.get')
    def test_empresa_ativa(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "razao_social": "EMPRESA TESTE LTDA",
            "descricao_situacao_cadastral": "ATIVA",
            "descricao_porte": "MICRO EMPRESA",
            "cnae_fiscal_descricao": "Desenvolvimento de software",
            "data_inicio_atividade": "2010-01-15",
            "qsa": [{"nome_socio": "FULANO DA SILVA", "cargo": "SÓCIO-ADMINISTRADOR"}],
        }

        result = ddi_consultas._buscar_receita("11222333000181")

        assert result["razao_social"] == "EMPRESA TESTE LTDA"
        assert result["situacao"] == "ATIVA"
        assert result["porte"] == "MICRO EMPRESA"
        assert result["socios"][0]["nome"] == "FULANO DA SILVA"

    @patch('ddi_consultas.requests.get')
    def test_timeout_retorna_none(self, mock_get):
        import requests as req_lib
        mock_get.side_effect = req_lib.exceptions.Timeout()

        result = ddi_consultas._buscar_receita("11222333000181")

        assert result is None

    @patch('ddi_consultas.requests.get')
    def test_status_404_retorna_none(self, mock_get):
        mock_get.return_value.status_code = 404

        result = ddi_consultas._buscar_receita("11222333000181")

        assert result is None
