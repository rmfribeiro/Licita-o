# -*- coding: utf-8 -*-
"""
Integration tests: ia_* → relatorio_* full pipeline.

For each module:
  1. Mock the HTTP layer only (ia_utils.urllib.request.urlopen).
  2. Call the ia_* analysis function — normalisation and business logic run for real.
  3. Feed the returned dict into the corresponding relatorio_* PDF generator.
  4. Assert the output is a valid PDF (starts with b'%PDF', len > 1000).

This validates that the dict schema produced by each ia_* module remains
compatible with its relatorio_* counterpart without requiring real API calls.
"""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest

import ia_contratos
import ia_ddi
import ia_etp
import ia_fid
import ia_integridade
import ia_pesquisa_mercado
import ia_pi_empresas
import ia_reabilitacao
import ia_recebimento
import ia_sancoes
import ia_tr
import relatorio_contratos
import relatorio_ddi
import relatorio_etp
import relatorio_fid
import relatorio_integridade
import relatorio_pesquisa_mercado
import relatorio_pi_empresas
import relatorio_reabilitacao
import relatorio_recebimento
import relatorio_sancoes
import relatorio_tr

_KEY = "test-dummy-key"


def _mock_urlopen(payload: dict):
    """Context-manager mock returning *payload* as the Anthropic API response."""
    data = json.dumps({"content": [{"text": json.dumps(payload)}]}).encode("utf-8")
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=data)))
    cm.__exit__ = MagicMock(return_value=False)
    return cm


def _assert_valid_pdf(pdf: bytes) -> None:
    assert isinstance(pdf, bytes), "gerar_pdf deve retornar bytes"
    assert pdf[:4] == b"%PDF", "bytes devem iniciar com assinatura PDF"
    assert len(pdf) > 1000, "PDF muito pequeno — possível geração incompleta"


# ---------------------------------------------------------------------------
# DDI — Due Diligence de Integridade
# ---------------------------------------------------------------------------

class TestDDIPipeline:
    _DADOS = {
        "razao_social": "Empresa Teste LTDA",
        "cnpj": "12345678000195",
        "cnaes": ["6201-5/01"],
        "valor_contrato": 500_000.0,
        "grande_vulto": False,
    }
    _FID = {"q1": "Sim", "q2": "Sim", "q3": "Não", "q4": "Não", "q5": "Não"}
    _PARECER_API = {
        "risco_geral": "MÉDIO",
        "dimensoes": {
            "situacao_cadastral": {"status": "ok", "descricao": "Regular"},
            "sancoes": {"status": "ok", "achados": []},
            "programa_integridade": {
                "status": "alerta", "obrigatorio": True,
                "pro_etica": False, "descricao": "Sem programa formal",
            },
            "fid": {"status": "ok", "inconsistencias": [], "descricao": "Coerente"},
            "contexto_contrato": {
                "status": "ok", "grande_vulto": False, "descricao": "Padrão",
            },
        },
        "resumo": "Risco médio identificado.",
        "recomendacao": "Exigir evidências do programa de integridade.",
        "base_legal": ["Portaria SEGES/ME 8.678/2021, art. 2 III"],
        "validade_fid": "12 meses",
    }

    def test_pipeline_retorna_pdf_valido(self):
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(self._PARECER_API)):
            parecer = ia_ddi.analisar(self._DADOS, self._FID)
        pdf = relatorio_ddi.gerar_pdf(
            cnpj="12345678000195",
            valor_contrato=500_000.0,
            dados=self._DADOS,
            fid=self._FID,
            parecer=parecer,
        )
        _assert_valid_pdf(pdf)

    def test_risco_alto_chega_ao_relatorio(self):
        parecer_api = {**self._PARECER_API, "risco_geral": "ALTO"}
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(parecer_api)):
            parecer = ia_ddi.analisar(self._DADOS, self._FID)
        assert parecer["risco_geral"] == "ALTO"
        pdf = relatorio_ddi.gerar_pdf("12345678000195", 500_000.0, self._DADOS, self._FID, parecer)
        _assert_valid_pdf(pdf)

    def test_risco_desconhecido_normalizado_para_sem_risco(self):
        parecer_api = {**self._PARECER_API, "risco_geral": "INEXISTENTE"}
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(parecer_api)):
            parecer = ia_ddi.analisar(self._DADOS, self._FID)
        assert parecer["risco_geral"] == "SEM RISCO IDENTIFICADO"
        pdf = relatorio_ddi.gerar_pdf("12345678000195", None, self._DADOS, self._FID, parecer)
        _assert_valid_pdf(pdf)


