from __future__ import annotations
import pytest
import ia_pi_empresas


class TestNivelMaturidade:
    def test_score_0_retorna_inexistente(self):
        assert ia_pi_empresas.nivel_maturidade(0) == "INEXISTENTE"

    def test_score_24_retorna_inexistente(self):
        assert ia_pi_empresas.nivel_maturidade(24) == "INEXISTENTE"

    def test_score_25_retorna_inicial(self):
        assert ia_pi_empresas.nivel_maturidade(25) == "INICIAL"

    def test_score_49_retorna_inicial(self):
        assert ia_pi_empresas.nivel_maturidade(49) == "INICIAL"

    def test_score_50_retorna_em_desenvolvimento(self):
        assert ia_pi_empresas.nivel_maturidade(50) == "EM DESENVOLVIMENTO"

    def test_score_74_retorna_em_desenvolvimento(self):
        assert ia_pi_empresas.nivel_maturidade(74) == "EM DESENVOLVIMENTO"

    def test_score_75_retorna_consolidado(self):
        assert ia_pi_empresas.nivel_maturidade(75) == "CONSOLIDADO"

    def test_score_100_retorna_consolidado(self):
        assert ia_pi_empresas.nivel_maturidade(100) == "CONSOLIDADO"


def _respostas_todos_implementados() -> dict:
    return {p: "Implementado" for p in ia_pi_empresas.QUESTOES_PI}


def _respostas_todos_nao_existem() -> dict:
    return {p: "Não existe" for p in ia_pi_empresas.QUESTOES_PI}


def _respostas_todos_parcialmente() -> dict:
    return {p: "Parcialmente" for p in ia_pi_empresas.QUESTOES_PI}


class TestCalcularScores:
    def test_todos_implementados_score_geral_100(self):
        r = _respostas_todos_implementados()
        s = ia_pi_empresas.calcular_scores(r)
        assert s["geral"] == 100.0

    def test_todos_nao_existem_score_geral_0(self):
        r = _respostas_todos_nao_existem()
        s = ia_pi_empresas.calcular_scores(r)
        assert s["geral"] == 0.0

    def test_todos_parcialmente_score_geral_50(self):
        r = _respostas_todos_parcialmente()
        s = ia_pi_empresas.calcular_scores(r)
        assert s["geral"] == 50.0

    def test_retorna_por_parametro_com_17_chaves(self):
        r = _respostas_todos_implementados()
        s = ia_pi_empresas.calcular_scores(r)
        assert len(s["por_parametro"]) == 17

    def test_retorna_por_dimensao_com_5_chaves(self):
        r = _respostas_todos_implementados()
        s = ia_pi_empresas.calcular_scores(r)
        assert len(s["por_dimensao"]) == 5

    def test_nivel_derivado_do_score(self):
        r = _respostas_todos_implementados()
        s = ia_pi_empresas.calcular_scores(r)
        assert s["nivel"] == "CONSOLIDADO"

    def test_resposta_ausente_conta_como_nao_existe(self):
        r = {}  # nenhuma resposta
        s = ia_pi_empresas.calcular_scores(r)
        assert s["geral"] == 0.0

    def test_score_por_dimensao_media_simples_dos_parametros(self):
        # Comprometimento (p1, p2, p3): p1=100, p2=0, p3=0 → media=33.3
        r = _respostas_todos_nao_existem()
        r["p1"] = "Implementado"
        s = ia_pi_empresas.calcular_scores(r)
        assert abs(s["por_dimensao"]["comprometimento_alta_direcao"] - (100 / 3)) < 0.1

    def test_pesos_somam_1(self):
        total = sum(ia_pi_empresas.PESOS_DIMENSAO.values())
        assert abs(total - 1.0) < 1e-9
