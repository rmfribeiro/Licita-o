from __future__ import annotations
import io
import pdfplumber
import relatorio_pesquisa_mercado

_OBJETO = "Contratação de consultoria em TI"

_ITENS = [
    {
        "item_id":             1,
        "descricao":           "Consultoria TI",
        "unidade":             "hora",
        "quantidade_estimada": 100.0,
        "cotacoes_detalhadas": [
            {"fornecedor": "Empresa A", "preco_unitario": 120.0},
            {"fornecedor": "Empresa B", "preco_unitario": 125.0},
            {"fornecedor": "Empresa C", "preco_unitario": 130.0},
        ],
        "preco_referencia":   125.0,
        "cotacoes_validas":   [120.0, 125.0, 130.0],
        "cotacoes_excluidas": [],
        "status":             "VALIDO",
        "subtotal_estimado":  12500.0,
    },
    {
        "item_id":             2,
        "descricao":           "Licença SW",
        "unidade":             "un",
        "quantidade_estimada": 5.0,
        "cotacoes_detalhadas": [
            {"fornecedor": "Empresa A", "preco_unitario": 500.0},
        ],
        "preco_referencia":   None,
        "cotacoes_validas":   [500.0],
        "cotacoes_excluidas": [],
        "status":             "INSUFICIENTE",
        "subtotal_estimado":  None,
    },
]

_FORNECEDORES = [
    {"nome": "Empresa A", "cnpj": "11.111.111/0001-11"},
    {"nome": "Empresa B", "cnpj": "22.222.222/0001-22"},
    {"nome": "Empresa C", "cnpj": "33.333.333/0001-33"},
]


class TestGerarMapaPrecos:
    def test_retorna_bytes_pdf(self):
        pdf = relatorio_pesquisa_mercado.gerar_mapa_precos(
            _OBJETO, _ITENS, _FORNECEDORES, 12500.0
        )
        assert isinstance(pdf, bytes)
        assert pdf[:4] == b"%PDF"

    def test_inclui_nome_do_fornecedor(self):
        pdf = relatorio_pesquisa_mercado.gerar_mapa_precos(
            _OBJETO, _ITENS, _FORNECEDORES, 12500.0
        )
        with pdfplumber.open(io.BytesIO(pdf)) as doc:
            texto = "\n".join(pg.extract_text() or "" for pg in doc.pages)
        assert "Empresa A" in texto

    def test_item_insuficiente_aparece_como_insuf(self):
        pdf = relatorio_pesquisa_mercado.gerar_mapa_precos(
            _OBJETO, _ITENS, _FORNECEDORES, 12500.0
        )
        with pdfplumber.open(io.BytesIO(pdf)) as doc:
            texto = "\n".join(pg.extract_text() or "" for pg in doc.pages)
        assert "INSUF" in texto

    def test_caracteres_especiais_nao_quebram_pdf(self):
        itens_xss = [{**_ITENS[0], "descricao": "Item <Teste> & \"Especial\""}]
        pdf = relatorio_pesquisa_mercado.gerar_mapa_precos(
            "Objeto <com> &amp; especiais", itens_xss, _FORNECEDORES, 1000.0
        )
        assert isinstance(pdf, bytes)
        assert pdf[:4] == b"%PDF"


class TestGerarRelatorioPesquisa:
    def test_retorna_bytes_pdf(self):
        pdf = relatorio_pesquisa_mercado.gerar_relatorio_pesquisa(
            _OBJETO, _ITENS, _FORNECEDORES, "Parecer aprovado.", "VÁLIDA", 12500.0
        )
        assert isinstance(pdf, bytes)
        assert pdf[:4] == b"%PDF"

    def test_status_valida_aparece_no_relatorio(self):
        pdf = relatorio_pesquisa_mercado.gerar_relatorio_pesquisa(
            _OBJETO, _ITENS, _FORNECEDORES, "Parecer aprovado.", "VÁLIDA", 12500.0
        )
        with pdfplumber.open(io.BytesIO(pdf)) as doc:
            texto = "\n".join(pg.extract_text() or "" for pg in doc.pages)
        assert "VÁLIDA" in texto
