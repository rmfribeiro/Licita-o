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


class TestBuscarCeis:
    @patch('ddi_consultas.requests.get')
    def test_com_sancao_ativa(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = [{
            "nomeInfrator": "EMPRESA TESTE LTDA",
            "orgaoSancionador": {"nome": "CGU"},
            "dataInicioSancao": "2023-01-01",
            "dataFimSancao": "2025-12-31",
            "situacaoAtual": "Ativo",
            "fundamentacaoLegal": "Lei 8.666/93, art. 87",
        }]

        result = ddi_consultas._buscar_ceis("11222333000181")

        assert len(result) == 1
        assert result[0]["situacaoAtual"] == "Ativo"
        assert result[0]["orgaoSancionador"] == "CGU"

    @patch('ddi_consultas.requests.get')
    def test_sem_sancao_retorna_lista_vazia(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = []

        result = ddi_consultas._buscar_ceis("11222333000181")

        assert result == []

    @patch('ddi_consultas._get_cgu_key', return_value=None)
    def test_sem_chave_retorna_lista_vazia(self, mock_key):
        result = ddi_consultas._buscar_ceis("11222333000181")

        assert result == []

    @patch('ddi_consultas.requests.get')
    def test_timeout_retorna_lista_vazia(self, mock_get):
        import requests as req_lib
        mock_get.side_effect = req_lib.exceptions.Timeout()

        result = ddi_consultas._buscar_ceis("11222333000181")

        assert result == []


class TestBuscarCnep:
    @patch('ddi_consultas.requests.get')
    def test_com_punicao(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = [{
            "nomeInfrator": "EMPRESA TESTE LTDA",
            "orgaoSancionador": {"nome": "CGU"},
            "dataInicioSancao": "2022-06-01",
            "dataFimSancao": None,
            "situacaoAtual": "Ativo",
            "tipoPenalidade": "Multa",
            "fundamentacaoLegal": "Lei 12.846/2013, art. 6º",
        }]

        result = ddi_consultas._buscar_cnep("11222333000181")

        assert len(result) == 1
        assert result[0]["tipoPenalidade"] == "Multa"
        assert result[0]["situacaoAtual"] == "Ativo"

    @patch('ddi_consultas.requests.get')
    def test_sem_punicao(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = []

        result = ddi_consultas._buscar_cnep("11222333000181")

        assert result == []

    @patch('ddi_consultas._get_cgu_key', return_value=None)
    def test_sem_chave_retorna_lista_vazia(self, mock_key):
        result = ddi_consultas._buscar_cnep("11222333000181")

        assert result == []

    @patch('ddi_consultas.requests.get')
    def test_timeout_retorna_lista_vazia(self, mock_get):
        import requests as req_lib
        mock_get.side_effect = req_lib.exceptions.Timeout()

        result = ddi_consultas._buscar_cnep("11222333000181")

        assert result == []


class TestVerificarProEtica:
    @patch('ddi_consultas.requests.get')
    def test_empresa_consta_formatada(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = "...11.222.333/0001-81 EMPRESA TESTE..."

        result = ddi_consultas._verificar_pro_etica("11222333000181")

        assert result is True

    @patch('ddi_consultas.requests.get')
    def test_empresa_consta_sem_mascara(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = "...11222333000181 EMPRESA TESTE..."

        result = ddi_consultas._verificar_pro_etica("11222333000181")

        assert result is True

    @patch('ddi_consultas.requests.get')
    def test_empresa_nao_consta(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = "lista sem match algum"

        result = ddi_consultas._verificar_pro_etica("11222333000181")

        assert result is False

    @patch('ddi_consultas.requests.get')
    def test_erro_retorna_none(self, mock_get):
        import requests as req_lib
        mock_get.side_effect = req_lib.exceptions.Timeout()

        result = ddi_consultas._verificar_pro_etica("11222333000181")

        assert result is None


class TestEGrandeVulto:
    def test_acima_do_limite(self):
        assert ddi_consultas._e_grande_vulto(239_000_001.0) is True

    def test_abaixo_do_limite(self):
        assert ddi_consultas._e_grande_vulto(238_999_999.0) is False

    def test_igual_ao_limite_nao_e_grande_vulto(self):
        assert ddi_consultas._e_grande_vulto(239_000_000.0) is False

    def test_none_retorna_none(self):
        assert ddi_consultas._e_grande_vulto(None) is None


class TestConsultar:
    def test_cnpj_invalido_levanta_valor_error(self):
        with pytest.raises(ValueError, match="CNPJ inválido"):
            ddi_consultas.consultar("00000000000000", 100_000.0)

    @patch('ddi_consultas._buscar_receita')
    @patch('ddi_consultas._buscar_ceis')
    @patch('ddi_consultas._buscar_cnep')
    @patch('ddi_consultas._verificar_pro_etica')
    def test_resultado_consolidado(self, mock_pro, mock_cnep, mock_ceis, mock_receita):
        mock_receita.return_value = {
            "razao_social": "EMPRESA TESTE LTDA",
            "nome_fantasia": "",
            "situacao": "ATIVA",
            "porte": "MICRO EMPRESA",
            "cnae": "Desenvolvimento de software",
            "data_abertura": "2010-01-15",
            "socios": [],
        }
        mock_ceis.return_value = []
        mock_cnep.return_value = []
        mock_pro.return_value = False

        result = ddi_consultas.consultar("11222333000181", 100_000.0)

        assert result["razao_social"] == "EMPRESA TESTE LTDA"
        assert result["ceis"] == []
        assert result["cnep"] == []
        assert result["pro_etica"] is False
        assert result["grande_vulto"] is False
        assert result["valor_contrato"] == 100_000.0
        assert result["cnpj"] == "11222333000181"

    @patch('ddi_consultas._buscar_receita')
    @patch('ddi_consultas._buscar_ceis')
    @patch('ddi_consultas._buscar_cnep')
    @patch('ddi_consultas._verificar_pro_etica')
    def test_grande_vulto_flag(self, mock_pro, mock_cnep, mock_ceis, mock_receita):
        mock_receita.return_value = {
            "razao_social": "CONSTRUTORA GRANDE", "nome_fantasia": "",
            "situacao": "ATIVA", "porte": "GRANDE", "cnae": "Construção",
            "data_abertura": "2000-01-01", "socios": [],
        }
        mock_ceis.return_value = []
        mock_cnep.return_value = []
        mock_pro.return_value = False

        result = ddi_consultas.consultar("11222333000181", 300_000_000.0)

        assert result["grande_vulto"] is True

    @patch('ddi_consultas._buscar_receita', return_value=None)
    @patch('ddi_consultas._buscar_ceis', return_value=[])
    @patch('ddi_consultas._buscar_cnep', return_value=[])
    @patch('ddi_consultas._verificar_pro_etica', return_value=None)
    def test_receita_indisponivel_retorna_campos_vazios(self, *mocks):
        result = ddi_consultas.consultar("11222333000181", 100_000.0)

        assert result["razao_social"] == ""
        assert result["receita_disponivel"] is False

    @patch('ddi_consultas._buscar_receita', return_value=None)
    @patch('ddi_consultas._buscar_ceis', return_value=[])
    @patch('ddi_consultas._buscar_cnep', return_value=[])
    @patch('ddi_consultas._verificar_pro_etica', return_value=None)
    def test_valor_contrato_none_grande_vulto_none(self, *mocks):
        result = ddi_consultas.consultar("11222333000181", None)

        assert result["grande_vulto"] is None
        assert result["valor_contrato"] is None
