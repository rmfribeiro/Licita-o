from __future__ import annotations
import io
import pdfplumber
from docx import Document

_LIMITE_CHARS = 50_000


def _extrair_pdf(conteudo: bytes) -> str:
    texto = ""
    try:
        with pdfplumber.open(io.BytesIO(conteudo)) as pdf:
            for page in pdf.pages:
                texto += page.extract_text() or ""
    except Exception:
        pass
    return texto


def _extrair_docx(conteudo: bytes) -> str:
    texto = ""
    try:
        doc = Document(io.BytesIO(conteudo))
        for para in doc.paragraphs:
            if para.text.strip():
                texto += para.text + "\n"
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        texto += cell.text + "\n"
    except Exception:
        pass
    return texto


def extrair_texto(arquivos: list) -> tuple[str, list[str]]:
    partes: list[str] = []
    avisos: list[str] = []

    for arquivo in arquivos:
        nome = arquivo.name
        conteudo = arquivo.read() if hasattr(arquivo, "read") else arquivo.getvalue()
        ext = nome.lower().rsplit(".", 1)[-1] if "." in nome else ""

        if ext == "pdf":
            texto = _extrair_pdf(conteudo)
        elif ext == "docx":
            texto = _extrair_docx(conteudo)
        else:
            avisos.append(f"Formato não suportado ignorado: {nome}")
            continue

        if not texto.strip():
            avisos.append(f"Sem texto extraível: {nome}")
            continue

        partes.append(f"[ARQUIVO: {nome}]\n{texto.strip()}")

    if not partes:
        raise ValueError("Nenhum texto extraível nos arquivos enviados.")

    concatenado = "\n\n".join(partes)

    if len(concatenado) > _LIMITE_CHARS:
        concatenado = concatenado[:_LIMITE_CHARS]
        avisos.append(
            f"Texto truncado em {_LIMITE_CHARS} caracteres. "
            "Documentos muito extensos podem ter conteúdo não analisado."
        )

    return concatenado, avisos
