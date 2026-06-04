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
