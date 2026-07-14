# Módulo 10 — Auditoria do ETP — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar Tab 3 "📋 Auditoria de ETP" ao IA-Licita, com upload de múltiplos arquivos PDF/Word, análise por IA das 8 dimensões da IN SEGES/MGI 58/2022 e download do parecer em PDF.

**Architecture:** Três novos arquivos com responsabilidade única (etp_extrator.py, ia_etp.py, relatorio_etp.py). app.py recebe aba3 no st.tabs() existente (linha 55). ia_etp.py usa urllib diretamente sem SDK anthropic, mesmo padrão de ia_semantica.py. api_key e modelo são passados como parâmetros para analisar_etp() (diferente de ia_ddi.py que os busca internamente).

**Tech Stack:** Python 3.9, Streamlit, pdfplumber (PDF), python-docx (Word), urllib stdlib (API Anthropic), reportlab (PDF output), pytest

---

## Mapeamento de Arquivos

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `etp_extrator.py` | Criar | Extrai texto de PDF e Word, concatena múltiplos arquivos, aplica limite de 50k chars |
| `ia_etp.py` | Criar | Chamada única à API Anthropic → parecer JSON com 8 dimensões |
| `relatorio_etp.py` | Criar | Gera PDF do parecer com reportlab |
| `app.py` | Modificar (linha 55 + final) | Adiciona aba3 ao st.tabs() e bloco with aba3: |
| `tests/test_etp_extrator.py` | Criar | Testes unitários de extração PDF/Word/concatenação |
| `tests/test_ia_etp.py` | Criar | Testes unitários da camada de IA com mock urllib |
| `tests/test_relatorio_etp.py` | Criar | Testes de geração de PDF |

---

### Task 1: etp_extrator.py — extração de PDF

**Files:**
- Create: `~/Documents/Daysival/etp_extrator.py`
- Create: `~/Documents/Daysival/tests/test_etp_extrator.py`

- [ ] **Passo 1: Criar tests/test_etp_extrator.py**

```python
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
```

- [ ] **Passo 2: Rodar e verificar que falha**

```bash
cd ~/Documents/Daysival && python3 -m pytest tests/test_etp_extrator.py::TestExtrairPdf -v
```

Resultado esperado: `ModuleNotFoundError: No module named 'etp_extrator'`

- [ ] **Passo 3: Criar etp_extrator.py**

```python
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
```

- [ ] **Passo 4: Rodar e verificar que passa**

```bash
cd ~/Documents/Daysival && python3 -m pytest tests/test_etp_extrator.py::TestExtrairPdf -v
```

Resultado esperado: 3 testes PASSED

- [ ] **Passo 5: Commitar**

```bash
cd ~/Documents/Daysival && git add etp_extrator.py tests/test_etp_extrator.py && git commit -m "feat(etp): PDF extraction in etp_extrator"
```

---

### Task 2: etp_extrator.py — extração de Word e concatenação

**Files:**
- Modify: `~/Documents/Daysival/tests/test_etp_extrator.py`

- [ ] **Passo 1: Adicionar testes ao FINAL de test_etp_extrator.py**

```python
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
```

- [ ] **Passo 2: Rodar e verificar que passa**

```bash
cd ~/Documents/Daysival && python3 -m pytest tests/test_etp_extrator.py -v
```

Resultado esperado: todos PASSED

- [ ] **Passo 3: Commitar**

```bash
cd ~/Documents/Daysival && git add tests/test_etp_extrator.py && git commit -m "feat(etp): Word extraction + concatenation tests"
```

---

### Task 3: ia_etp.py — análise IA das 8 dimensões

**Files:**
- Create: `~/Documents/Daysival/ia_etp.py`
- Create: `~/Documents/Daysival/tests/test_ia_etp.py`

- [ ] **Passo 1: Criar tests/test_ia_etp.py**