# ---------------------------------------------------------------------------
# ETP — Estudo Técnico Preliminar
# ---------------------------------------------------------------------------

class TestETPPipeline:
    _PARECER_API = {
        "adequacao_geral": "ADEQUADO COM RESSALVAS",
        "dimensoes": {
            "descricao_necessidade":       {"status": "ok",     "descricao": "Bem descrita"},
            "alinhamento_estrategico":     {"status": "ok",     "descricao": "Alinhado"},
            "requisitos_contratacao":      {"status": "alerta", "descricao": "Incompleto"},
            "levantamento_mercado":        {"status": "ok",     "descricao": "Suficiente"},
            "estimativa_quantidade_valor": {"status": "ok",     "descricao": "Razoável"},
            "sustentabilidade":            {"status": "alerta", "descricao": "Ausente"},
            "parcelamento":                {"status": "ok",     "descricao": "Justificado"},
            "posicionamento_conclusivo":   {"status": "alerta", "descricao": "Aprovado com ressalvas"},
        },
        "pontos_criticos": ["Requisitos técnicos incompletos", "Sustentabilidade ausente"],
        "recomendacoes": ["Detalhar requisitos técnicos"],
        "base_legal": ["IN SEGES/MGI 58/2022", "Lei 14.133/2021, art. 18, I"],
    }

    def test_pipeline_retorna_pdf_valido(self):
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(self._PARECER_API)):
            parecer = ia_etp.analisar_etp("Texto ETP de exemplo.", _KEY)
        pdf = relatorio_etp.gerar_pdf(
            nomes_arquivos=["etp_integracao.pdf"],
            avisos=[],
            parecer=parecer,
        )
        _assert_valid_pdf(pdf)

    def test_adequacao_inadequado_no_relatorio(self):
        parecer_api = {**self._PARECER_API, "adequacao_geral": "INADEQUADO"}
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(parecer_api)):
            parecer = ia_etp.analisar_etp("ETP incompleto.", _KEY)
        assert parecer["adequacao_geral"] == "INADEQUADO"
        pdf = relatorio_etp.gerar_pdf(["etp.pdf"], ["Aviso de incompletude"], parecer)
        _assert_valid_pdf(pdf)


# ---------------------------------------------------------------------------
# TR — Termo de Referência
# ---------------------------------------------------------------------------

class TestTRPipeline:
    _PARECER_API = {
        "adequacao_geral": "ADEQUADO",
        "dimensoes": {
            "objeto":            {"status": "ok", "descricao": "Claro e preciso"},
            "descricao_solucao": {"status": "ok", "descricao": "Detalhada"},
            "requisitos":        {"status": "ok", "descricao": "Completos"},
        },
        "pontos_criticos": [],
        "recomendacoes": ["Manter atualização periódica"],
        "base_legal": ["Lei 14.133/2021, art. 6, XXIII"],
    }

    @pytest.mark.parametrize("tipo", ["servico", "bem", "tic"])
    def test_pipeline_todos_os_tipos(self, tipo):
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(self._PARECER_API)):
            parecer = ia_tr.analisar_tr("Texto TR de exemplo.", tipo, _KEY)
        pdf = relatorio_tr.gerar_pdf(
            nome_objeto="Objeto de teste",
            tipo_objeto=tipo,
            parecer=parecer,
        )
        _assert_valid_pdf(pdf)


# ---------------------------------------------------------------------------
# Integridade — PIP Municipal
# ---------------------------------------------------------------------------

