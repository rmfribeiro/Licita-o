from __future__ import annotations
import pytest
import ia_ddi


def _dados_base():
    return {
        "razao_social": "EMPRESA TESTE LTDA",
        "cnpj": "11222333000181",
        "situacao": "ATIVA",
        "ceis": [],
        "cnep": [],
        "pro_etica": False,
        "grande_vulto": False,
        "valor_contrato": 100_000.0,
    }


class TestAplicarPiso:
    def test_sem_ocorrencias_sem_risco(self):
        assert ia_ddi._aplicar_piso(_dados_base()) == "SEM RISCO IDENTIFICADO"

    def test_ceis_ativo_resulta_alto(self):
        dados = {**_dados_base(), "ceis": [{"situacaoAtual": "Ativo"}]}
        assert ia_ddi._aplicar_piso(dados) == "ALTO"

    def test_ceis_inativo_nao_eleva_risco(self):
        dados = {**_dados_base(), "ceis": [{"situacaoAtual": "Inativo"}]}
        assert ia_ddi._aplicar_piso(dados) == "SEM RISCO IDENTIFICADO"

    def test_cnep_ativo_resulta_medio(self):
        dados = {**_dados_base(), "cnep": [{"situacaoAtual": "Ativo"}]}
        assert ia_ddi._aplicar_piso(dados) == "MÉDIO"

    def test_situacao_suspensa_resulta_medio(self):
        dados = {**_dados_base(), "situacao": "SUSPENSA"}
        assert ia_ddi._aplicar_piso(dados) == "MÉDIO"

    def test_situacao_baixada_resulta_medio(self):
        dados = {**_dados_base(), "situacao": "BAIXADA"}
        assert ia_ddi._aplicar_piso(dados) == "MÉDIO"

    def test_ceis_prevalece_sobre_cnep(self):
        dados = {
            **_dados_base(),
            "ceis": [{"situacaoAtual": "Ativo"}],
            "cnep": [{"situacaoAtual": "Ativo"}],
        }
        assert ia_ddi._aplicar_piso(dados) == "ALTO"

    def test_grande_vulto_sem_pi_resulta_medio(self):
        dados = {**_dados_base(), "grande_vulto": True, "pro_etica": False}
        fid = {"q1": "Não", "q2": "Não", "q3": "Não", "q4": "Não", "q5": "Não"}
        assert ia_ddi._aplicar_piso(dados, fid) == "MÉDIO"

    def test_grande_vulto_com_pro_etica_nao_eleva(self):
        dados = {**_dados_base(), "grande_vulto": True, "pro_etica": True}
        fid = {"q1": "Sim", "q2": "Sim", "q3": "Sim", "q4": "Sim", "q5": "Sim"}
        assert ia_ddi._aplicar_piso(dados, fid) == "SEM RISCO IDENTIFICADO"

    def test_grande_vulto_com_fid_positivo_nao_eleva(self):
        dados = {**_dados_base(), "grande_vulto": True, "pro_etica": False}
        fid = {"q1": "Sim", "q2": "Sim", "q3": "Sim", "q4": "Não", "q5": "Não"}
        assert ia_ddi._aplicar_piso(dados, fid) == "SEM RISCO IDENTIFICADO"