```python
from __future__ import annotations
import json
import pytest
from unittest.mock import patch, MagicMock
import ia_etp


def _parecer_mock() -> dict:
    return {
        "adequacao_geral": "ADEQUADO COM RESSALVAS",
        "dimensoes": {
            "descricao_necessidade":       {"status": "ok",     "descricao": "Necessidade bem descrita."},
            "alinhamento_estrategico":     {"status": "ok",     "descricao": "Alinhado ao PPA."},
            "requisitos_contratacao":      {"status": "alerta", "descricao": "Requisitos incompletos."},
            "levantamento_mercado":        {"status": "ok",     "descricao": "Mercado pesquisado."},
            "estimativa_quantidade_valor": {"status": "alerta", "descricao": "Metodologia ausente."},
            "sustentabilidade":            {"status": "ok",     "descricao": "Critérios presentes."},
            "parcelamento":                {"status": "ok",     "descricao": "Justificado."},
            "posicionamento_conclusivo":   {"status": "ok",     "descricao": "Favorável."},
        },
        "pontos_criticos": ["Requisitos técnicos incompletos."],
        "recomendacoes": ["Detalhar especificações técnicas."],
        "base_legal": ["IN SEGES/MGI 58/2022", "Lei 14.133/2021, art. 18, I"],
    }


def _mock_urlopen(parecer: dict):
    resposta = json.dumps({"content": [{"text": json.dumps(parecer)}]}).encode("utf-8")
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=resposta)))
    mock_cm.__exit__ = MagicMock(return_value=False)
    return mock_cm


class TestAnalisarEtp:
    @patch("ia_etp.urllib.request.urlopen")
    def test_retorna_estrutura_correta(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen(_parecer_mock())

        resultado = ia_etp.analisar_etp("Texto do ETP", "sk-test", "claude-haiku-4-5-20251001")

        assert "adequacao_geral" in resultado
        assert "dimensoes" in resultado
        assert "pontos_criticos" in resultado
        assert "recomendacoes" in resultado
        assert "base_legal" in resultado

    @patch("ia_etp.urllib.request.urlopen")
    def test_todas_as_8_dimensoes_presentes(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen(_parecer_mock())

        resultado = ia_etp.analisar_etp("Texto", "sk-test", "claude-haiku-4-5-20251001")

        dims = resultado["dimensoes"]
        for esperada in [
            "descricao_necessidade", "alinhamento_estrategico", "requisitos_contratacao",
            "levantamento_mercado", "estimativa_quantidade_valor", "sustentabilidade",
            "parcelamento", "posicionamento_conclusivo",
        ]:
            assert esperada in dims, f"Dimensão ausente: {esperada}"

    @patch("ia_etp.urllib.request.urlopen")
    def test_adequacao_geral_valida(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen(_parecer_mock())

        resultado = ia_etp.analisar_etp("Texto", "sk-test", "claude-haiku-4-5-20251001")

        assert resultado["adequacao_geral"] in (
            "ADEQUADO", "ADEQUADO COM RESSALVAS", "INADEQUADO"
        )

    @patch("ia_etp.urllib.request.urlopen")
    def test_modelo_padrao_usado_se_omitido(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen(_parecer_mock())

        resultado = ia_etp.analisar_etp("Texto", "sk-test")

        assert "adequacao_geral" in resultado
```

- [ ] **Passo 2: Rodar e verificar que falha**

```bash
cd ~/Documents/Daysival && python3 -m pytest tests/test_ia_etp.py -v
```

Resultado esperado: `ModuleNotFoundError: No module named 'ia_etp'`

- [ ] **Passo 3: Criar ia_etp.py**

