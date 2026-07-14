from __future__ import annotations
import relatorio_sancoes


def _dados_formulario_mock() -> dict:
    return {
        "cnpj":            "12345678000195",
        "numero_contrato": "042/2024",
        "valor_contrato":  200000.0,
        "reincidencia":    "Não",
        "autoridade":      "Secretário Municipal de Obras",
        "orgao":           "Prefeitura de São Paulo",
    }


def _parecer_completo_mock() -> dict:
    return {
        "fatos_apurados": "Empresa deixou de entregar equipamentos no prazo contratado.",
        "condutas_identificadas": ["inexecução parcial do contrato", "atraso injustificado"],
        "enquadramento": {
            "tipo_sancao":   "multa",
            "artigo":        "Art. 156, II, Lei 14.133/2021",
            "justificativa": "Atraso superior a 30 dias sem justificativa.",
        },
        "dosimetria": {
            "percentual_multa":    5.0,
            "valor_multa_estimado": 10000.0,
            "prazo_sancao":        None,
            "nivel_gravidade":     "MÉDIO",
            "agravantes":          ["dano ao erário"],
            "atenuantes":          ["primeira ocorrência"],
        },
        "alerta_criminal": {
            "configura_crime":   False,
            "artigo_178":        None,
            "descricao_conduta": None,
            "recomendacao":      None,
        },
        "base_legal": ["Art. 156, II, Lei 14.133/2021", "Art. 158, Lei 14.133/2021"],
    }


_MINUTA_MOCK = "PORTARIA Nº 001/2024\n\nCONSIDERANDO os fatos apurados...\n\nDecido aplicar multa."


class TestGerarPdf:
    def test_retorna_bytes_nao_vazios(self):
        pdf = relatorio_sancoes.gerar_pdf(
            _dados_formulario_mock(), _parecer_completo_mock(), _MINUTA_MOCK
        )
        assert isinstance(pdf, bytes)
        assert len(pdf) > 1000
        assert pdf[:4] == b"%PDF"

    def test_sem_alerta_criminal_nao_quebra(self):
        parecer = {**_parecer_completo_mock()}
        parecer["alerta_criminal"] = {
            "configura_crime": False,
            "artigo_178": None,
            "descricao_conduta": None,
            "recomendacao": None,
        }
        pdf = relatorio_sancoes.gerar_pdf(
            _dados_formulario_mock(), parecer, _MINUTA_MOCK
        )
        assert isinstance(pdf, bytes)
        assert len(pdf) > 1000

    def test_com_alerta_criminal_nao_quebra(self):
        parecer = {**_parecer_completo_mock()}
        parecer["alerta_criminal"] = {
            "configura_crime":   True,
            "artigo_178":        "Art. 178, III, Lei 14.133/2021",
            "descricao_conduta": "Frustração do caráter competitivo da licitação.",
            "recomendacao":      "Representação ao Ministério Público Federal.",
        }
        pdf = relatorio_sancoes.gerar_pdf(
            _dados_formulario_mock(), parecer, _MINUTA_MOCK
        )
        assert isinstance(pdf, bytes)
        assert len(pdf) > 1000

    def test_minuta_vazia_nao_quebra(self):
        pdf = relatorio_sancoes.gerar_pdf(
            _dados_formulario_mock(), _parecer_completo_mock(), ""
        )
        assert isinstance(pdf, bytes)
        assert len(pdf) > 1000

    def test_todos_tipos_de_sancao_nao_quebram(self):
        for tipo in ("advertencia", "multa", "impedimento", "inidoneidade"):
            parecer = {**_parecer_completo_mock()}
            parecer["enquadramento"] = {**parecer["enquadramento"], "tipo_sancao": tipo}
            if tipo in ("impedimento", "inidoneidade"):
                parecer["dosimetria"] = {**parecer["dosimetria"], "prazo_sancao": 2}
            pdf = relatorio_sancoes.gerar_pdf(
                _dados_formulario_mock(), parecer, _MINUTA_MOCK
            )
            assert isinstance(pdf, bytes)
            assert len(pdf) > 1000

    def test_listas_nulas_nao_quebram(self):
        parecer = {**_parecer_completo_mock()}
        parecer["condutas_identificadas"] = None
        parecer["base_legal"] = None
        parecer["dosimetria"] = {**parecer["dosimetria"], "agravantes": None, "atenuantes": None}
        pdf = relatorio_sancoes.gerar_pdf(
            _dados_formulario_mock(), parecer, _MINUTA_MOCK
        )
        assert isinstance(pdf, bytes)
        assert len(pdf) > 1000

    def test_cnpj_formatado_corretamente(self):
        assert relatorio_sancoes._fmt_cnpj("12345678000195") == "12.345.678/0001-95"

    def test_cnpj_invalido_retorna_original(self):
        assert relatorio_sancoes._fmt_cnpj("abc") == "abc"

    def test_todos_niveis_de_gravidade_nao_quebram(self):
        for nivel in ("LEVE", "MÉDIO", "GRAVE"):
            parecer = {**_parecer_completo_mock()}
            parecer["dosimetria"] = {**parecer["dosimetria"], "nivel_gravidade": nivel}
            pdf = relatorio_sancoes.gerar_pdf(
                _dados_formulario_mock(), parecer, _MINUTA_MOCK
            )
            assert isinstance(pdf, bytes)
            assert len(pdf) > 1000