class TestIntegridadePipeline:
    _RESPOSTAS = {k: "Sim" for k, _ in ia_integridade.QUESTOES_PIP}
    _PARECER_API = {
        "maturidade_geral": "CONSOLIDADO",
        "dimensoes": {
            "compromisso_alta_gestao": {
                "nivel": "CONSOLIDADO",
                "achados": ["Alta gestão comprometida"],
                "recomendacoes": [],
            },
            "diretrizes_integridade": {
                "nivel": "CONSOLIDADO",
                "achados": ["Publicadas e divulgadas"],
                "recomendacoes": [],
            },
            "base_legal_normativa": {"nivel": "CONSOLIDADO", "achados": [], "recomendacoes": []},
            "responsabilizacao":    {"nivel": "CONSOLIDADO", "achados": [], "recomendacoes": []},
            "metodologia_gestao":   {
                "nivel": "EM DESENVOLVIMENTO",
                "achados": ["Indicadores parciais"],
                "recomendacoes": ["Formalizar indicadores"],
            },
            "tres_linhas_defesa": {
                "nivel": "INICIAL",
                "achados": ["Auditoria interna incipiente"],
                "recomendacoes": ["Estruturar auditoria interna"],
            },
        },
        "prioridades": ["Estruturar auditoria interna"],
        "resumo_executivo": "Programa em estágio consolidado com oportunidade de melhoria.",
        "base_legal": ["Decreto 11.129/2022", "IN CGU 21/2021"],
    }

    def test_pipeline_retorna_pdf_valido(self):
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(self._PARECER_API)):
            parecer = ia_integridade.diagnosticar(self._RESPOSTAS, None, _KEY)
        pdf = relatorio_integridade.gerar_pdf("Município Teste", parecer)
        _assert_valid_pdf(pdf)

    def test_piso_todos_nao_clampa_para_inexistente(self):
        respostas_nao = {k: "Não" for k, _ in ia_integridade.QUESTOES_PIP}
        parecer_api = {**self._PARECER_API, "maturidade_geral": "CONSOLIDADO"}
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(parecer_api)):
            parecer = ia_integridade.diagnosticar(respostas_nao, None, _KEY)
        assert parecer["maturidade_geral"] == "INEXISTENTE"
        pdf = relatorio_integridade.gerar_pdf("Município X", parecer)
        _assert_valid_pdf(pdf)


# ---------------------------------------------------------------------------
# PI Empresas — Programa de Integridade de Empresas
# ---------------------------------------------------------------------------

class TestPIEmpresasPipeline:
    _RESPOSTAS = {
        p: 100
        for _, (_, params) in ia_pi_empresas.DIMENSOES_PI.items()
        for p in params
    }
    _HIPOTESE = list(ia_pi_empresas.HIPOTESES_POR_TIPO["empresa_privada"].keys())[0]
    _PARECER_API = {
        "dimensoes": {
            "comprometimento_alta_direcao": {
                "sintese": "Alta direção comprometida.",
                "parametros": {
                    "p1": {"achados": [], "recomendacoes": []},
                    "p2": {"achados": [], "recomendacoes": []},
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
                "sintese": "Controles robustos.",
                "parametros": {
                    f"p{i}": {"achados": [], "recomendacoes": []} for i in range(6, 13)
                },
            },
            "monitoramento_melhoria": {
                "sintese": "Monitoramento ativo.",
                "parametros": {
                    "p13": {"achados": [], "recomendacoes": []},
                    "p14": {"achados": [], "recomendacoes": []},
                    "p15": {"achados": [], "recomendacoes": []},
                },
            },
            "transparencia": {
                "sintese": "Transparente.",
                "parametros": {
                    "p16": {"achados": [], "recomendacoes": []},
                    "p17": {"achados": [], "recomendacoes": []},
                },
            },
        },
        "pontos_criticos": [],
        "conclusao_hipotese": "Empresa elegível para contratação.",
        "recomendacoes": ["Manter atualização anual"],
        "base_legal": ["Decreto 12.304/2024, Art. 4º"],
    }

    def test_pipeline_retorna_pdf_valido(self):
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(self._PARECER_API)):
            parecer = ia_pi_empresas.avaliar(
                self._RESPOSTAS, self._HIPOTESE, None, _KEY, tipo_entidade="empresa_privada"
            )
        pdf = relatorio_pi_empresas.gerar_pdf(
            cnpj="12345678000195",
            razao_social="Empresa Teste LTDA",
            hipotese=self._HIPOTESE,
            parecer=parecer,
            tipo_entidade="empresa_privada",
        )
        _assert_valid_pdf(pdf)

    @pytest.mark.parametrize("tipo", list(ia_pi_empresas.TIPOS_ENTIDADE.keys()))
    def test_pipeline_todos_os_tipos_entidade(self, tipo):
        hipotese = list(ia_pi_empresas.HIPOTESES_POR_TIPO[tipo].keys())[0]
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(self._PARECER_API)):
            parecer = ia_pi_empresas.avaliar(
                self._RESPOSTAS, hipotese, None, _KEY, tipo_entidade=tipo
            )
        pdf = relatorio_pi_empresas.gerar_pdf(
            cnpj="12345678000195",
            razao_social="Entidade Teste",
            hipotese=hipotese,
            parecer=parecer,
            tipo_entidade=tipo,
        )
        _assert_valid_pdf(pdf)


