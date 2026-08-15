from __future__ import annotations
import verificacao_prazos as VP


def _ids(achados):
    return [a["id"] for a in achados]


def _por_id(achados, pid):
    return next(a for a in achados if a["id"] == pid)


class TestMapeamentoDeSecoes:
    def test_sumario_de_anexos_nao_abre_secao(self):
        """Defeito real do edital de Laranjeiras (14/08/2026).

        O corpo do edital lista os anexos perto do fim. Tomando a PRIMEIRA
        ocorrência, a minuta de contrato "começava" no sumário e engolia o
        Termo de Referência inteiro — todos os prazos eram atribuídos à peça
        errada e a comparação entre peças virava ficção.
        """
        texto = (
            "EDITAL DE PREGAO\n"
            "1.1 Objeto: aquisicao de bens.\n"
            "ANEXO I - Termo de Referencia\n"
            "ANEXO III - Minuta da Ata de Registro de Precos\n"
            "ANEXO IV - Minuta do Contrato\n"
            + ("corpo do edital continua. " * 40) + "\n"
            "TERMO DE REFERENCIA - TR\n"
            + ("texto do TR. " * 40) + "\n"
            "MINUTA DA ATA DE REGISTRO DE PRECOS\n"
            + ("texto da ata. " * 40) + "\n"
            "MINUTA DE CONTRATO N 001/2026\n"
            + ("texto do contrato. " * 40)
        )
        marcos = VP.mapear_secoes(texto)
        secoes = [s for _, s in marcos]
        assert secoes == ["CORPO", "TR", "ATA", "CONTRATO"], secoes
        # a secao real do contrato fica DEPOIS do TR, nao no sumario
        pos = {s: p for p, s in marcos}
        assert pos["TR"] < pos["ATA"] < pos["CONTRATO"]
        assert pos["CONTRATO"] > texto.index("texto do TR.")

    def test_remissao_no_meio_da_frase_nao_abre_secao(self):
        texto = ("Conforme especificacoes do Anexo I - Termo de Referencia do Edital, "
                 "o licitante devera apresentar proposta.\n")
        assert [s for _, s in VP.mapear_secoes(texto)] == ["CORPO"]


class TestExtracaoDePrazos:
    def test_vigencia_da_contratacao_nao_e_prazo_de_entrega(self):
        """Defeito real, pego no 1º teste: o módulo acusou "inconformidade —
        12 meses x 30 dias" num edital em que os dois números estão certos.
        Vigência e prazo de entrega são obrigações distintas."""
        texto = ("4.3. O prazo de vigencia da contratacao e de 12 (doze) meses, contada da "
                 "prolacao da ordem de fornecimento.\n"
                 "5.3. O prazo de entrega dos itens sera de ate 30 (trinta) dias contados a "
                 "partir do envio da nota de empenho.\n")
        prazos = VP.extrair_prazos_entrega(texto)
        assert [(p["valor"], p["unidade"]) for p in prazos] == [(30, "dias corridos")]

    def test_prazo_de_pagamento_nao_entra(self):
        texto = "18.1 O prazo para pagamento das notas fiscais sera de 30 (trinta) dias.\n"
        assert VP.extrair_prazos_entrega(texto) == []

    def test_dias_uteis_nao_vira_dias_corridos(self):
        texto = "O prazo de entrega sera de 30 (trinta) dias uteis contados da nota de empenho.\n"
        p = VP.extrair_prazos_entrega(texto)[0]
        assert p["unidade"] == "dias úteis"

    def test_marco_inicial_identificado(self):
        texto = ("O prazo de entrega sera de 30 (trinta) dias contados a partir do envio da "
                 "nota de empenho.\n")
        assert VP.extrair_prazos_entrega(texto)[0]["marco"] == "nota de empenho"


