from __future__ import annotations
import json
import urllib.error
import pytest
from unittest.mock import patch, MagicMock
import ia_fid
from .helpers import mock_urlopen as _mock_urlopen


def _dados_licitante_mock() -> dict:
    return {
        "cnpj":          "12345678000195",
        "razao_social":  "Empresa XPTO Ltda",
        "numero_edital": "PE 042/2024",
        "objeto":        "Contratação de serviços de TI",
        "orgao":         "Ministério da Educação",
    }


def _parecer_api_mock() -> dict:
    return {
        "necessita_diligencia": "SIM",
        "documentos_solicitados": [
            {
                "documento": "Certidão de regularidade com o FGTS",
                "situacao": "vencida",
                "fundamento_legal": "Art. 62, III, Lei 14.133/2021",
                "prazo_dias": 5,
            }
        ],
        "pontos_de_atencao": ["Certidão FGTS vencida há 15 dias."],
        "minuta_oficio": (
            "OFÍCIO DE DILIGÊNCIA Nº ___\n\n"
            "Assunto: Complementação documental.\n\n"
            "Senhor(a) Representante,\n\nSolicitamos a complementação dos documentos indicados."
        ),
        "prazo_resposta_sugerido": 5,
        "conclusao": "Necessária a complementação da documentação de habilitação.",
        "base_legal": [
            "Art. 59, §2º, Lei 14.133/2021",
            "Art. 64, I e II, Lei 14.133/2021",
        ],
    }


class TestConstantes:
    def test_fases_tem_3_opcoes(self):
        assert len(ia_fid.FASES_PROCESSO) == 3

    def test_fases_chaves_corretas(self):
        assert set(ia_fid.FASES_PROCESSO.keys()) == {
            "habilitacao", "proposta", "pos_adjudicacao"
        }

    def test_resultado_diligencia_tem_3_opcoes(self):
        assert len(ia_fid.RESULTADO_DILIGENCIA) == 3

    def test_resultado_diligencia_contem_sim_nao_parcialmente(self):
        assert "SIM" in ia_fid.RESULTADO_DILIGENCIA
        assert "NÃO" in ia_fid.RESULTADO_DILIGENCIA
        assert "PARCIALMENTE" in ia_fid.RESULTADO_DILIGENCIA

    def test_fases_sao_mapping_proxy(self):
        import types
        assert isinstance(ia_fid.FASES_PROCESSO, types.MappingProxyType)
        assert isinstance(ia_fid.RESULTADO_DILIGENCIA, types.MappingProxyType)


