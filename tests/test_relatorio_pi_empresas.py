from __future__ import annotations
import relatorio_pi_empresas


def _parecer_minimo() -> dict:
    return {
        "scores": {
            "por_parametro": {f"p{i}": 50 for i in range(1, 18)},
            "por_dimensao": {
                "comprometimento_alta_direcao": 50.0,
                "analise_riscos":               50.0,
                "estrutura_controles":          50.0,
                "monitoramento_melhoria":       50.0,
                "transparencia":               50.0,
            },
            "geral": 50.0,
            "nivel": "EM DESENVOLVIMENTO",
        },
        "hipotese": "grande_vulto",
        "dimensoes": {
            "comprometimento_alta_direcao": {
                "sintese": "Comprometimento parcial.",
                "parametros": {
                    "p1": {"achados": ["Política existe."], "recomendacoes": []},
                    "p2": {"achados": [], "recomendacoes": ["Designar CCO."]},
                    "p3": {"achados": [], "recomendacoes": []},
                },
            },
            "analise_riscos": {
                "sintese": "Riscos mapeados.",
                "parametros": {
                    "p4": {"achados": [], "recomendacoes": []},
                    "p5": {"achados": [], "recomendacoes": []},
                },
            },
            "estrutura_controles": {
                "sintese": "Controles presentes.",
                "parametros": {k: {"achados": [], "recomendacoes": []} for k in
                               ["p6", "p7", "p8", "p9", "p10", "p11", "p12"]},
            },
            "monitoramento_melhoria": {
                "sintese": "Monitoramento básico.",
                "parametros": {k: {"achados": [], "recomendacoes": []} for k in
                               ["p13", "p14", "p15"]},
            },
            "transparencia": {
                "sintese": "Transparência adequada.",
                "parametros": {
                    "p16": {"achados": [], "recomendacoes": []},
                    "p17": {"achados": [], "recomendacoes": []},
                },
            },
        },
        "pontos_criticos": ["Canal sem anonimato."],
        "conclusao_hipotese": "PI obrigatório. Score limítrofe.",
        "recomendacoes": ["Implantar KPIs."],
        "base_legal": ["Decreto 12.304/2024, Art. 4º"],
    }


class TestGerarPdf:
    def test_retorna_bytes_nao_vazios(self):
        pdf = relatorio_pi_empresas.gerar_pdf(
            cnpj="11222333000181",
            razao_social="EMPRESA TESTE LTDA",
            hipotese="grande_vulto",
            parecer=_parecer_minimo(),
        )
        assert isinstance(pdf, bytes)
        assert len(pdf) > 1000
        assert pdf[:4] == b"%PDF"

    def test_pdf_sem_pontos_criticos_nao_quebra(self):
        parecer = _parecer_minimo()
        parecer["pontos_criticos"] = []
        pdf = relatorio_pi_empresas.gerar_pdf(
            cnpj="11222333000181",
            razao_social="EMPRESA TESTE LTDA",
            hipotese="desempate",
            parecer=parecer,
        )
        assert isinstance(pdf, bytes)
        assert len(pdf) > 1000

    def test_pdf_com_achados_nulos_nao_quebra(self):
        parecer = _parecer_minimo()
        parecer["dimensoes"]["comprometimento_alta_direcao"]["parametros"]["p1"]["achados"] = [None, "Válido"]
        pdf = relatorio_pi_empresas.gerar_pdf(
            cnpj="11222333000181",
            razao_social="EMPRESA TESTE LTDA",
            hipotese="reabilitacao",
            parecer=parecer,
        )
        assert isinstance(pdf, bytes)
        assert len(pdf) > 1000