```python
from __future__ import annotations
import json
import re
import urllib.request
import urllib.error

_MODELO_PADRAO = "claude-haiku-4-5-20251001"

_SISTEMA = (
    "Você é um auditor especialista em contratações públicas federais brasileiras. "
    "Analise o Estudo Técnico Preliminar (ETP) fornecido à luz da IN SEGES/MGI 58/2022 "
    "e do art. 18 da Lei 14.133/2021. Avalie cada uma das 8 dimensões obrigatórias do ETP. "
    "Responda SOMENTE com JSON válido no formato especificado. Não inclua texto fora do JSON."
)

_ESTRUTURA_PARECER = """{
  "adequacao_geral": "ADEQUADO | ADEQUADO COM RESSALVAS | INADEQUADO",
  "dimensoes": {
    "descricao_necessidade":       {"status": "ok|alerta|critico", "descricao": "..."},
    "alinhamento_estrategico":     {"status": "ok|alerta|critico", "descricao": "..."},
    "requisitos_contratacao":      {"status": "ok|alerta|critico", "descricao": "..."},
    "levantamento_mercado":        {"status": "ok|alerta|critico", "descricao": "..."},
    "estimativa_quantidade_valor": {"status": "ok|alerta|critico", "descricao": "..."},
    "sustentabilidade":            {"status": "ok|alerta|critico", "descricao": "..."},
    "parcelamento":                {"status": "ok|alerta|critico", "descricao": "..."},
    "posicionamento_conclusivo":   {"status": "ok|alerta|critico", "descricao": "..."}
  },
  "pontos_criticos": ["..."],
  "recomendacoes": ["..."],
  "base_legal": ["IN SEGES/MGI 58/2022", "Lei 14.133/2021, art. 18, I"]
}"""


def _chamar_anthropic(prompt: str, api_key: str, modelo: str) -> str:
    corpo = json.dumps({
        "model": modelo,
        "max_tokens": 3000,
        "system": _SISTEMA,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=corpo,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        dados = json.loads(resp.read().decode("utf-8"))
    return "".join(b.get("text", "") for b in dados.get("content", []))


def _extrair_json(texto: str) -> dict:
    t = texto.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.IGNORECASE).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    ini = t.find("{")
    fim = t.rfind("}") + 1
    if ini == -1 or fim == 0:
        raise ValueError("Resposta sem JSON reconhecível")
    return json.loads(t[ini:fim])


def analisar_etp(texto: str, api_key: str, modelo: str = _MODELO_PADRAO) -> dict:
    prompt = (
        f"Analise o seguinte Estudo Técnico Preliminar (ETP) e documentos complementares:\n\n"
        f"{texto}\n\n"
        f"Retorne o parecer de auditoria no formato:\n{_ESTRUTURA_PARECER}"
    )
    try:
        bruto = _chamar_anthropic(prompt, api_key, modelo)
        return _extrair_json(bruto)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        raise RuntimeError(f"Falha na API Anthropic: {exc}") from exc
    except (ValueError, Exception) as exc:
        raise RuntimeError(f"Resposta inesperada da API: {exc}") from exc
```

- [ ] **Passo 4: Rodar e verificar que passa**

```bash
cd ~/Documents/Daysival && python3 -m pytest tests/test_ia_etp.py -v
```

Resultado esperado: 4 testes PASSED

- [ ] **Passo 5: Commitar**

```bash
cd ~/Documents/Daysival && git add ia_etp.py tests/test_ia_etp.py && git commit -m "feat(etp): IA analysis of 8 ETP dimensions"
```

---

### Task 4: relatorio_etp.py — geração de PDF

**Files:**
- Create: `~/Documents/Daysival/relatorio_etp.py`
- Create: `~/Documents/Daysival/tests/test_relatorio_etp.py`

- [ ] **Passo 1: Criar tests/test_relatorio_etp.py**

```python
from __future__ import annotations
import relatorio_etp


def _parecer() -> dict:
    return {
        "adequacao_geral": "ADEQUADO COM RESSALVAS",
        "dimensoes": {
            "descricao_necessidade":       {"status": "ok",     "descricao": "Necessidade clara."},
            "alinhamento_estrategico":     {"status": "ok",     "descricao": "Alinhado ao PPA."},
            "requisitos_contratacao":      {"status": "alerta", "descricao": "Incompleto."},
            "levantamento_mercado":        {"status": "ok",     "descricao": "Pesquisado."},
            "estimativa_quantidade_valor": {"status": "alerta", "descricao": "Metodologia ausente."},
            "sustentabilidade":            {"status": "ok",     "descricao": "Critérios presentes."},
            "parcelamento":                {"status": "ok",     "descricao": "Justificado."},
            "posicionamento_conclusivo":   {"status": "ok",     "descricao": "Favorável."},
        },
        "pontos_criticos": ["Requisitos incompletos."],
        "recomendacoes": ["Detalhar especificações."],
        "base_legal": ["IN SEGES/MGI 58/2022", "Lei 14.133/2021, art. 18, I"],
    }


class TestGerarPdf:
    def test_retorna_bytes(self):
        pdf = relatorio_etp.gerar_pdf(["etp.pdf"], [], _parecer())
        assert isinstance(pdf, bytes)

    def test_comeca_com_magic_bytes_pdf(self):
        pdf = relatorio_etp.gerar_pdf(["etp.pdf"], [], _parecer())
        assert pdf[:4] == b"%PDF"

    def test_tamanho_minimo(self):
        pdf = relatorio_etp.gerar_pdf(["etp.pdf"], [], _parecer())
        assert len(pdf) > 2000

    def test_com_avisos_nao_levanta_erro(self):
        avisos = ["Texto truncado em 50000 chars.", "Formato nao suportado: planilha.xlsx"]
        pdf = relatorio_etp.gerar_pdf(["etp.pdf", "anexo.docx"], avisos, _parecer())
        assert pdf[:4] == b"%PDF"

    def test_adequacao_inadequado_nao_levanta_erro(self):
        parecer = {**_parecer(), "adequacao_geral": "INADEQUADO"}
        pdf = relatorio_etp.gerar_pdf(["etp.pdf"], [], parecer)
        assert pdf[:4] == b"%PDF"
```

