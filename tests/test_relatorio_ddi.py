from __future__ import annotations
import relatorio_ddi


def _dados():
    return {
        "razao_social": "EMPRESA TESTE LTDA",
        "cnpj": "11222333000181",
        "situacao": "ATIVA",
        "porte": "MICRO EMPRESA",
        "cnae": "Desenvolvimento de software",
        "data_abertura": "2010-01-15",
        "socios": [{"nome": "FULANO DA SILVA", "cargo": "SÓCIO-ADMINISTRADOR"}],
        "ceis": [],
        "cnep": [],
        "pro_etica": False,
        "grande_vulto": False,
        "valor_contrato": 100_000.0,
    }


def _fid():
    return {"q1": "Sim", "q2": "Não", "q3": "Sim", "q4": "Não sei", "q5": "Não"}


def _parecer():
    return {
        "risco_geral": "BAIXO",
        "dimensoes": {
            "situacao_cadastral": {"status": "ok", "descricao": "Empresa ativa."},
            "sancoes": {"status": "ok", "achados": []},
            "programa_integridade": {
                "status": "alerta", "obrigatorio": False,
                "pro_etica": False, "descricao": "Sem PI declarado.",
            },
            "fid": {"status": "ok", "inconsistencias": [], "descricao": "Consistente."},
            "contexto_contrato": {
                "status": "ok", "grande_vulto": False, "descricao": "Abaixo do limite.",
            },
        },
        "resumo": "Empresa sem ocorrências graves.",
        "recomendacao": "Contratação pode prosseguir.",
        "base_legal": ["Portaria SEGES/ME 8.678/2021, art. 2º, III"],
        "validade_fid": "12 meses a partir da data desta consulta",
    }


class TestGerarPdf:
    def test_retorna_bytes(self):
        pdf = relatorio_ddi.gerar_pdf("11222333000181", 100_000.0, _dados(), _fid(), _parecer())
        assert isinstance(pdf, bytes)

    def test_comeca_com_magic_bytes_pdf(self):
        pdf = relatorio_ddi.gerar_pdf("11222333000181", 100_000.0, _dados(), _fid(), _parecer())
        assert pdf[:4] == b'%PDF'

    def test_tamanho_minimo(self):
        pdf = relatorio_ddi.gerar_pdf("11222333000181", 100_000.0, _dados(), _fid(), _parecer())
        assert len(pdf) > 2000

    def test_risco_alto_nao_levanta_erro(self):
        parecer_alto = {**_parecer(), "risco_geral": "ALTO"}
        pdf = relatorio_ddi.gerar_pdf("11222333000181", 300_000_000.0, _dados(), _fid(), parecer_alto)
        assert pdf[:4] == b'%PDF'