class TestAnalisar:
    def test_fase_invalida_levanta_value_error(self):
        with pytest.raises(ValueError, match="Fase inválida"):
            ia_fid.analisar("inexistente", {}, "situação", None, "key")

    def test_retorna_dict_com_chaves_obrigatorias(self):
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(_parecer_api_mock())):
            r = ia_fid.analisar(
                "habilitacao", _dados_licitante_mock(), "FGTS vencido", None, "key"
            )
        assert "necessita_diligencia" in r
        assert "documentos_solicitados" in r
        assert "minuta_oficio" in r
        assert "conclusao" in r
        assert "base_legal" in r

    def test_necessita_diligencia_sim(self):
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(_parecer_api_mock())):
            r = ia_fid.analisar(
                "habilitacao", _dados_licitante_mock(), "doc ausente", None, "key"
            )
        assert r["necessita_diligencia"] == "SIM"

    def test_resultado_nao_sem_acento_normalizado(self):
        parecer = {**_parecer_api_mock(),
                   "necessita_diligencia": "NAO", "documentos_solicitados": []}
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(parecer)):
            r = ia_fid.analisar(
                "proposta", _dados_licitante_mock(), "tudo ok", None, "key"
            )
        assert r["necessita_diligencia"] == "NÃO"

    def test_resultado_parcial_normalizado(self):
        parecer = {**_parecer_api_mock(), "necessita_diligencia": "PARCIAL"}
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(parecer)):
            r = ia_fid.analisar(
                "habilitacao", _dados_licitante_mock(), "dúvida", None, "key"
            )
        assert r["necessita_diligencia"] == "PARCIALMENTE"

    def test_resultado_desconhecido_e_derivado_da_lista_com_aviso(self):
        """Antes caía em PARCIALMENTE: selo laranja afirmando que a diligência é
        parcialmente necessária, construído a partir de uma falha de leitura.
        Agora o veredito vem da lista de documentos e o valor original fica
        registrado."""
        parecer = {**_parecer_api_mock(), "necessita_diligencia": "TALVEZ"}
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(parecer)):
            r = ia_fid.analisar(
                "habilitacao", _dados_licitante_mock(), "dúvida", None, "key"
            )
        assert r["necessita_diligencia"] == "SIM"   # há 1 documento a solicitar
        assert r.get("_aviso_nd") == "TALVEZ"

    def test_sem_resultado_e_sem_documentos_vira_nao_avaliado(self):
        """Nem 'necessária' nem 'desnecessária': ausência de base para as duas.
        Não ter base nunca vira selo colorido."""
        parecer = {**_parecer_api_mock(),
                   "necessita_diligencia": None, "documentos_solicitados": []}
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(parecer)):
            r = ia_fid.analisar(
                "habilitacao", _dados_licitante_mock(), "dúvida", None, "key"
            )
        assert r["necessita_diligencia"] == ia_fid.RESULTADO_NAO_AVALIADO

    def test_sim_sem_nenhum_documento_a_solicitar_vira_nao_avaliado(self):
        """Ofício sem objeto: a IA afirma a diligência e não diz o que pedir."""
        parecer = {**_parecer_api_mock(),
                   "necessita_diligencia": "SIM", "documentos_solicitados": []}
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(parecer)):
            r = ia_fid.analisar(
                "habilitacao", _dados_licitante_mock(), "dúvida", None, "key"
            )
        assert r["necessita_diligencia"] == ia_fid.RESULTADO_NAO_AVALIADO
        assert r.get("_divergencia_ia") == "SIM"

    def test_resultado_bool_true_vira_sim_sem_aviso(self):
        parecer = {**_parecer_api_mock(), "necessita_diligencia": True}
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(parecer)):
            r = ia_fid.analisar(
                "habilitacao", _dados_licitante_mock(), "dúvida", None, "key"
            )
        assert r["necessita_diligencia"] == "SIM"
        assert "_aviso_nd" not in r

    def test_resultado_bool_false_vira_nao_quando_nada_a_solicitar(self):
        parecer = {**_parecer_api_mock(),
                   "necessita_diligencia": False, "documentos_solicitados": []}
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(parecer)):
            r = ia_fid.analisar(
                "habilitacao", _dados_licitante_mock(), "dúvida", None, "key"
            )
        assert r["necessita_diligencia"] == "NÃO"
        assert "_aviso_nd" not in r
        assert "_divergencia_ia" not in r

    def test_nao_com_documentos_listados_e_contradicao_registrada(self):
        """A IA dizia 'não há diligência a fazer' e listava, logo abaixo, um
        documento a solicitar. Nada amarrava as duas coisas."""
        parecer = {**_parecer_api_mock(), "necessita_diligencia": "NÃO"}
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(parecer)):
            r = ia_fid.analisar(
                "habilitacao", _dados_licitante_mock(), "dúvida", None, "key"
            )
        assert r["necessita_diligencia"] == "SIM"
        assert r.get("_divergencia_ia") == "NÃO"

    def test_resultado_int_e_derivado_da_lista_com_aviso(self):
        parecer = {**_parecer_api_mock(), "necessita_diligencia": 1}
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(parecer)):
            r = ia_fid.analisar(
                "habilitacao", _dados_licitante_mock(), "dúvida", None, "key"
            )
        assert r["necessita_diligencia"] == "SIM"
        assert r.get("_aviso_nd") == 1

    def test_resultado_reconhecido_nao_seta_aviso_nd(self):
        parecer = {**_parecer_api_mock(), "necessita_diligencia": "PARCIAL"}
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(parecer)):
            r = ia_fid.analisar(
                "habilitacao", _dados_licitante_mock(), "dúvida", None, "key"
            )
        assert r["necessita_diligencia"] == "PARCIALMENTE"
        assert "_aviso_nd" not in r

    def test_pop_limpa_aviso_nd_espurio_da_api(self):
        parecer = {**_parecer_api_mock(), "necessita_diligencia": "SIM", "_aviso_nd": "stale"}
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(parecer)):
            r = ia_fid.analisar(
                "habilitacao", _dados_licitante_mock(), "dúvida", None, "key"
            )
        assert r["necessita_diligencia"] == "SIM"
        assert "_aviso_nd" not in r

    # ------------------------------------------------------------------ prazos
    # A versao anterior tinha um _clamp_prazo que devolvia 5 sempre que a IA nao
    # respondesse, e esse 5 ia impresso na tabela do PDF e no oficio — num campo
    # PRECLUSIVO. Numero inventado em peca que faz correr prazo contra o
    # particular e a mesma familia do "percentual_multa or 0.5" da Dosimetria.

    def test_prazo_fora_da_faixa_nao_e_aparado_para_a_borda(self):
        """Aparar 999 para 30 nao corrige a resposta: substitui um numero errado
        da IA por um numero nosso, com aparencia de conferido."""
        for absurdo in (999, 0, -3):
            parecer = {**_parecer_api_mock(), "prazo_resposta_sugerido": absurdo}
            with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(parecer)):
                r = ia_fid.analisar(
                    "habilitacao", _dados_licitante_mock(), "teste", None, "key"
                )
            assert r["prazo_resposta_sugerido"] is None, absurdo

    def test_prazo_nao_numerico_fica_vazio(self):
        parecer = {**_parecer_api_mock(), "prazo_resposta_sugerido": "não informado"}
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(parecer)):
            r = ia_fid.analisar(
                "habilitacao", _dados_licitante_mock(), "teste", None, "key"
            )
        assert r["prazo_resposta_sugerido"] is None

    def test_prazo_none_continua_none_e_nunca_vira_5(self):
        parecer = {**_parecer_api_mock(), "prazo_resposta_sugerido": None}
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(parecer)):
            r = ia_fid.analisar(
                "habilitacao", _dados_licitante_mock(), "teste",
                "[ARQUIVO: edital.pdf]\nO prazo de resposta é de 5 dias.", "key"
            )
        assert r["prazo_resposta_sugerido"] is None
        assert r["documentos_solicitados"][0]["prazo_dias"] == 5   # com lastro, aceito

    def test_prazo_sem_documento_anexado_e_descartado(self):
        """Sem documento anexado não existe fonte de onde ler prazo: qualquer
        número devolvido nasceu do formulário ou do nada. Declaração não vira
        prazo preclusivo em ofício."""
        with patch("ia_utils.urllib.request.urlopen",
                   return_value=_mock_urlopen(_parecer_api_mock())):
            r = ia_fid.analisar(
                "habilitacao", _dados_licitante_mock(), "teste", None, "key"
            )
        assert r["prazo_resposta_sugerido"] is None
        assert r["documentos_solicitados"][0]["prazo_dias"] is None

    def test_prazo_do_item_ausente_fica_vazio(self):
        parecer = _parecer_api_mock()
        parecer["documentos_solicitados"][0].pop("prazo_dias")
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(parecer)):
            r = ia_fid.analisar(
                "habilitacao", _dados_licitante_mock(), "teste",
                "[ARQUIVO: edital.pdf]\ntexto", "key"
            )
        assert r["documentos_solicitados"][0]["prazo_dias"] is None

    def test_sem_documentos_nao_levanta_erro(self):
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(_parecer_api_mock())):
            r = ia_fid.analisar(
                "pos_adjudicacao", _dados_licitante_mock(), "pendência", None, "key"
            )
        assert isinstance(r, dict)

    def test_com_texto_docs_nao_levanta_erro(self):
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(_parecer_api_mock())):
            r = ia_fid.analisar(
                "habilitacao", _dados_licitante_mock(), "FGTS vencido",
                "Texto do documento de habilitação...", "key",
            )
        assert isinstance(r, dict)

    def test_todas_as_fases_funcionam(self):
        for fase in ia_fid.FASES_PROCESSO:
            with patch(
                "ia_utils.urllib.request.urlopen",
                return_value=_mock_urlopen(_parecer_api_mock()),
            ):
                r = ia_fid.analisar(fase, _dados_licitante_mock(), "teste", None, "key")
            assert isinstance(r, dict)

    def test_http_error_levanta_runtime_error(self):
        http_err = urllib.error.HTTPError(
            url="https://api.anthropic.com/v1/messages",
            code=401, msg="Unauthorized", hdrs=None,
            fp=MagicMock(read=MagicMock(return_value=b'{"error":"invalid key"}')),
        )
        with patch("ia_utils.urllib.request.urlopen", side_effect=http_err):
            with pytest.raises(RuntimeError, match="HTTP 401"):
                ia_fid.analisar(
                    "habilitacao", _dados_licitante_mock(), "teste", None, "key_invalida"
                )

    def test_url_error_levanta_runtime_error(self):
        url_err = urllib.error.URLError(reason="Connection refused")
        with patch("ia_utils.urllib.request.urlopen", side_effect=url_err):
            with pytest.raises(RuntimeError):
                ia_fid.analisar(
                    "habilitacao", _dados_licitante_mock(), "teste", None, "key"
                )

    def test_resultado_necessaria_feminino_mapeado_para_sim(self):
        for variante in ("NECESSÁRIA", "NECESSARIA"):
            parecer = {**_parecer_api_mock(), "necessita_diligencia": variante}
            with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(parecer)):
                r = ia_fid.analisar("habilitacao", _dados_licitante_mock(), "teste", None, "key")
            assert r["necessita_diligencia"] == "SIM", f"variante {variante!r} não mapeada"
            assert "_aviso_nd" not in r
            assert "_divergencia_ia" not in r

    def test_api_retorna_nao_dict_levanta_runtime_error(self):
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen([1, 2, 3])):
            with pytest.raises(RuntimeError, match="objeto JSON esperado"):
                ia_fid.analisar(
                    "habilitacao", _dados_licitante_mock(), "teste", None, "key"
                )