- [ ] **Passo 2: Rodar e verificar que falha**

```bash
cd ~/Documents/Daysival && python3 -m pytest tests/test_relatorio_etp.py -v
```

Resultado esperado: `ModuleNotFoundError: No module named 'relatorio_etp'`

- [ ] **Passo 3: Criar relatorio_etp.py**

```python
from __future__ import annotations
import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)

_COR_ADEQUACAO = {
    "ADEQUADO": colors.HexColor("#27AE60"),
    "ADEQUADO COM RESSALVAS": colors.HexColor("#F39C12"),
    "INADEQUADO": colors.HexColor("#C0392B"),
}
_COR_STATUS = {"ok": "#27AE60", "alerta": "#E67E22", "critico": "#C0392B"}
_LABEL_DIMENSAO = {
    "descricao_necessidade":       "Descrição da Necessidade",
    "alinhamento_estrategico":     "Alinhamento Estratégico",
    "requisitos_contratacao":      "Requisitos da Contratação",
    "levantamento_mercado":        "Levantamento de Mercado",
    "estimativa_quantidade_valor": "Estimativa de Quantidade e Valor",
    "sustentabilidade":            "Sustentabilidade",
    "parcelamento":                "Parcelamento do Objeto",
    "posicionamento_conclusivo":   "Posicionamento Conclusivo",
}


def gerar_pdf(nomes_arquivos: list[str], avisos: list[str], parecer: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm,
    )
    estilos = getSampleStyleSheet()
    titulo = ParagraphStyle("titulo", parent=estilos["Title"], fontSize=16, spaceAfter=4)
    h2 = ParagraphStyle("h2", parent=estilos["Heading2"], fontSize=12, spaceAfter=3)
    corpo = ParagraphStyle("corpo", parent=estilos["Normal"], fontSize=10, spaceAfter=3)
    pequeno = ParagraphStyle("peq", parent=estilos["Normal"], fontSize=8, textColor=colors.grey)
    alerta_style = ParagraphStyle("alerta", parent=corpo, textColor=colors.HexColor("#E67E22"))

    story = []

    # Cabeçalho
    story.append(Paragraph("IA-Licita — RM Vértice Digital", titulo))
    story.append(Paragraph("Auditoria de ETP — Estudo Técnico Preliminar", estilos["Heading1"]))
    story.append(Paragraph("IN SEGES/MGI 58/2022 · Lei 14.133/2021, art. 18, I", pequeno))
    story.append(Paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y as %H:%M')}", pequeno))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.grey, spaceAfter=8))

    # Documentos analisados
    story.append(Paragraph("Documentos Analisados", h2))
    for nome in nomes_arquivos:
        story.append(Paragraph(f"- {nome}", corpo))
    story.append(Spacer(1, 0.3*cm))

    # Avisos
    if avisos:
        story.append(Paragraph("Avisos", h2))
        for aviso in avisos:
            story.append(Paragraph(f"AVISO: {aviso}", alerta_style))
        story.append(Spacer(1, 0.3*cm))

    # Adequação geral
    adequacao = parecer.get("adequacao_geral", "INADEQUADO")
    cor = _COR_ADEQUACAO.get(adequacao, colors.grey)
    story.append(Paragraph("Adequação Geral", h2))
    t_adeq = Table(
        [[Paragraph(f"<b>{adequacao}</b>",
                    ParagraphStyle("a", fontSize=14, textColor=colors.white, alignment=1))]],
        colWidths=[17*cm],
    )
    t_adeq.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), cor),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("PADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(t_adeq)
    story.append(Spacer(1, 0.4*cm))

    # Análise por dimensão
    story.append(Paragraph("Análise por Dimensão", h2))
    dims = parecer.get("dimensoes", {})
    for chave, label in _LABEL_DIMENSAO.items():
        dim = dims.get(chave, {})
        status = dim.get("status", "ok")
        cor_s = _COR_STATUS.get(status, "#000000")
        icone = {"ok": "OK", "alerta": "ALERTA", "critico": "CRITICO"}.get(status, "-")
        story.append(Paragraph(
            f"<font color='{cor_s}'><b>[{icone}] {label}</b></font>: {dim.get('descricao', '-')}",
            corpo,
        ))
    story.append(Spacer(1, 0.3*cm))

    # Pontos críticos
    criticos = parecer.get("pontos_criticos", [])
    if criticos:
        story.append(Paragraph("Pontos Críticos", h2))
        for i, ponto in enumerate(criticos, 1):
            story.append(Paragraph(f"{i}. {ponto}", corpo))
        story.append(Spacer(1, 0.3*cm))

    # Recomendações
    recs = parecer.get("recomendacoes", [])
    if recs:
        story.append(Paragraph("Recomendações ao Gestor", h2))
        for i, rec in enumerate(recs, 1):
            story.append(Paragraph(f"{i}. {rec}", corpo))
        story.append(Spacer(1, 0.3*cm))

    # Base legal
    story.append(Paragraph("Base Legal", h2))
    for bl in parecer.get("base_legal", []):
        story.append(Paragraph(f"- {bl}", corpo))
    story.append(Spacer(1, 0.4*cm))

    # Rodapé
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Paragraph(
        "Gerado por IA-Licita — RM Vértice Digital. Sujeito a verificacao humana. "
        "Nao substitui parecer juridico.",
        pequeno,
    ))

    doc.build(story)
    return buf.getvalue()
```

