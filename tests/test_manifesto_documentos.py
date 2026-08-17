from __future__ import annotations
import ia_utils


class TestManifestoDocumentos:
    """Criado em 17/08/2026, depois do teste da Reabilitação.

    Um parecer citou "GRU nº 2022/4471" — dado de um documento que o Roberto
    acreditava ter substituído. O `st.file_uploader` com
    accept_multiple_files=True ACRESCENTA arquivos: arrastar um novo sem remover
    o anterior analisa os dois. Descobrir isso exigiu deduzir por marcadores de
    texto. O relatório passa a dizer o que leu.
    """

    def test_dois_arquivos_sao_listados_separadamente(self):
        texto = ("[ARQUIVO: completo.pdf]\nconteudo A\n\n"
                 "[ARQUIVO: incompleto.pdf]\nB")
        docs = ia_utils.manifesto_documentos(texto)
        assert [d["arquivo"] for d in docs] == ["completo.pdf", "incompleto.pdf"]
        assert docs[0]["chars"] > docs[1]["chars"]

    def test_um_arquivo(self):
        docs = ia_utils.manifesto_documentos("[ARQUIVO: unico.pdf]\ntexto qualquer")
        assert len(docs) == 1 and docs[0]["arquivo"] == "unico.pdf"

    def test_sem_documento_nao_inventa_lista(self):
        assert ia_utils.manifesto_documentos(None) == []
        assert ia_utils.manifesto_documentos("") == []

    def test_texto_sem_marcacao_ainda_e_declarado(self):
        """Chamada direta ou extrator antigo: melhor declarar 'documento
        enviado' do que sumir com a informação."""
        docs = ia_utils.manifesto_documentos("texto sem marca de arquivo")
        assert len(docs) == 1
        assert docs[0]["chars"] == len("texto sem marca de arquivo")

    def test_linhas_prontas_para_exibicao(self):
        docs = [{"arquivo": "a.pdf", "chars": 12345}]
        assert ia_utils.linhas_manifesto(docs) == ["a.pdf — 12.345 caracteres extraídos"]

    def test_linhas_vazias_quando_nao_ha_documento(self):
        assert ia_utils.linhas_manifesto([]) == []
        assert ia_utils.linhas_manifesto(None) == []


class TestManifestoChegaAoParecer:
    """O manifesto tem de sair do extrator e chegar ao relatório."""

    def test_reabilitacao(self):
        from datetime import date
        from unittest.mock import patch
        import ia_reabilitacao
        from tests.helpers import mock_urlopen
        par = {"parecer": "ELEGÍVEL", "condicoes_avaliadas": [
            {"numero": "I", "descricao": "c", "status": "ATENDIDA", "observacao": ""}],
            "sintese": "", "base_legal": []}
        with patch("ia_utils.urllib.request.urlopen", return_value=mock_urlopen(par)):
            r = ia_reabilitacao.analisar(
                "impedimento", {"cnpj": "1"}, {"data_aplicacao": "2020-01-01"},
                {}, "[ARQUIVO: prova.pdf]\nconteudo", "key",
                data_referencia=date(2026, 8, 17))
        assert [d["arquivo"] for d in r["_documentos_analisados"]] == ["prova.pdf"]

    def test_recebimento(self):
        from unittest.mock import patch
        import ia_recebimento
        from tests.helpers import mock_urlopen
        par = {"recebimento_provisorio": {"parecer": "APTO", "condicoes": [
                   {"descricao": "c", "status": "ATENDIDA", "observacao": ""}],
                   "pendencias": [], "sintese": ""},
               "recebimento_definitivo": {"parecer": "APTO", "condicoes": [],
                   "pendencias": [], "sintese": ""},
               "recomendacoes_gerais": [], "base_legal": []}
        with patch("ia_utils.urllib.request.urlopen", return_value=mock_urlopen(par)):
            r = ia_recebimento.analisar("bem", {}, "[ARQUIVO: nf.pdf]\nnota", "key")
        assert [d["arquivo"] for d in r["_documentos_analisados"]] == ["nf.pdf"]

    def test_sem_documento_o_campo_fica_vazio(self):
        from unittest.mock import patch
        import ia_recebimento
        from tests.helpers import mock_urlopen
        par = {"recebimento_provisorio": {"parecer": "APTO", "condicoes": [],
                   "pendencias": [], "sintese": ""},
               "recebimento_definitivo": {"parecer": "APTO", "condicoes": [],
                   "pendencias": [], "sintese": ""},
               "recomendacoes_gerais": [], "base_legal": []}
        with patch("ia_utils.urllib.request.urlopen", return_value=mock_urlopen(par)):
            r = ia_recebimento.analisar("bem", {}, None, "key")
        assert r["_documentos_analisados"] == []