class TestIsolamentoEManifesto:
    """Este era o ÚNICO módulo que ainda punha o documento cru no prompt — e o
    pior lugar possível para essa falta: nos demais o documento vem do ÓRGÃO
    (edital, contrato, PIP); aqui vem do LICITANTE, parte adversarial, num PDF
    que ele mesmo montou."""

    def _prompt_enviado(self, mock_urlopen_ctx) -> str:
        import json as _json
        req = mock_urlopen_ctx.call_args[0][0]
        return _json.dumps(_json.loads(req.data.decode("utf-8")), ensure_ascii=False)

    def test_documento_do_licitante_vai_isolado_em_bloco(self):
        with patch("ia_utils.urllib.request.urlopen",
                   return_value=_mock_urlopen(_parecer_api_mock())) as m:
            ia_fid.analisar("habilitacao", _dados_licitante_mock(), "FGTS vencido",
                            "Certidão de regularidade do FGTS, validade 01/2024.", "key")
        enviado = self._prompt_enviado(m)
        assert "DOCUMENTOS_DO_LICITANTE" in enviado
        assert "DADO NÃO CONFIÁVEL" in enviado          # SUFIXO_SEGURANCA

    def test_regras_de_lastro_prazo_e_minuta_vao_no_sistema(self):
        with patch("ia_utils.urllib.request.urlopen",
                   return_value=_mock_urlopen(_parecer_api_mock())) as m:
            ia_fid.analisar("habilitacao", _dados_licitante_mock(), "teste", None, "key")
        enviado = self._prompt_enviado(m)
        assert "REGRA DO LASTRO DOCUMENTAL" in enviado
        assert "REGRA DO PRAZO" in enviado
        assert "REGRA DA MINUTA" in enviado

    def test_manifesto_registra_o_que_foi_lido(self):
        with patch("ia_utils.urllib.request.urlopen",
                   return_value=_mock_urlopen(_parecer_api_mock())):
            r = ia_fid.analisar("habilitacao", _dados_licitante_mock(), "teste",
                                "[ARQUIVO: fgts.pdf]\nconteudo da certidao", "key")
        docs = r["_documentos_analisados"]
        assert [d["arquivo"] for d in docs] == ["fgts.pdf"]

    def test_sem_documento_o_manifesto_fica_vazio(self):
        with patch("ia_utils.urllib.request.urlopen",
                   return_value=_mock_urlopen(_parecer_api_mock())):
            r = ia_fid.analisar("habilitacao", _dados_licitante_mock(), "teste", None, "key")
        assert r["_documentos_analisados"] == []