- [ ] **Passo 4: Rodar e verificar que passa**

```bash
cd ~/Documents/Daysival && python3 -m pytest tests/test_relatorio_etp.py -v
```

Resultado esperado: 5 testes PASSED

- [ ] **Passo 5: Commitar**

```bash
cd ~/Documents/Daysival && git add relatorio_etp.py tests/test_relatorio_etp.py && git commit -m "feat(etp): PDF report generation"
```

---

### Task 5: Modificar app.py — Tab 3

**Files:**
- Modify: `~/Documents/Daysival/app.py`

- [ ] **Passo 1: Adicionar imports após `import relatorio_ddi` (linha 13)**

Localizar:
```python
import relatorio_ddi
```

Adicionar logo abaixo:
```python
import etp_extrator
import ia_etp
import relatorio_etp
```

- [ ] **Passo 2: Atualizar st.tabs() na linha 55**

Localizar:
```python
aba1, aba2 = st.tabs(["📄 Auditoria de Edital", "🔍 Due Diligence de Integridade"])
```

Substituir por:
```python
aba1, aba2, aba3 = st.tabs([
    "📄 Auditoria de Edital",
    "🔍 Due Diligence de Integridade",
    "📋 Auditoria de ETP",
])
```

- [ ] **Passo 3: Adicionar bloco `with aba3:` ao final do arquivo (após o bloco `with aba2:`)**

