from __future__ import annotations
import relatorio_contratos


def _dados_contrato_mock() -> dict:
    return {
        "numero_contrato": "001/2024",
        "objeto": "Prestação de serviços de limpeza predial",
        "data_assinatura": "15/01/2024",
        "valor_atual": 500000.0,
    }


def _parecer_completo_mock() -> dict:
    return {
        "parecer": "DEFERÍVEL COM RESSALVAS",
        "tipo_alteracao": "reajuste",
        "dados_contrato": _dados_contrato_mock(),
        "requisitos": [
            {
                "descricao": "Cláusula de reajuste expressa no contrato",
                "status": "ATENDIDO",
                "observacao": "Cláusula 12ª prevê IPCA anual",
            },
            {
                "descricao": "Intervalo mínimo de 12 meses",
                "status": "PARCIAL",
                "observacao": "Apenas 11 meses decorridos",
            },
            {
                "descricao": "Memória de cálculo apresentada",
                "status": "AUSENTE",
                "observacao": "",
            },
        ],
        "lacunas_documentais": ["Planilha de cálculo IPCA não anexada"],
        "fundamentos_legais": ["Art. 25 §8º, Lei 14.133/2021"],
        "recomendacoes": ["Aguardar 1 mês para completar a data-base"],
        "sintese": "O pedido atende parcialmente os requisitos legais.",
    }


class TestGerarPdf:
    def test_retorna_bytes_nao_vazios(self):
        pdf = relatorio_contratos.gerar_pdf(
            dados_contrato=_dados_contrato_mock(),
            tipo="reajuste",
            parecer=_parecer_completo_mock(),
        )
        assert isinstance(pdf, bytes)
        assert len(pdf) > 1000
        assert pdf[:4] == b"%PDF"

    def test_todos_os_tipos_de_parecer_nao_quebram(self):
        for tipo_parecer in [
            "DEFERÍVEL",
            "DEFERÍVEL COM RESSALVAS",
            "INDEFERÍVEL",
        ]:
            parecer = _parecer_completo_mock()
            parecer["parecer"] = tipo_parecer
            pdf = relatorio_contratos.gerar_pdf(
                dados_contrato=_dados_contrato_mock(),
                tipo="repactuacao",
                parecer=parecer,
            )
            assert isinstance(pdf, bytes)
            assert len(pdf) > 1000

    def test_requisitos_vazios_nao_quebra(self):
        parecer = _parecer_completo_mock()
        parecer["requisitos"] = []
        pdf = relatorio_contratos.gerar_pdf(
            dados_contrato=_dados_contrato_mock(),
            tipo="reequilibrio",
            parecer=parecer,
        )
        assert isinstance(pdf, bytes)
        assert len(pdf) > 1000

    def test_listas_nulas_nao_quebram(self):
        parecer = _parecer_completo_mock()
        parecer["lacunas_documentais"] = None
        parecer["recomendacoes"] = None
        parecer["fundamentos_legais"] = None
        pdf = relatorio_contratos.gerar_pdf(
            dados_contrato=_dados_contrato_mock(),
            tipo="reajuste",
            parecer=parecer,
        )
        assert isinstance(pdf, bytes)
        assert len(pdf) > 1000
