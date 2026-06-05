from __future__ import annotations
import pytest
import relatorio_integridade


def _parecer() -> dict:
    return {
        "maturidade_geral": "INICIAL",
        "dimensoes": {
            "compromisso_alta_gestao": {
                "nivel": "INEXISTENTE",
                "achados": ["Nenhum ato formal publicado."],
                "recomendacoes": ["Publicar decreto de instituição do PIP."],
            },
            "diretrizes_integridade":  {"nivel": "INEXISTENTE", "achados": [], "recomendacoes": []},
            "base_legal_normativa":    {"nivel": "INICIAL",     "achados": [], "recomendacoes": []},
            "responsabilizacao":       {"nivel": "INICIAL",     "achados": [], "recomendacoes": []},
            "metodologia_gestao":      {"nivel": "INEXISTENTE", "achados": [], "recomendacoes": []},
            "tres_linhas_defesa":      {"nivel": "INEXISTENTE", "achados": [], "recomendacoes": []},
        },
        "prioridades": ["Publicar decreto.", "Designar responsável.", "Criar código de ética."],
        "resumo_executivo": "O programa está em estágio inicial e requer ação imediata.",
        "base_legal": ["Decreto 11.129/2022", "IN CGU 21/2021"],
    }


class TestGerarPdf:
    def test_retorna_bytes(self):
        resultado = relatorio_integridade.gerar_pdf("Ilha Solteira/SP", _parecer())
        assert isinstance(resultado, bytes)
        assert len(resultado) > 1000

    def test_pdf_comeca_com_magic_bytes(self):
        resultado = relatorio_integridade.gerar_pdf("Ilha Solteira/SP", _parecer())
        assert resultado[:4] == b"%PDF"

    def test_municipio_vazio_nao_quebra(self):
        resultado = relatorio_integridade.gerar_pdf("", _parecer())
        assert isinstance(resultado, bytes)

    def test_parecer_vazio_nao_quebra(self):
        resultado = relatorio_integridade.gerar_pdf("Ilha Solteira/SP", {})
        assert isinstance(resultado, bytes)

    def test_dimensoes_vazias_nao_quebra(self):
        p = _parecer()
        p["dimensoes"] = {}
        resultado = relatorio_integridade.gerar_pdf("Ilha Solteira/SP", p)
        assert isinstance(resultado, bytes)

    def test_prioridades_vazias_nao_quebra(self):
        p = _parecer()
        p["prioridades"] = []
        resultado = relatorio_integridade.gerar_pdf("Ilha Solteira/SP", p)
        assert isinstance(resultado, bytes)
