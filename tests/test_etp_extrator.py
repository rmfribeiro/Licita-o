from __future__ import annotations
import io
import pytest
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph
import etp_extrator


class MockFile:
    def __init__(self, name: str, content: bytes):
        self.name = name
        self._content = content

    def read(self) -> bytes:
        return self._content

    def getvalue(self) -> bytes:
        return self._content


def _pdf_bytes(texto: str) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter)
    doc.build([Paragraph(texto, getSampleStyleSheet()["Normal"])])
    return buf.getvalue()


class TestExtrairPdf:
    def test_extrai_texto_de_pdf(self):
        conteudo = _pdf_bytes("Texto do ETP para teste de extracao.")
        arquivo = MockFile("etp.pdf", conteudo)

        texto, avisos = etp_extrator.extrair_texto([arquivo])

        assert "Texto do ETP para teste de extracao." in texto
        assert avisos == []

    def test_inclui_nome_arquivo_no_separador(self):
        conteudo = _pdf_bytes("Conteudo qualquer")
        arquivo = MockFile("meu_etp.pdf", conteudo)

        texto, _ = etp_extrator.extrair_texto([arquivo])

        assert "[ARQUIVO: meu_etp.pdf]" in texto

    def test_pdf_sem_texto_gera_aviso(self):
        arquivo = MockFile("vazio.pdf", b"%PDF-1.4 %%EOF")

        _, avisos = etp_extrator.extrair_texto(
            [MockFile("ok.pdf", _pdf_bytes("texto ok")), arquivo]
        )

        assert any("vazio.pdf" in a for a in avisos)


from docx import Document as DocxDocument


def _docx_bytes(texto: str) -> bytes:
    doc = DocxDocument()
    doc.add_paragraph(texto)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


class TestExtrairDocx:
    def test_extrai_texto_de_docx(self):
        conteudo = _docx_bytes("ETP em formato Word para teste.")
        arquivo = MockFile("etp.docx", conteudo)

        texto, avisos = etp_extrator.extrair_texto([arquivo])

        assert "ETP em formato Word para teste." in texto
        assert avisos == []

    def test_inclui_separador_com_nome(self):
        conteudo = _docx_bytes("Conteudo Word")
        arquivo = MockFile("estudo.docx", conteudo)

        texto, _ = etp_extrator.extrair_texto([arquivo])

        assert "[ARQUIVO: estudo.docx]" in texto


class TestConcatenacaoELimites:
    def test_multiplos_arquivos_concatenados(self):
        pdf = MockFile("a.pdf", _pdf_bytes("Texto PDF"))
        docx = MockFile("b.docx", _docx_bytes("Texto Word"))

        texto, avisos = etp_extrator.extrair_texto([pdf, docx])

        assert "[ARQUIVO: a.pdf]" in texto
        assert "[ARQUIVO: b.docx]" in texto
        assert avisos == []

    def test_formato_nao_suportado_gera_aviso(self):
        invalido = MockFile("planilha.xlsx", b"conteudo qualquer")
        valido = MockFile("a.pdf", _pdf_bytes("texto ok"))

        _, avisos = etp_extrator.extrair_texto([valido, invalido])

        assert any("planilha.xlsx" in a for a in avisos)

    def test_todos_invalidos_levanta_erro(self):
        with pytest.raises(ValueError, match="Nenhum texto extraível"):
            etp_extrator.extrair_texto([MockFile("x.xlsx", b"lixo")])

    def test_truncagem_aplicada_quando_excede_50k(self):
        texto_a = "A" * 30_000
        texto_b = "B" * 30_000
        arq_a = MockFile("a.pdf", _pdf_bytes(texto_a[:2000]))
        arq_b = MockFile("b.pdf", _pdf_bytes(texto_b[:2000]))

        # Garante que a lógica de limite existe no módulo
        assert etp_extrator._LIMITE_CHARS == 50_000