class TestConferirOficio:
    """A minuta é texto livre do modelo; o parecer é estrutura conferida por
    código. É a minuta que sai assinada e faz correr prazo contra o licitante."""

    def _parecer(self, **kw):
        base = {"necessita_diligencia": "SIM", "prazo_resposta_sugerido": None}
        base.update(kw)
        return base

    def test_minuta_vazia_nao_gera_alerta(self):
        assert ia_fid.conferir_oficio("", self._parecer(), {}) == []

    def test_prazo_inventado_na_minuta_e_apontado(self):
        alertas = ia_fid.conferir_oficio(
            "Solicitamos a apresentação no prazo de 5 (cinco) dias.",
            self._parecer(), {})
        assert any("preclusivo" in a for a in alertas)

    def test_prazo_da_minuta_divergente_do_parecer_e_apontado(self):
        alertas = ia_fid.conferir_oficio(
            "Apresente em 10 (dez) dias.",
            self._parecer(prazo_resposta_sugerido=5), {})
        assert any("divergente" in a for a in alertas)

    def test_prazo_coerente_nao_gera_alerta_de_prazo(self):
        alertas = ia_fid.conferir_oficio(
            "Apresente em 5 (cinco) dias.",
            self._parecer(prazo_resposta_sugerido=5), {})
        assert not any("prazo" in a.lower() for a in alertas)

    def test_numero_no_cnpj_nao_e_lido_como_prazo(self):
        """A lição da conferência da Dosimetria: comparar por substring simples
        fazia '5' casar dentro de um CNPJ."""
        alertas = ia_fid.conferir_oficio(
            "Ao licitante inscrito no CNPJ 12.345.678/0001-95, sem prazo fixado.",
            self._parecer(), {"cnpj": "12345678000195"})
        assert alertas == []

    def test_data_preenchida_e_apontada(self):
        for texto in ("Brasília, 17/08/2026.", "Brasília, 17 de agosto de 2026."):
            alertas = ia_fid.conferir_oficio(texto, self._parecer(), {})
            assert any("data" in a.lower() for a in alertas), texto

    def test_numero_de_oficio_preenchido_e_apontado(self):
        alertas = ia_fid.conferir_oficio(
            "OFÍCIO DE DILIGÊNCIA Nº 42", self._parecer(), {})
        assert any("número de ofício" in a for a in alertas)

    def test_numero_de_oficio_em_branco_nao_e_apontado(self):
        alertas = ia_fid.conferir_oficio(
            "OFÍCIO DE DILIGÊNCIA Nº ____", self._parecer(), {})
        assert alertas == []

    def test_cnpj_diferente_do_formulario_e_apontado(self):
        alertas = ia_fid.conferir_oficio(
            "Ao licitante CNPJ 99.888.777/0001-66.",
            self._parecer(), {"cnpj": "12345678000195"})
        assert any("diferente do informado" in a for a in alertas)

    def test_minuta_com_parecer_nao_avaliado_e_apontada(self):
        alertas = ia_fid.conferir_oficio(
            "OFÍCIO DE DILIGÊNCIA Nº ____",
            self._parecer(necessita_diligencia=ia_fid.RESULTADO_NAO_AVALIADO), {})
        assert any("sem conclusão que a sustente" in a for a in alertas)

    def test_conferencia_roda_dentro_de_analisar(self):
        # sem documento anexado o prazo e descartado -> "5 (cinco) dias" na
        # minuta vira prazo sem lastro, alem do numero de oficio preenchido
        parecer = {**_parecer_api_mock(),
                   "minuta_oficio": "OFÍCIO Nº 7\nApresente em 5 (cinco) dias."}
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(parecer)):
            r = ia_fid.analisar("habilitacao", _dados_licitante_mock(), "teste", None, "key")
        assert len(r["_conferencia_oficio"]) >= 2