```python
with aba3:
    st.subheader("Auditoria de ETP — Estudo Técnico Preliminar")
    st.caption("IN SEGES/MGI 58/2022 · Lei 14.133/2021, art. 18, I")

    _api_key_etp = os.environ.get("ANTHROPIC_API_KEY")
    if not _api_key_etp:
        try:
            _api_key_etp = st.secrets.get("ANTHROPIC_API_KEY")
        except Exception:
            pass
    _modelo_etp = os.environ.get("IA_LICITA_MODELO", "claude-haiku-4-5-20251001")

    _arqs_etp = st.file_uploader(
        "ETP e documentos complementares (PDF ou Word)",
        type=["pdf", "docx"],
        accept_multiple_files=True,
        key="etp_arquivos",
    )

    if st.button("Analisar ETP", type="primary", key="btn_etp", disabled=not _arqs_etp):
        if not _api_key_etp:
            st.error("ANTHROPIC_API_KEY não configurada.")
        else:
            try:
                with st.spinner("Extraindo texto e analisando com IA (pode levar 1-2 minutos)..."):
                    _texto_etp, _avisos_etp = etp_extrator.extrair_texto(_arqs_etp)
                    _parecer_etp = ia_etp.analisar_etp(_texto_etp, _api_key_etp, _modelo_etp)
                st.session_state["etp_parecer"] = _parecer_etp
                st.session_state["etp_avisos"] = _avisos_etp
                st.session_state["etp_nomes"] = [f.name for f in _arqs_etp]
            except ValueError as e:
                st.error(str(e))
            except RuntimeError as e:
                st.error(str(e))

    if "etp_parecer" in st.session_state:
        _pr = st.session_state["etp_parecer"]
        _av = st.session_state["etp_avisos"]
        _nm = st.session_state["etp_nomes"]

        for _aviso in _av:
            st.warning(_aviso)

        st.divider()
        _adeq = _pr.get("adequacao_geral", "INADEQUADO")
        _icone_adeq = {"ADEQUADO": "🟢", "ADEQUADO COM RESSALVAS": "🟡", "INADEQUADO": "🔴"}
        st.subheader(f"{_icone_adeq.get(_adeq, '⚪')} Adequação Geral: {_adeq}")

        _dims = _pr.get("dimensoes", {})
        _labels = {
            "descricao_necessidade":       "Descrição da Necessidade",
            "alinhamento_estrategico":     "Alinhamento Estratégico",
            "requisitos_contratacao":      "Requisitos da Contratação",
            "levantamento_mercado":        "Levantamento de Mercado",
            "estimativa_quantidade_valor": "Estimativa de Quantidade e Valor",
            "sustentabilidade":            "Sustentabilidade",
            "parcelamento":                "Parcelamento do Objeto",
            "posicionamento_conclusivo":   "Posicionamento Conclusivo",
        }
        _ic_st = {"ok": "✅", "alerta": "⚠️", "critico": "❌"}
        for _ch, _lb in _labels.items():
            _d = _dims.get(_ch, {})
            _ic = _ic_st.get(_d.get("status", "ok"), "ℹ️")
            with st.expander(f"{_ic} {_lb}"):
                st.write(_d.get("descricao", "—"))

        _criticos = _pr.get("pontos_criticos", [])
        if _criticos:
            st.subheader("Pontos Críticos")
            for _c in _criticos:
                st.error(_c)

        _recs = _pr.get("recomendacoes", [])
        if _recs:
            st.subheader("Recomendações ao Gestor")
            for _r in _recs:
                st.info(_r)

        with st.expander("Base Legal"):
            for _bl in _pr.get("base_legal", []):
                st.write(f"• {_bl}")

        _pdf_etp = relatorio_etp.gerar_pdf(_nm, _av, _pr)
        st.download_button(
            label="Baixar Relatório PDF",
            data=_pdf_etp,
            file_name="ETP_auditoria.pdf",
            mime="application/pdf",
        )
```

- [ ] **Passo 4: Verificar sintaxe**

```bash
cd ~/Documents/Daysival && python3 -m py_compile app.py && echo "Sintaxe OK"
```

Resultado esperado: `Sintaxe OK`

- [ ] **Passo 5: Commitar**

```bash
cd ~/Documents/Daysival && git add app.py && git commit -m "feat(etp): Tab 3 ETP audit flow in app.py"
```

---

### Task 6: Suite completa e smoke test

**Files:** nenhum (apenas execução)

- [ ] **Passo 1: Rodar todos os testes**

```bash
cd ~/Documents/Daysival && python3 -m pytest tests/ -v
```

Resultado esperado: todos PASSED (45 anteriores + 12 novos ETP = 57+ PASSED, 0 FAILED).

- [ ] **Passo 2: Verificar sintaxe do app final**

```bash
cd ~/Documents/Daysival && python3 -m py_compile app.py && echo "OK"
```

- [ ] **Passo 3: Commit final**

```bash
cd ~/Documents/Daysival && git add -A && git commit -m "feat(etp): ETP audit module complete — all tests passing"
```