class TestLastroDocumental:
    """Decisão de 17/08/2026, depois do Teste 5 da Reabilitação.

    O parecer afirmou "COMPROVADO o pagamento integral da multa no valor de
    R$ 38.400,00" — valor que existia apenas no formulário, num pedido cujo
    documento não mencionava multa alguma. Resposta de formulário é DECLARAÇÃO,
    não prova; e o art. 163 exige comprovação.
    """

    def test_sem_documento_o_parecer_e_marcado(self):
        assert ia_utils.sem_lastro_documental({"_documentos_analisados": []}) is True
        assert ia_utils.sem_lastro_documental({}) is True

    def test_com_documento_nao_e_marcado(self):
        p = {"_documentos_analisados": [{"arquivo": "a.pdf", "chars": 10}]}
        assert ia_utils.sem_lastro_documental(p) is False

    def test_o_aviso_nao_afirma_irregularidade(self):
        """O aviso diz que nada foi comprovado — não que algo está errado."""
        a = ia_utils.AVISO_SEM_LASTRO
        assert "NÃO comprova" in a
        assert "declarado" in a.lower()
        for palavra in ("irregular", "inidôneo", "descumpre"):
            assert palavra not in a.lower()

    def test_regra_do_lastro_chega_ao_prompt_da_reabilitacao(self):
        import json
        from datetime import date
        from unittest.mock import patch
        import ia_reabilitacao
        from tests.helpers import mock_urlopen
        par = {"parecer": "ELEGÍVEL", "condicoes_avaliadas": [], "sintese": "", "base_legal": []}
        with patch("ia_utils.urllib.request.urlopen", return_value=mock_urlopen(par)) as mock:
            ia_reabilitacao.analisar("impedimento", {"cnpj": "1"},
                                     {"data_aplicacao": "2020-01-01"}, {}, None, "key",
                                     data_referencia=date(2026, 8, 17))
        corpo = json.loads(mock.call_args[0][0].data.decode("utf-8"))
        sistema = corpo["system"] if isinstance(corpo.get("system"), str) else str(corpo.get("system"))
        assert "declarado no formulário, sem comprovação documental anexada" in sistema
        assert "NUNCA escreva 'comprovado'" in sistema


class TestDataBrasileira:
    """O `st.date_input` devolve ISO e o Streamlit exibia AAAA/MM/DD."""

    def test_formatos_aceitos(self):
        from datetime import date
        assert ia_utils.fmt_data_br(date(2022, 3, 10)) == "10/03/2022"
        assert ia_utils.fmt_data_br("2022-03-10") == "10/03/2022"
        assert ia_utils.fmt_data_br("2022/03/10") == "10/03/2022"
        assert ia_utils.fmt_data_br("20220310") == "10/03/2022"

    def test_ja_brasileira_nao_e_alterada(self):
        assert ia_utils.fmt_data_br("10/03/2022") == "10/03/2022"

    def test_vazio_usa_default(self):
        assert ia_utils.fmt_data_br(None) == "não informada"
        assert ia_utils.fmt_data_br("", "-") == "-"