# ---------------------------------------------------------------------------
# Contratos — Alterações Contratuais
# ---------------------------------------------------------------------------

class TestContratosPipeline:
    _DADOS = {
        "numero_contrato": "CT-042/2024",
        "objeto": "Contratação de serviços de suporte técnico",
        "data_assinatura": "2024-01-15",
        "valor_atual": 200_000.0,
    }
    _PARECER_API = {
        "parecer": "DEFERÍVEL COM RESSALVAS",
        "tipo_alteracao": "reequilibrio",
        "requisitos": [
            {"descricao": "Fato superveniente imprevisível", "status": "ATENDIDO", "observacao": ""},
            {"descricao": "Comprovação documental", "status": "PARCIAL", "observacao": "Faltam notas fiscais"},
        ],
        "lacunas_documentais": ["Notas fiscais do período base ausentes"],
        "fundamentos_legais": ["Art. 124, II, 'd', Lei 14.133/2021"],
        "recomendacoes": ["Exigir complementação documental"],
        "sintese": "Pedido deferível com ressalvas pendentes de regularização.",
    }

    @pytest.mark.parametrize("tipo", list(ia_contratos.TIPOS_ALTERACAO.keys()))
    def test_pipeline_todos_os_tipos(self, tipo):
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(self._PARECER_API)):
            parecer = ia_contratos.analisar(tipo, self._DADOS, None, _KEY)
        pdf = relatorio_contratos.gerar_pdf(
            dados_contrato=self._DADOS,
            tipo=tipo,
            parecer=parecer,
        )
        _assert_valid_pdf(pdf)


# ---------------------------------------------------------------------------
# TR — Recebimento Contratual
# ---------------------------------------------------------------------------

class TestRecebimentoPipeline:
    _DADOS_ENTREGA = {
        "objeto": "Contratação de serviços de suporte técnico",
        "numero_contrato": "CT-042/2024",
        "fornecedor": "Empresa Prestadora S/A",
        "data_entrega": "2024-11-30",
    }
    _PARECER_API = {
        "tipo_objeto": "servico",
        "recebimento_provisorio": {
            "parecer": "APTO COM RESSALVAS",
            "condicoes": [
                {"descricao": "Prazo atendido", "status": "ATENDIDA", "observacao": ""},
                {"descricao": "Escopo completo", "status": "PARCIAL", "observacao": "3 itens pendentes"},
            ],
            "pendencias": ["Itens 4, 7 e 9 não entregues"],
            "sintese": "Recebimento provisório com ressalvas.",
        },
        "recebimento_definitivo": {
            "parecer": "INAPTO",
            "condicoes": [
                {"descricao": "Testes realizados", "status": "AUSENTE", "observacao": "Sem relatório"},
            ],
            "pendencias": ["Relatório de testes ausente"],
            "sintese": "Definitivo inapto até regularização.",
        },
        "recomendacoes_finais": ["Exigir complementação em 10 dias"],
        "base_legal": ["Lei 14.133/2021, art. 140"],
    }

    @pytest.mark.parametrize("tipo", list(ia_recebimento.TIPOS_OBJETO.keys()))
    def test_pipeline_todos_os_tipos(self, tipo):
        parecer_api = {**self._PARECER_API, "tipo_objeto": tipo}
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(parecer_api)):
            parecer = ia_recebimento.analisar(tipo, self._DADOS_ENTREGA, None, _KEY)
        pdf = relatorio_recebimento.gerar_pdf(self._DADOS_ENTREGA, tipo, parecer)
        _assert_valid_pdf(pdf)