class TestSituacaoSemLastro:
    """Defeito real do 1º teste: a REGRA DO LASTRO mandava usar 'pendente'. O
    modelo escreveu na CONCLUSÃO que havia obedecido e preencheu a coluna com
    'vencido' e 'inconsistente'. Declarar obediência a uma regra descumprida é
    pior do que não ter a regra."""

    def _com_situacoes(self, *situacoes):
        return {**_parecer_api_mock(), "documentos_solicitados": [
            {"documento": f"Doc {i}", "situacao": s,
             "fundamento_legal": "Art. 64, I", "prazo_dias": None}
            for i, s in enumerate(situacoes, 1)]}

    def test_constatacao_sem_documento_anexado_vira_pendente(self):
        parecer = self._com_situacoes("vencido", "inconsistente", "ausente", "ilegível")
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(parecer)):
            r = ia_fid.analisar("habilitacao", _dados_licitante_mock(), "teste", None, "key")
        for d in r["documentos_solicitados"]:
            assert d["situacao"] == ia_fid.SITUACAO_PENDENTE, d
        assert [d["_situacao_declarada"] for d in r["documentos_solicitados"]] == \
               ["vencido", "inconsistente", "ausente", "ilegível"]

    def test_com_documento_anexado_a_constatacao_e_preservada(self):
        parecer = self._com_situacoes("vencido")
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(parecer)):
            r = ia_fid.analisar("habilitacao", _dados_licitante_mock(), "teste",
                                "[ARQUIVO: fgts.pdf]\nCertidão vencida em 10/05/2026", "key")
        d = r["documentos_solicitados"][0]
        assert d["situacao"] == "vencido"
        assert "_situacao_declarada" not in d

    def test_situacao_desconhecida_vira_pendente_mesmo_com_lastro(self):
        parecer = self._com_situacoes("gravíssimo")
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(parecer)):
            r = ia_fid.analisar("habilitacao", _dados_licitante_mock(), "teste",
                                "[ARQUIVO: a.pdf]\ntexto", "key")
        d = r["documentos_solicitados"][0]
        assert d["situacao"] == ia_fid.SITUACAO_PENDENTE
        assert d["_situacao_declarada"] == "gravíssimo"

    def test_pendente_declarado_pela_ia_nao_ganha_sufixo_redundante(self):
        parecer = self._com_situacoes("pendente")
        with patch("ia_utils.urllib.request.urlopen", return_value=_mock_urlopen(parecer)):
            r = ia_fid.analisar("habilitacao", _dados_licitante_mock(), "teste", None, "key")
        d = r["documentos_solicitados"][0]
        assert d["situacao"] == ia_fid.SITUACAO_PENDENTE
        assert "_situacao_declarada" not in d


