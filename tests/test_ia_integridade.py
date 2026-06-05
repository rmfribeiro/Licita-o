from __future__ import annotations
import pytest
import ia_integridade


def _nao() -> dict:
    return {k: "Não" for k in ia_integridade._CHAVES_QUESTIONARIO}


def _sim() -> dict:
    return {k: "Sim" for k in ia_integridade._CHAVES_QUESTIONARIO}


class TestAplicarPiso:
    def test_all_nao_retorna_inexistente(self):
        assert ia_integridade._aplicar_piso(_nao(), "CONSOLIDADO") == "INEXISTENTE"

    def test_regra1_tem_precedencia_sobre_regra2(self):
        # All-Não deve produzir INEXISTENTE, não INICIAL
        assert ia_integridade._aplicar_piso(_nao(), "CONSOLIDADO") == "INEXISTENTE"

    def test_ato_formal_nao_responsavel_nao_cap_inicial(self):
        r = _sim()
        r["q_ato_formal"] = "Não"
        r["q_responsavel_designado"] = "Não"
        assert ia_integridade._aplicar_piso(r, "CONSOLIDADO") == "INICIAL"

    def test_ato_formal_parcialmente_responsavel_parcialmente_cap_inicial(self):
        r = _sim()
        r["q_ato_formal"] = "Parcialmente"
        r["q_responsavel_designado"] = "Parcialmente"
        assert ia_integridade._aplicar_piso(r, "CONSOLIDADO") == "INICIAL"

    def test_ato_formal_nao_responsavel_parcialmente_cap_inicial(self):
        r = _sim()
        r["q_ato_formal"] = "Não"
        r["q_responsavel_designado"] = "Parcialmente"
        assert ia_integridade._aplicar_piso(r, "CONSOLIDADO") == "INICIAL"

    def test_tudo_sim_aceita_resposta_ia(self):
        assert ia_integridade._aplicar_piso(_sim(), "CONSOLIDADO") == "CONSOLIDADO"

    def test_cap_nao_eleva_maturidade(self):
        # Piso nunca eleva — se IA já retornou INICIAL, fica INICIAL
        r = _sim()
        r["q_ato_formal"] = "Não"
        r["q_responsavel_designado"] = "Não"
        assert ia_integridade._aplicar_piso(r, "INICIAL") == "INICIAL"