# ---------------------------------------------------------------------------
# Sanções — Dosimetria de Sanção Administrativa
# ---------------------------------------------------------------------------

class TestSancoesPipeline:
    _DADOS_FORMULARIO = {
        "cnpj": "11223344000155",
        "numero_contrato": "CT-099/2024",
        "valor_contrato": 200_000.0,
        "reincidencia": "Não verificado",
        "autoridade": "Diretor de Contratos",
        "orgao": "Secretaria de Administração",
    }
    _PARECER_API = {
        "fatos_apurados": "Inexecução parcial do contrato.",
        "condutas_identificadas": ["Atraso na entrega"],
        "enquadramento": {
            "tipo_sancao": "multa",
            "artigo": "Art. 156, II, Lei 14.133/2021",
            "justificativa": "Atraso injustificado configura inexecução parcial.",
        },
        "dosimetria": {
            "percentual_multa": 10.0,
            "valor_multa_estimado": 20_000.0,
            "prazo_sancao": None,
            "nivel_gravidade": "MÉDIO",
            "agravantes": [],
            "atenuantes": ["Primeira ocorrência"],
        },
        "alerta_criminal": {
            "configura_crime": False,
            "artigo_178": None,
            "descricao_conduta": None,
            "recomendacao": None,
        },
        "base_legal": ["Art. 156, II, Lei 14.133/2021", "Art. 158, §1º, Lei 14.133/2021"],
    }
    _MINUTA_API = {"minuta": "PORTARIA Nº 001/2024\n\nO DIRETOR resolve: Aplicar multa de 10% ao fornecedor."}

    def test_pipeline_dosimetria_para_pdf(self):
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(self._PARECER_API)):
            parecer = ia_sancoes.analisar_dosimetria(self._DADOS_FORMULARIO, None, _KEY)
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(self._MINUTA_API)):
            minuta = ia_sancoes.gerar_minuta(parecer, self._DADOS_FORMULARIO, _KEY)
        assert isinstance(minuta, str) and len(minuta) > 0
        pdf = relatorio_sancoes.gerar_pdf(self._DADOS_FORMULARIO, parecer, minuta)
        _assert_valid_pdf(pdf)

    def test_pdf_sem_minuta_nao_quebra(self):
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(self._PARECER_API)):
            parecer = ia_sancoes.analisar_dosimetria(self._DADOS_FORMULARIO, None, _KEY)
        pdf = relatorio_sancoes.gerar_pdf(self._DADOS_FORMULARIO, parecer, "")
        _assert_valid_pdf(pdf)


# ---------------------------------------------------------------------------
# Reabilitação — Reabilitação de Fornecedor
# ---------------------------------------------------------------------------

