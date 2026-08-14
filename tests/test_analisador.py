from __future__ import annotations
import analisador


class TestSeparacaoCamadaIA:
    """Decisao de 14/08/2026 (opcao A): os achados livres da IA saem das
    contagens e da tabela principal e vao para um bloco proprio no fim.

    O teste que importa: duas leituras do MESMO edital em que a IA discorda de
    si mesma (status diferente, severidade diferente, um achado a mais) tem de
    produzir a parte deterministica do relatorio IDENTICA.
    """

    @staticmethod
    def _regra(id_, status="ok", sev="media"):
        return {"id": id_, "item": f"Requisito {id_}", "categoria": "Cat", "status": status,
                "severidade": sev, "detalhe": "d", "trecho": "", "fonte": "Automatico",
                "fundamento": "", "base_legal": "art. 1"}

    @staticmethod
    def _ia(id_, status="alerta", sev="media", detalhe="x"):
        return {"id": id_, "item": f"Achado {id_}", "categoria": "Analise semantica",
                "status": status, "severidade": sev, "detalhe": detalhe, "trecho": "",
                "fonte": "IA (semantica)", "fundamento": "", "base_legal": "art. 1"}

    def test_separar_camadas_usa_a_fonte(self):
        ap = [self._regra("R01"), self._ia("EXTRA-1")]
        regras, ia = analisador.separar_camadas(ap)
        assert [a["id"] for a in regras] == ["R01"]
        assert [a["id"] for a in ia] == ["EXTRA-1"]

    def test_parte_deterministica_identica_mesmo_com_ia_divergente(self):
        base = [self._regra("R01", "inconformidade", "alta"), self._regra("R02", "alerta"),
                self._regra("R03", "ok")]
        rod1 = base + [self._ia("EXTRA-1", "alerta", "media", "redacao A")]
        rod2 = base + [self._ia("EXTRA-1", "revisar", "baixa", "redacao B"),
                       self._ia("EXTRA-2", "alerta", "alta", "achado a mais")]
        import re
        htmls = []
        for ap in (rod1, rod2):
            pct, nivel = analisador.indice_de_risco(ap)
            h = analisador.gerar_html(ap, pct, nivel, "e.pdf", 10)
            htmls.append(re.sub(r"gerado em \d{2}/\d{2}/\d{4} \d{2}:\d{2}", "<TS>", h))
        det = [h.split("Observacoes adicionais da IA")[0] for h in htmls]
        assert det[0] == det[1], "a parte deterministica mudou quando so a IA mudou"
        assert htmls[0] != htmls[1], "o bloco da IA deveria refletir a diferenca"

    def test_achados_da_ia_ficam_fora_da_tabela_principal(self):
        ap = [self._regra("R01"), self._ia("EXTRA-1", detalhe="SO_NO_BLOCO_DA_IA")]
        pct, nivel = analisador.indice_de_risco(ap)
        h = analisador.gerar_html(ap, pct, nivel, "e.pdf", 1)
        antes, depois = h.split("Observacoes adicionais da IA")
        assert "SO_NO_BLOCO_DA_IA" not in antes
        assert "SO_NO_BLOCO_DA_IA" in depois

    def test_sem_achados_da_ia_nao_cria_bloco(self):
        ap = [self._regra("R01")]
        pct, nivel = analisador.indice_de_risco(ap)
        h = analisador.gerar_html(ap, pct, nivel, "e.pdf", 1)
        assert "Observacoes adicionais da IA" not in h

    def test_primeira_tela_nao_mostra_contagem_da_ia(self):
        ap = [self._regra("R01")] + [self._ia(f"EXTRA-{i}") for i in range(1, 6)]
        pct, nivel = analisador.indice_de_risco(ap)
        h = analisador.gerar_html(ap, pct, nivel, "e.pdf", 1)
        topo = h.split("Observacoes adicionais da IA")[0]
        assert "Total de pontos da IA" not in topo
        assert "5 ponto(s) de atencao" not in topo
