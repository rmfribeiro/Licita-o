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


class TestObservacoesDaIaNoBlocoDoFim:
    """Decisão de 14/08/2026, depois de medir os relatórios 3 e 4 de Laranjeiras.

    Os 38 ids, os status, as contagens e o índice saíram idênticos entre as duas
    execuções — mas as 16 "Observações da IA" mudaram TODAS, algumas com 26% de
    similaridade. Como ficavam no miolo da tabela principal, quem comparasse dois
    relatórios do mesmo edital veria 16 parágrafos diferentes com todos os
    números iguais. Texto que varia vai para o bloco que avisa que varia.
    """
    _regra = staticmethod(TestSeparacaoCamadaIA._regra)
    _ia = staticmethod(TestSeparacaoCamadaIA._ia)

    def _html(self, apont):
        import re
        pct, nivel = analisador.indice_de_risco(apont)
        h = analisador.gerar_html(apont, pct, nivel, "e.pdf", 10)
        return re.sub(r"gerado em \d{2}/\d{2}/\d{4} \d{2}:\d{2}", "<TS>", h)

    def test_observacao_sai_da_tabela_principal(self):
        r = dict(self._regra("R01", "alerta"), observacao_ia="TEXTO_QUE_VARIA_ENTRE_ANALISES")
        h = self._html([r])
        antes, depois = h.split("Observacoes adicionais da IA")
        assert "TEXTO_QUE_VARIA_ENTRE_ANALISES" not in antes
        assert "TEXTO_QUE_VARIA_ENTRE_ANALISES" in depois

    def test_bloco_do_fim_existe_so_com_observacoes(self):
        """Sem achados livres, mas com comentários, o bloco ainda tem de aparecer."""
        r = dict(self._regra("R01"), observacao_ia="comentario")
        assert "Observacoes adicionais da IA" in self._html([r])

    def test_tabela_principal_identica_com_observacoes_totalmente_diferentes(self):
        base = [self._regra("R01", "inconformidade", "alta"), self._regra("R02", "alerta"),
                self._regra("R03", "ok")]
        r1 = [dict(a, observacao_ia=f"redacao A {i}") for i, a in enumerate(base)]
        r2 = [dict(a, observacao_ia=f"outra redacao completamente diferente {i}")
              for i, a in enumerate(base)]
        d1 = self._html(r1).split("Observacoes adicionais da IA")[0]
        d2 = self._html(r2).split("Observacoes adicionais da IA")[0]
        assert d1 == d2

    def test_comentario_indica_a_regra_que_comenta(self):
        r = dict(self._regra("R07", "alerta"), observacao_ia="comentario")
        depois = self._html([r]).split("Observacoes adicionais da IA")[1]
        assert "R07" in depois
        assert "Comentário sobre:" in depois