class TestReabilitacaoPipeline:
    _DADOS_EMPRESA = {
        "razao_social": "Fornecedor Suspenso LTDA",
        "cnpj": "98765432000111",
    }
    _DADOS_SANCAO = {
        "data_aplicacao": "2022-01-15",
        "prazo_anos": 3,
        "valor_multa": 50_000.0,
    }
    _RESPOSTAS = {
        "reparacao_dano": "Sim",
        "cessacao_atos": "Sim",
        "adocao_medidas": "Parcialmente",
        "regularizacao_trabalhista": "Sim",
    }
    _PARECER_API = {
        "parecer": "ELEGÍVEL COM RESSALVAS",
        "condicoes_avaliadas": [
            {
                "numero": "I",
                "descricao": "Reparação integral do dano",
                "status": "ATENDIDA",
                "observacao": "Confirmada documentalmente.",
            }
        ],
        "sintese": "Empresa elegível com ressalvas quanto ao item III.",
        "base_legal": ["Art. 163, Par. Único, Lei 14.133/2021"],
    }

    @pytest.mark.parametrize("tipo", list(ia_reabilitacao.TIPOS_SANCAO.keys()))
    def test_pipeline_relatorio_tecnico_pdf_valido(self, tipo):
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(self._PARECER_API)):
            parecer = ia_reabilitacao.analisar(
                tipo, self._DADOS_EMPRESA, self._DADOS_SANCAO, self._RESPOSTAS, None, _KEY
            )
        pdf = relatorio_reabilitacao.gerar_relatorio_tecnico(
            "98765432000111", self._DADOS_EMPRESA, self._DADOS_SANCAO, parecer
        )
        _assert_valid_pdf(pdf)

    @pytest.mark.parametrize("tipo", list(ia_reabilitacao.TIPOS_SANCAO.keys()))
    def test_pipeline_minuta_requerimento_pdf_valido(self, tipo):
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(self._PARECER_API)):
            parecer = ia_reabilitacao.analisar(
                tipo, self._DADOS_EMPRESA, self._DADOS_SANCAO, self._RESPOSTAS, None, _KEY
            )
        pdf = relatorio_reabilitacao.gerar_minuta_requerimento(
            "98765432000111", self._DADOS_EMPRESA, self._DADOS_SANCAO, parecer
        )
        _assert_valid_pdf(pdf)


# ---------------------------------------------------------------------------
# Pesquisa de Mercado
# ---------------------------------------------------------------------------

class TestPesquisaMercadoPipeline:
    _ITENS_TR = [
        {"id": 1, "descricao": "Consultoria de TI", "unidade": "hora", "quantidade_estimada": 100},
        {"id": 2, "descricao": "Licença de software", "unidade": "un", "quantidade_estimada": 5},
    ]
    _COTACOES_API = {
        "fornecedores": [
            {"nome": "Empresa Alpha Ltda", "cnpj": "11111111000111"},
            {"nome": "Empresa Beta S/A", "cnpj": "22222222000122"},
        ],
        "itens_cotados": [
            {
                "item_id": 1,
                "descricao_no_orcamento": "Consultoria de TI",
                "cotacoes": [
                    {"fornecedor": "Empresa Alpha Ltda", "preco_unitario": 120.0},
                    {"fornecedor": "Empresa Beta S/A", "preco_unitario": 130.0},
                ],
            },
            {
                "item_id": 2,
                "descricao_no_orcamento": "Licença de software",
                "cotacoes": [
                    {"fornecedor": "Empresa Alpha Ltda", "preco_unitario": 5000.0},
                    {"fornecedor": "Empresa Beta S/A", "preco_unitario": 4800.0},
                ],
            },
        ],
    }
    _PARECER_API = {
        "parecer_narrativo": "Pesquisa válida com cotações suficientes para todos os itens.",
    }

    def test_pipeline_relatorio_pesquisa_pdf_valido(self):
        with patch(
            "ia_utils.urllib.request.urlopen",
            side_effect=[_mock_urlopen(self._COTACOES_API), _mock_urlopen(self._PARECER_API)],
        ):
            resultado = ia_pesquisa_mercado.analisar(
                self._ITENS_TR, "Orçamentos fornecidos pelas empresas.", _KEY
            )
        pdf = relatorio_pesquisa_mercado.gerar_relatorio_pesquisa(
            objeto="Contratação de TI",
            itens_avaliados=resultado["itens_avaliados"],
            fornecedores=resultado["fornecedores"],
            parecer_narrativo=resultado["parecer_narrativo"],
            status_geral=resultado["status_geral"],
            valor_total_estimado=resultado["valor_total_estimado"],
        )
        _assert_valid_pdf(pdf)

    def test_pipeline_mapa_precos_pdf_valido(self):
        with patch(
            "ia_utils.urllib.request.urlopen",
            side_effect=[_mock_urlopen(self._COTACOES_API), _mock_urlopen(self._PARECER_API)],
        ):
            resultado = ia_pesquisa_mercado.analisar(
                self._ITENS_TR, "Orçamentos fornecidos.", _KEY
            )
        pdf = relatorio_pesquisa_mercado.gerar_mapa_precos(
            objeto="Contratação de TI",
            itens_avaliados=resultado["itens_avaliados"],
            fornecedores=resultado["fornecedores"],
            valor_total_estimado=resultado["valor_total_estimado"],
        )
        _assert_valid_pdf(pdf)

    def test_sem_itens_tr_retorna_pdf_valido_sem_api_call(self):
        resultado = ia_pesquisa_mercado.analisar([], "sem orçamentos", _KEY)
        assert resultado["status_geral"] == ia_pesquisa_mercado.STATUS_PESQUISA["INVÁLIDA"]
        pdf = relatorio_pesquisa_mercado.gerar_relatorio_pesquisa(
            objeto="Sem itens",
            itens_avaliados=[],
            fornecedores=[],
            parecer_narrativo=resultado["parecer_narrativo"],
            status_geral=resultado["status_geral"],
            valor_total_estimado=None,
        )
        _assert_valid_pdf(pdf)


