from __future__ import annotations
import pytest
from datetime import date
import relatorio_reabilitacao


def _dados_empresa():
    return {
        "razao_social": "EMPRESA TESTE LTDA",
        "cnpj": "11222333000181",
        "porte": "MICRO EMPRESA",
    }


def _dados_sancao(tipo: str = "impedimento"):
    return {
        "tipo_sancao":    tipo,
        "data_aplicacao": date(2024, 1, 1),
        "orgao":          "Ministério da Gestão",
        "multa_aplicada": True,
        "multa_valor":    5000.0,
        "multa_quitada":  True,
    }


def _parecer_elegivel():
    return {
        "parecer": "ELEGÍVEL",
        "condicoes_avaliadas": [
            {"numero": "I",   "descricao": "Reparação do dano",  "status": "ATENDIDA", "observacao": ""},
            {"numero": "II",  "descricao": "Pagamento de multa", "status": "ATENDIDA", "observacao": ""},
            {"numero": "III", "descricao": "Prazo mínimo",       "status": "ATENDIDA", "observacao": ""},
            {"numero": "IV",  "descricao": "Cond. punitivo",     "status": "ATENDIDA", "observacao": ""},
            {"numero": "V",   "descricao": "Análise jurídica",   "status": "ATENDIDA", "observacao": ""},
        ],
        "sintese":    "Todas as condições estão atendidas.",
        "base_legal": ["Art. 163, Par. Único, Lei 14.133/2021"],
    }


class TestGerarRelatorioTecnico:
    def test_retorna_bytes_nao_vazios(self):
        pdf = relatorio_reabilitacao.gerar_relatorio_tecnico(
            "11222333000181", _dados_empresa(), _dados_sancao(), _parecer_elegivel()
        )
        assert isinstance(pdf, bytes)
        assert len(pdf) > 2000

    def test_comeca_com_magic_bytes_pdf(self):
        pdf = relatorio_reabilitacao.gerar_relatorio_tecnico(
            "11222333000181", _dados_empresa(), _dados_sancao(), _parecer_elegivel()
        )
        assert pdf[:4] == b"%PDF"

    def test_caracteres_especiais_nao_quebram_pdf(self):
        dados = {**_dados_empresa(), "razao_social": "EMPRESA <TESTE> & CIA LTDA"}
        pdf = relatorio_reabilitacao.gerar_relatorio_tecnico(
            "11222333000181", dados, _dados_sancao(), _parecer_elegivel()
        )
        assert isinstance(pdf, bytes)
        assert len(pdf) > 2000


class TestGerarMinutaRequerimento:
    def test_retorna_bytes_nao_vazios(self):
        pdf = relatorio_reabilitacao.gerar_minuta_requerimento(
            "11222333000181", _dados_empresa(), _dados_sancao(), _parecer_elegivel()
        )
        assert isinstance(pdf, bytes)
        assert len(pdf) > 2000

    def test_comeca_com_magic_bytes_pdf(self):
        pdf = relatorio_reabilitacao.gerar_minuta_requerimento(
            "11222333000181", _dados_empresa(), _dados_sancao(), _parecer_elegivel()
        )
        assert pdf[:4] == b"%PDF"

    def test_tipo_impedimento_menciona_art_156_iii(self):
        import pdfplumber, io
        pdf = relatorio_reabilitacao.gerar_minuta_requerimento(
            "11222333000181", _dados_empresa(), _dados_sancao("impedimento"), _parecer_elegivel()
        )
        texto = ""
        with pdfplumber.open(io.BytesIO(pdf)) as doc:
            for pg in doc.pages:
                texto += pg.extract_text() or ""
        assert "156" in texto

    def test_tipo_inidoneidade_menciona_art_156_iv(self):
        import pdfplumber, io
        pdf = relatorio_reabilitacao.gerar_minuta_requerimento(
            "11222333000181", _dados_empresa(), _dados_sancao("inidoneidade"), _parecer_elegivel()
        )
        texto = ""
        with pdfplumber.open(io.BytesIO(pdf)) as doc:
            for pg in doc.pages:
                texto += pg.extract_text() or ""
        assert "156" in texto
