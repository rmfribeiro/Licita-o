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

    def test_limite_acompanha_o_das_chamadas_de_ia(self):
        """O limite da LEITURA nao pode ser menor que o do envio ao modelo.

        Era 50.000 aqui contra 300.000 em ia_utils: o texto chegava cortado aos
        modulos e o limite de la nunca era alcancado — 63% de um TR real de obra
        (136.556 caracteres) era descartado antes de qualquer analise.
        """
        import ia_utils
        assert etp_extrator._LIMITE_CHARS >= ia_utils.LIMITE_DOC_PADRAO

    def test_truncagem_avisa_quanto_ficou_de_fora(self):
        """Cortar e aceitavel; cortar em silencio, nao. O aviso precisa dizer o
        tamanho real e a proporcao descartada, para o usuario decidir se confia
        no parecer."""
        original = etp_extrator._extrair_docx
        etp_extrator._extrair_docx = lambda c: c.decode()
        try:
            grande = "x" * (etp_extrator._LIMITE_CHARS + 100_000)
            texto, avisos = etp_extrator.extrair_texto([MockFile("t.docx", grande.encode())])
            assert len(texto) == etp_extrator._LIMITE_CHARS
            assert avisos and "NÃO foram analisados" in avisos[0]
            # o aviso informa quanto ficou de fora (o total inclui o cabeçalho
            # "[ARQUIVO: ...]", por isso a comparação é por ordem de grandeza)
            assert "100." in avisos[0] and "%" in avisos[0]
            # e a frase final não pode ter sido estragada pela formatação numérica
            assert "cada uma, ou envie" in avisos[0]
        finally:
            etp_extrator._extrair_docx = original

    def test_documento_dentro_do_limite_nao_e_cortado(self):
        original = etp_extrator._extrair_docx
        etp_extrator._extrair_docx = lambda c: c.decode()
        try:
            # tamanho de um TR real de obra: 136.556 caracteres
            texto, avisos = etp_extrator.extrair_texto(
                [MockFile("tr.docx", ("y" * 136_556).encode())]
            )
            assert len(texto) >= 136_556
            assert avisos == []
        finally:
            etp_extrator._extrair_docx = original