class TestAchados:
    def test_ids_fixos_sempre_presentes(self):
        assert _ids(VP.verificar("")) == ["P01", "P02"]
        assert _ids(VP.verificar("O prazo de entrega e de 30 (trinta) dias.")) == ["P01", "P02"]

    def test_sem_prazo_localizado_sai_revisar_e_nunca_afirma_ausencia(self):
        achados = VP.verificar("Edital sem qualquer previsao numerica.")
        p01 = _por_id(achados, "P01")
        assert p01["status"] == "revisar"
        assert "NÃO significa que o edital seja omisso" in p01["detalhe"]

    def test_prazos_diferentes_viram_inconformidade(self):
        texto = (
            "O prazo de entrega sera de 30 (trinta) dias contados da nota de empenho.\n"
            + ("corpo. " * 40) + "\n"
            "TERMO DE REFERENCIA - TR\n"
            "5.3. O prazo de entrega dos itens sera de ate 15 (quinze) dias contados da "
            "nota de empenho.\n"
        )
        p01 = _por_id(VP.verificar(texto), "P01")
        assert p01["status"] == "inconformidade"
        assert p01["severidade"] == "alta"
        assert "15 dias corridos" in p01["detalhe"] and "30 dias corridos" in p01["detalhe"]

    def test_dias_uteis_contra_dias_corridos_e_divergencia(self):
        texto = (
            "O prazo de entrega sera de 30 (trinta) dias contados da nota de empenho.\n"
            + ("corpo. " * 40) + "\n"
            "TERMO DE REFERENCIA - TR\n"
            "O prazo de entrega sera de 30 (trinta) dias uteis contados da nota de empenho.\n"
        )
        assert _por_id(VP.verificar(texto), "P01")["status"] == "inconformidade"

    def test_prazo_so_no_TR_e_alerta_nao_inconformidade(self):
        texto = (
            "EDITAL\n" + ("corpo sem prazo. " * 40) + "\n"
            "TERMO DE REFERENCIA - TR\n"
            "O prazo de entrega sera de 30 (trinta) dias contados da nota de empenho.\n"
        )
        p01 = _por_id(VP.verificar(texto), "P01")
        assert p01["status"] == "alerta"
        assert "APENAS" in p01["detalhe"]

    def test_prazo_igual_em_duas_pecas_e_ok(self):
        texto = (
            "O prazo de entrega sera de 30 (trinta) dias contados da nota de empenho.\n"
            + ("corpo. " * 40) + "\n"
            "TERMO DE REFERENCIA - TR\n"
            "O prazo de entrega sera de 30 (trinta) dias contados da nota de empenho.\n"
        )
        achados = VP.verificar(texto)
        assert _por_id(achados, "P01")["status"] == "ok"
        assert _por_id(achados, "P02")["status"] == "ok"

    def test_mesmo_numero_com_marcos_diferentes_e_alerta(self):
        """O achado real de Laranjeiras: 30 dias nos dois pontos, mas um conta
        da nota de empenho e o outro da solicitação atestada."""
        texto = (
            "5.3. O prazo de entrega dos itens sera de ate 30 (trinta) dias contados a "
            "partir do envio da nota de empenho.\n"
            "11.4. As entregas dos itens deverao ser efetuadas em, no maximo, 30 (trinta) "
            "dias apos atestada a solicitacao previamente encaminhada.\n"
        )
        achados = VP.verificar(texto)
        assert _por_id(achados, "P01")["status"] in ("ok", "alerta")   # numero bate
        p02 = _por_id(achados, "P02")
        assert p02["status"] == "alerta"
        assert "nota de empenho" in p02["detalhe"]
        assert "solicitação atestada" in p02["detalhe"]

    def test_prazo_sem_marco_inicial_sai_revisar(self):
        texto = "O prazo de entrega sera de 30 (trinta) dias.\n"
        p02 = _por_id(VP.verificar(texto), "P02")
        assert p02["status"] == "revisar"

    def test_formato_do_achado_compativel_com_o_relatorio(self):
        for a in VP.verificar("O prazo de entrega sera de 30 (trinta) dias."):
            for campo in ("id", "categoria", "item", "base_legal", "severidade",
                          "tipo", "status", "detalhe", "trecho", "fonte", "fundamento"):
                assert campo in a, campo
            assert a["fonte"] == "Automatico"      # entra no indice, nao no bloco da IA
            assert a["status"] in ("inconformidade", "alerta", "revisar", "ok")
            assert a["severidade"] in ("alta", "media", "baixa")


class TestRotuloDoSelo:
    """O rótulo padrão de "alerta" no analisador é "Alerta - possivel ausencia",
    que descreve requisito não localizado. Chamar de "possível ausência" uma
    DIVERGÊNCIA entre duas peças do edital descreve errado o achado — e isto é
    um documento jurídico."""

    def test_p02_nao_e_rotulado_como_possivel_ausencia(self):
        texto = ("5.3. O prazo de entrega sera de 30 (trinta) dias contados da nota de empenho.\n"
                 "11.4. As entregas dos itens deverao ser efetuadas em 30 (trinta) dias apos "
                 "atestada a solicitacao.\n")
        p02 = next(a for a in VP.verificar(texto) if a["id"] == "P02")
        assert p02["rotulo_status"] == "Alerta - divergência entre peças"

    def test_regra_comum_mantem_o_rotulo_padrao(self):
        import analisador
        regra = {"id": "R99", "item": "Requisito", "categoria": "C", "status": "alerta",
                 "severidade": "media", "detalhe": "nao localizado", "trecho": "",
                 "fonte": "Automatico", "fundamento": "", "base_legal": "art. 1"}
        pct, nivel = analisador.indice_de_risco([regra])
        html = analisador.gerar_html([regra], pct, nivel, "e.pdf", 1)
        assert "Alerta - possivel ausencia" in html
