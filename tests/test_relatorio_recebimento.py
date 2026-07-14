# tests/test_relatorio_recebimento.py
from __future__ import annotations
import relatorio_recebimento


def _dados_entrega_mock() -> dict:
    return {
        "numero_contrato": "010/2024",
        "objeto": "Serviços de manutenção predial",
        "data_entrega": "30/05/2025",
        "descricao_entrega": "Manutenção preventiva realizada em todos os andares",
        "nao_conformidades": "",
        "valor_contrato": 120000.0,
    }


def _parecer_completo_mock() -> dict:
    return {
        "recebimento_provisorio": {
            "parecer": "APTO",
            "condicoes": [
                {"descricao": "Serviço prestado conforme TR", "status": "ATENDIDA", "observacao": ""},
                {"descricao": "Medição elaborada", "status": "ATENDIDA", "observacao": ""},
            ],
            "pendencias": [],
            "sintese": "Condições de recebimento provisório plenamente atendidas.",
        },
        "recebimento_definitivo": {
            "parecer": "APTO COM RESSALVAS",
            "condicoes": [
                {"descricao": "Qualidade confirmada", "status": "PARCIAL", "observacao": "Revisão pendente"},
            ],
            "pendencias": ["Revisão técnica agendada"],
            "sintese": "Recebimento definitivo condicionado à revisão técnica.",
        },
        "recomendacoes_gerais": ["Agendar revisão técnica em 30 dias"],
        "base_legal": ["Art. 140, I, Lei 14.133/2021", "Art. 140, II, Lei 14.133/2021"],
    }


class TestGerarPdf:
    def test_retorna_bytes_nao_vazios_com_magic_bytes_pdf(self):
        pdf = relatorio_recebimento.gerar_pdf(
            dados_entrega=_dados_entrega_mock(),
            tipo_objeto="servico",
            parecer=_parecer_completo_mock(),
        )
        assert isinstance(pdf, bytes)
        assert len(pdf) > 1000
        assert pdf[:4] == b"%PDF"

    def test_todos_os_pareceres_possiveis_nao_quebram(self):
        for parecer_val in ["APTO", "APTO COM RESSALVAS", "INAPTO"]:
            parecer = _parecer_completo_mock()
            parecer["recebimento_provisorio"]["parecer"] = parecer_val
            parecer["recebimento_definitivo"]["parecer"] = parecer_val
            pdf = relatorio_recebimento.gerar_pdf(
                dados_entrega=_dados_entrega_mock(),
                tipo_objeto="bem",
                parecer=parecer,
            )
            assert isinstance(pdf, bytes)
            assert len(pdf) > 1000

    def test_todos_os_tipos_de_objeto_nao_quebram(self):
        for tipo in ["servico", "bem", "obra"]:
            pdf = relatorio_recebimento.gerar_pdf(
                dados_entrega=_dados_entrega_mock(),
                tipo_objeto=tipo,
                parecer=_parecer_completo_mock(),
            )
            assert isinstance(pdf, bytes)
            assert len(pdf) > 1000

    def test_listas_nulas_nao_quebram(self):
        parecer = _parecer_completo_mock()
        parecer["recebimento_provisorio"]["pendencias"] = None
        parecer["recebimento_definitivo"]["condicoes"] = None
        parecer["recomendacoes_gerais"] = None
        parecer["base_legal"] = None
        pdf = relatorio_recebimento.gerar_pdf(
            dados_entrega=_dados_entrega_mock(),
            tipo_objeto="servico",
            parecer=parecer,
        )
        assert isinstance(pdf, bytes)
        assert len(pdf) > 1000

    def test_condicao_nao_dict_ignorada(self):
        parecer = _parecer_completo_mock()
        parecer["recebimento_provisorio"]["condicoes"] = [
            None,
            {},
            {"descricao": "Condição válida", "status": "ATENDIDA", "observacao": ""},
        ]
        pdf = relatorio_recebimento.gerar_pdf(
            dados_entrega=_dados_entrega_mock(),
            tipo_objeto="servico",
            parecer=parecer,
        )
        assert isinstance(pdf, bytes)
        assert len(pdf) > 1000
