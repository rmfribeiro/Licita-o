from __future__ import annotations
import relatorio_etp


def _parecer() -> dict:
    return {
        "adequacao_geral": "ADEQUADO COM RESSALVAS",
        "dimensoes": {
            "descricao_necessidade":       {"status": "ok",     "descricao": "Necessidade clara."},
            "alinhamento_estrategico":     {"status": "ok",     "descricao": "Alinhado ao PPA."},
            "requisitos_contratacao":      {"status": "alerta", "descricao": "Incompleto."},
            "levantamento_mercado":        {"status": "ok",     "descricao": "Pesquisado."},
            "estimativa_quantidade_valor": {"status": "alerta", "descricao": "Metodologia ausente."},
            "sustentabilidade":            {"status": "ok",     "descricao": "Critérios presentes."},
            "parcelamento":                {"status": "ok",     "descricao": "Justificado."},
            "posicionamento_conclusivo":   {"status": "ok",     "descricao": "Favorável."},
        },
        "pontos_criticos": ["Requisitos incompletos."],
        "recomendacoes": ["Detalhar especificações."],
        "base_legal": ["IN SEGES/MGI 58/2022", "Lei 14.133/2021, art. 18, I"],
    }


class TestGerarPdf:
    def test_retorna_bytes(self):
        pdf = relatorio_etp.gerar_pdf(["etp.pdf"], [], _parecer())
        assert isinstance(pdf, bytes)

    def test_comeca_com_magic_bytes_pdf(self):
        pdf = relatorio_etp.gerar_pdf(["etp.pdf"], [], _parecer())
        assert pdf[:4] == b"%PDF"

    def test_tamanho_minimo(self):
        pdf = relatorio_etp.gerar_pdf(["etp.pdf"], [], _parecer())
        assert len(pdf) > 2000

    def test_com_avisos_nao_levanta_erro(self):
        avisos = ["Texto truncado em 50000 chars.", "Formato nao suportado: planilha.xlsx"]
        pdf = relatorio_etp.gerar_pdf(["etp.pdf", "anexo.docx"], avisos, _parecer())
        assert pdf[:4] == b"%PDF"

    def test_adequacao_inadequado_nao_levanta_erro(self):
        parecer = {**_parecer(), "adequacao_geral": "INADEQUADO"}
        pdf = relatorio_etp.gerar_pdf(["etp.pdf"], [], parecer)
        assert pdf[:4] == b"%PDF"
