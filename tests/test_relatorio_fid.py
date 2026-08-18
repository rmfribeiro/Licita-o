from __future__ import annotations
import re
import ia_fid
import ia_utils
import relatorio_fid


def _texto_do_pdf(pdf: bytes) -> str:
    """Extrai o texto do PDF gerado. Conferir o objeto Python nao basta: o que o
    prefeito le e o PDF."""
    import pdfplumber
    import io
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        bruto = "\n".join((p.extract_text() or "") for p in doc.pages)
    # a quebra de linha do PDF parte frases no meio; para procurar texto,
    # normalizar o espaco em branco evita falso negativo
    return re.sub(r"\s+", " ", bruto)


def _dados():
    return {"razao_social": "Empresa XPTO Ltda", "cnpj": "12345678000195",
            "numero_edital": "PE 042/2024", "objeto": "Serviços de TI",
            "orgao": "Prefeitura Exemplo"}


def _parecer(**kw):
    base = {
        "necessita_diligencia": "SIM",
        "documentos_solicitados": [{
            "documento": "Certidão FGTS", "situacao": "vencido",
            "fundamento_legal": "Art. 64, I, Lei 14.133/2021", "prazo_dias": None,
        }],
        "pontos_de_atencao": [],
        "minuta_oficio": "OFÍCIO DE DILIGÊNCIA Nº ____",
        "prazo_resposta_sugerido": None,
        "conclusao": "Necessária a complementação.",
        "base_legal": ["Art. 64, I e II, Lei 14.133/2021"],
        "_documentos_analisados": [],
        "_conferencia_oficio": [],
    }
    base.update(kw)
    return base


class TestPrazo:
    def test_prazo_ausente_nunca_imprime_5(self):
        txt = _texto_do_pdf(relatorio_fid.gerar_pdf(_dados(), "habilitacao", _parecer()))
        assert "5 dias" not in txt
        assert "a fixar" in txt
        assert "não fixa prazo geral" in txt

    def test_prazo_presente_vem_com_ressalva_de_origem(self):
        p = _parecer(prazo_resposta_sugerido=10,
                     _documentos_analisados=[{"arquivo": "edital.pdf", "chars": 900}])
        txt = _texto_do_pdf(relatorio_fid.gerar_pdf(_dados(), "habilitacao", p))
        assert "10 dias" in txt
        assert "confirme na fonte" in txt.lower()
        assert "úteis ou corridos" in txt


class TestLastro:
    def test_sem_documento_anexado_o_aviso_aparece(self):
        txt = _texto_do_pdf(relatorio_fid.gerar_pdf(_dados(), "habilitacao", _parecer()))
        assert "NENHUM DOCUMENTO FOI ANEXADO" in txt

    def test_com_documento_o_manifesto_lista_os_arquivos(self):
        p = _parecer(_documentos_analisados=[{"arquivo": "fgts.pdf", "chars": 4321}])
        txt = _texto_do_pdf(relatorio_fid.gerar_pdf(_dados(), "habilitacao", p))
        assert "fgts.pdf" in txt
        assert "NENHUM DOCUMENTO FOI ANEXADO" not in txt


class TestNaoAvaliado:
    def test_badge_e_corpo_dizem_a_mesma_coisa(self):
        """A lição do Diagnóstico de Integridade: o selo foi corrigido e o corpo
        continuou afirmando o contrário."""
        p = _parecer(necessita_diligencia=ia_fid.RESULTADO_NAO_AVALIADO,
                     documentos_solicitados=[])
        txt = _texto_do_pdf(relatorio_fid.gerar_pdf(_dados(), "habilitacao", p))
        assert "NÃO AVALIADO" in txt
        assert "NÃO conclui pela necessidade nem pela desnecessidade" in txt
        assert "DILIGÊNCIA NECESSÁRIA" not in txt

    def test_divergencia_da_ia_e_impressa(self):
        p = _parecer(_divergencia_ia="NÃO")
        txt = _texto_do_pdf(relatorio_fid.gerar_pdf(_dados(), "habilitacao", p))
        assert "Divergência entre as duas leituras" in txt


class TestConferenciaNoPDF:
    def test_alertas_da_conferencia_saem_no_relatorio(self):
        p = _parecer(_conferencia_oficio=["A minuta fixa prazo sem lastro."])
        txt = _texto_do_pdf(relatorio_fid.gerar_pdf(_dados(), "habilitacao", p))
        assert "Conferência automática da minuta" in txt
        assert "A minuta fixa prazo sem lastro." in txt

    def test_sem_alertas_a_secao_nao_aparece(self):
        txt = _texto_do_pdf(relatorio_fid.gerar_pdf(_dados(), "habilitacao", _parecer()))
        assert "Conferência automática da minuta" not in txt