# ---------------------------------------------------------------------------
# FID — Instituto da Diligência
# ---------------------------------------------------------------------------

class TestFIDPipeline:
    _DADOS_LICITANTE = {
        "cnpj": "12345678000195",
        "razao_social": "Empresa XPTO Ltda",
        "numero_edital": "PE 042/2024",
        "objeto": "Contratação de serviços de TI",
        "orgao": "Ministério da Educação",
    }
    _PARECER_API = {
        "necessita_diligencia": "SIM",
        "documentos_solicitados": [
            {
                "documento": "Certidão FGTS",
                "situacao": "vencida",
                "fundamento_legal": "Art. 62, III, Lei 14.133/2021",
                "prazo_dias": 5,
            }
        ],
        "pontos_de_atencao": ["Certidão FGTS vencida há 15 dias."],
        "minuta_oficio": (
            "OFÍCIO DE DILIGÊNCIA Nº ___\n\n"
            "Assunto: Complementação documental.\n\n"
            "Senhor(a) Representante,\n\n"
            "Solicitamos a complementação dos documentos indicados."
        ),
        "prazo_resposta_sugerido": 5,
        "conclusao": "Diligência necessária para regularização do FGTS.",
        "base_legal": ["Art. 59, §2º, Lei 14.133/2021"],
    }

    @pytest.mark.parametrize("fase", list(ia_fid.FASES_PROCESSO.keys()))
    def test_pipeline_todas_as_fases_pdf_valido(self, fase):
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(self._PARECER_API)):
            parecer = ia_fid.analisar(
                fase, self._DADOS_LICITANTE, "FGTS vencido", None, _KEY
            )
        pdf = relatorio_fid.gerar_pdf(self._DADOS_LICITANTE, fase, parecer)
        _assert_valid_pdf(pdf)

    def test_pipeline_diligencia_nao_pdf_valido(self):
        parecer_nao = {
            **self._PARECER_API,
            "necessita_diligencia": "NÃO",
            "documentos_solicitados": [],
            "pontos_de_atencao": [],
        }
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(parecer_nao)):
            parecer = ia_fid.analisar(
                "habilitacao", self._DADOS_LICITANTE, "Documentação completa.", None, _KEY
            )
        assert parecer["necessita_diligencia"] == "NÃO"
        pdf = relatorio_fid.gerar_pdf(self._DADOS_LICITANTE, "habilitacao", parecer)
        _assert_valid_pdf(pdf)