class TestDataNaMinuta:
    """A conferência acusou 'a minuta contém data' por causa de 'validade
    expirada em 10/05/2026' — citação legítima do vício, no corpo do ofício. O
    campo da data estava em branco. Verificador que grita sem motivo queima a
    credibilidade dos avisos verdadeiros."""

    def _p(self):
        return {"necessita_diligencia": "SIM", "prazo_resposta_sugerido": None}

    def test_data_citada_no_corpo_nao_e_alerta(self):
        for corpo in (
            "A certidão apresenta validade expirada em 10/05/2026, o que configura vício.",
            "O documento venceu em 1º de janeiro e não foi renovado.",
            "Conforme edital publicado em 03/02/2026, apresente os documentos.",
        ):
            assert ia_fid.conferir_oficio(corpo, self._p(), {}) == [], corpo

    def test_data_no_campo_do_oficio_e_alerta(self):
        for cabecalho in ("Data: 17/08/2026", "Data : 17 de agosto de 2026",
                          "Em: 17/08/2026"):
            alertas = ia_fid.conferir_oficio(cabecalho, self._p(), {})
            assert any("data" in a.lower() for a in alertas), cabecalho

    def test_data_no_fecho_cidade_virgula_data_e_alerta(self):
        alertas = ia_fid.conferir_oficio(
            "Atenciosamente,\nAracaju, 17 de agosto de 2026\n____", self._p(), {})
        assert any("data" in a.lower() for a in alertas)

    def test_campo_de_data_em_branco_nao_e_alerta(self):
        assert ia_fid.conferir_oficio("Data: ____", self._p(), {}) == []


class TestCominacao:
    """Defeito real do 2º teste: em pós-adjudicação a minuta escreveu 'sob pena
    de desclassificação da proposta e consequente rescisão do processo de
    contratação'. Nessa fase não se desclassifica proposta."""

    def _p(self):
        return {"necessita_diligencia": "SIM", "prazo_resposta_sugerido": None}

    def test_sob_pena_de_e_apontado(self):
        alertas = ia_fid.conferir_oficio(
            "Apresente os documentos, sob pena de desclassificação da proposta.",
            self._p(), {})
        assert any("comina consequência" in a for a in alertas)

    def test_variantes_de_cominacao(self):
        for t in ("sob pena de inabilitação", "sob pena de rescisão contratual",
                  "sob pena de desqualificação do certame"):
            assert ia_fid.conferir_oficio(f"Apresente o documento, {t}.", self._p(), {}), t

    def test_oficio_sem_cominacao_nao_gera_alerta(self):
        alertas = ia_fid.conferir_oficio(
            "OFÍCIO DE DILIGÊNCIA Nº ____\nData: ____\n"
            "Apresente os documentos no prazo de ____ (____) dias.", self._p(), {})
        assert alertas == []
