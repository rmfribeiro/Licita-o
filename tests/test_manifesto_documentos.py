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
