# DDI — Due Diligence de Integridade — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar ao IA-Licita o Módulo 2 — DDI como Tab 2 no app.py, com consulta automática a Receita Federal, CEIS, CNEP e Empresa Pró-Ética, FID simplificado de 5 perguntas, parecer IA multidimensional fundamentado no arcabouço normativo completo e relatório PDF para download.

**Architecture:** Três novos arquivos com responsabilidade única (ddi_consultas.py, ia_ddi.py, relatorio_ddi.py) e modificação mínima do app.py — conteúdo atual envolvido em Tab 1 sem nenhuma alteração de lógica, Tab 2 adicionada com fluxo de 3 etapas. ia_ddi.py usa urllib diretamente (mesmo padrão de ia_semantica.py, sem SDK anthropic).

**Tech Stack:** Python 3.x, Streamlit, urllib (stdlib), requests (nova dep), reportlab (existente), pytest (testes)

---

## Mapeamento de Arquivos

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `requirements.txt` | Modificar | Adicionar `requests>=2.31` e `pytest>=8.0` |
| `ddi_consultas.py` | Criar | Validação CNPJ, consultas API, lógica grande_vulto |
| `ia_ddi.py` | Criar | Regras de piso + prompt + chamada Anthropic via urllib |
| `relatorio_ddi.py` | Criar | Geração de PDF com reportlab |
| `app.py` | Modificar (mínimo) | st.tabs(), imports DDI, Tab 2 |
| `tests/__init__.py` | Criar | Marca como pacote pytest |
| `tests/test_ddi_consultas.py` | Criar | Testes unitários da camada de dados |
| `tests/test_ia_ddi.py` | Criar | Testes unitários da camada de IA |
| `tests/test_relatorio_ddi.py` | Criar | Testes da geração de PDF |

---

### Task 1: Dependências e estrutura de testes

**Files:**
- Modify: `requirements.txt`
- Create: `tests/__init__.py`

- [ ] **Passo 1: Atualizar requirements.txt**

Conteúdo final:
```
streamlit>=1.30
pdfplumber>=0.10
python-docx>=1.1
reportlab>=4.0
requests>=2.31
pytest>=8.0
```

- [ ] **Passo 2: Instalar novas dependências**

```bash
pip install requests pytest
```

Resultado esperado: `Successfully installed requests-...` e `Successfully installed pytest-...`

- [ ] **Passo 3: Criar diretório e arquivo de init de testes**

```bash
mkdir -p ~/Documents/Daysival/tests
touch ~/Documents/Daysival/tests/__init__.py
```

- [ ] **Passo 4: Verificar pytest**

```bash
cd ~/Documents/Daysival && pytest --version
```

Resultado esperado: `pytest 8.x.x`

- [ ] **Passo 5: Commitar**

```bash
git add requirements.txt tests/__init__.py
git commit -m "chore: add requests + pytest, create tests dir"
```

---

### Task 2: Validação de CNPJ em ddi_consultas.py

**Files:**
- Create: `ddi_consultas.py`
- Create: `tests/test_ddi_consultas.py`

- [ ] **Passo 1: Escrever os testes que falham**

Criar `tests/test_ddi_consultas.py`:
```python
import pytest
import ddi_consultas


class TestValidarCnpj:
    def test_cnpj_valido(self):
        assert ddi_consultas._validar_cnpj("11222333000181") is True

    def test_cnpj_com_mascara(self):
        assert ddi_consultas._validar_cnpj("11.222.333/0001-81") is True

    def test_cnpj_digitos_errados(self):
        assert ddi_consultas._validar_cnpj("11222333000100") is False

    def test_cnpj_todos_iguais(self):
        assert ddi_consultas._validar_cnpj("11111111111111") is False

    def test_cnpj_curto(self):
        assert ddi_consultas._validar_cnpj("1234567") is False

    def test_cnpj_vazio(self):
        assert ddi_consultas._validar_cnpj("") is False
```

- [ ] **Passo 2: Rodar e verificar que falha**

```bash
cd ~/Documents/Daysival && pytest tests/test_ddi_consultas.py -v
```

Resultado esperado: `ModuleNotFoundError: No module named 'ddi_consultas'`

- [ ] **Passo 3: Criar ddi_consultas.py com validação**

Criar `ddi_consultas.py`:
```python
import re
import os
import requests
import streamlit as st

_TIMEOUT = 10
_GRANDE_VULTO_LIMITE = 239_000_000.0
_PRO_ETICA_URL = (
    "https://www.gov.br/cgu/pt-br/assuntos/etica-e-integridade"
    "/empresa-pro-etica/lista-das-empresas-pro-etica"
)


def _get_cgu_key() -> str | None:
    chave = os.environ.get("CGU_API_KEY")
    if chave:
        return chave
    try:
        return st.secrets.get("CGU_API_KEY")
    except Exception:
        return None


def _validar_cnpj(cnpj: str) -> bool:
    cnpj = re.sub(r'\D', '', cnpj)
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(cnpj[i]) * pesos1[i] for i in range(12))
    d1 = 0 if soma % 11 < 2 else 11 - soma % 11
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(cnpj[i]) * pesos2[i] for i in range(13))
    d2 = 0 if soma % 11 < 2 else 11 - soma % 11
    return int(cnpj[12]) == d1 and int(cnpj[13]) == d2


def _e_grande_vulto(valor: float) -> bool:
    return valor > _GRANDE_VULTO_LIMITE


def _buscar_receita(cnpj: str) -> dict | None:
    pass


def _buscar_ceis(cnpj: str) -> list:
    pass


def _buscar_cnep(cnpj: str) -> list:
    pass


def _verificar_pro_etica(cnpj: str) -> bool | None:
    pass


def consultar(cnpj: str, valor_contrato: float) -> dict:
    pass
```

- [ ] **Passo 4: Rodar e verificar que passa**

```bash
cd ~/Documents/Daysival && pytest tests/test_ddi_consultas.py::TestValidarCnpj -v
```

Resultado esperado: 6 testes PASSED

- [ ] **Passo 5: Commitar**

```bash
git add ddi_consultas.py tests/test_ddi_consultas.py
git commit -m "feat(ddi): CNPJ validation + module skeleton"
```

---

### Task 3: Integração com Receita Federal

**Files:**
- Modify: `ddi_consultas.py`
- Modify: `tests/test_ddi_consultas.py`

- [ ] **Passo 1: Adicionar testes ao final de test_ddi_consultas.py**

```python
from unittest.mock import patch


class TestBuscarReceita:
    @patch('ddi_consultas.requests.get')
    def test_empresa_ativa(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "razao_social": "EMPRESA TESTE LTDA",
            "descricao_situacao_cadastral": "ATIVA",
            "descricao_porte": "MICRO EMPRESA",
            "cnae_fiscal_descricao": "Desenvolvimento de software",
            "data_inicio_atividade": "2010-01-15",
            "qsa": [{"nome_socio": "FULANO DA SILVA", "cargo": "SÓCIO-ADMINISTRADOR"}],
        }

        result = ddi_consultas._buscar_receita("11222333000181")

        assert result["razao_social"] == "EMPRESA TESTE LTDA"
        assert result["situacao"] == "ATIVA"
        assert result["porte"] == "MICRO EMPRESA"
        assert result["socios"][0]["nome"] == "FULANO DA SILVA"

    @patch('ddi_consultas.requests.get')
    def test_timeout_retorna_none(self, mock_get):
        import requests as req_lib
        mock_get.side_effect = req_lib.exceptions.Timeout()

        result = ddi_consultas._buscar_receita("11222333000181")

        assert result is None

    @patch('ddi_consultas.requests.get')
    def test_status_404_retorna_none(self, mock_get):
        mock_get.return_value.status_code = 404

        result = ddi_consultas._buscar_receita("11222333000181")

        assert result is None
```

- [ ] **Passo 2: Rodar e verificar que falha**

```bash
cd ~/Documents/Daysival && pytest tests/test_ddi_consultas.py::TestBuscarReceita -v
```

Resultado esperado: FAILED — `_buscar_receita` retorna None para todos

- [ ] **Passo 3: Implementar _buscar_receita em ddi_consultas.py**

Substituir o `pass` de `_buscar_receita`:
```python
def _buscar_receita(cnpj: str) -> dict | None:
    try:
        resp = requests.get(
            f"https://publica.cnpj.ws/cnpj/{cnpj}",
            timeout=_TIMEOUT,
            headers={"Accept": "application/json"},
        )
        if resp.status_code != 200:
            return None
        d = resp.json()
        return {
            "razao_social": d.get("razao_social", ""),
            "nome_fantasia": d.get("nome_fantasia", ""),
            "situacao": d.get("descricao_situacao_cadastral", ""),
            "porte": d.get("descricao_porte", ""),
            "cnae": d.get("cnae_fiscal_descricao", ""),
            "data_abertura": d.get("data_inicio_atividade", ""),
            "socios": [
                {"nome": s.get("nome_socio", ""), "cargo": s.get("cargo", "")}
                for s in d.get("qsa", [])
            ],
        }
    except requests.exceptions.RequestException:
        return None
```

- [ ] **Passo 4: Rodar e verificar que passa**

```bash
cd ~/Documents/Daysival && pytest tests/test_ddi_consultas.py::TestBuscarReceita -v
```

Resultado esperado: 3 testes PASSED

- [ ] **Passo 5: Commitar**

```bash
git add ddi_consultas.py tests/test_ddi_consultas.py
git commit -m "feat(ddi): Receita Federal integration"
```

---

### Task 4: Integração com CEIS

**Files:**
- Modify: `ddi_consultas.py`
- Modify: `tests/test_ddi_consultas.py`

- [ ] **Passo 1: Adicionar testes ao final de test_ddi_consultas.py**

```python
class TestBuscarCeis:
    @patch('ddi_consultas.requests.get')
    def test_com_sancao_ativa(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = [{
            "nomeInfrator": "EMPRESA TESTE LTDA",
            "orgaoSancionador": {"nome": "CGU"},
            "dataInicioSancao": "2023-01-01",
            "dataFimSancao": "2025-12-31",
            "situacaoAtual": "Ativo",
            "fundamentacaoLegal": "Lei 8.666/93, art. 87",
        }]

        result = ddi_consultas._buscar_ceis("11222333000181")

        assert len(result) == 1
        assert result[0]["situacaoAtual"] == "Ativo"
        assert result[0]["orgaoSancionador"] == "CGU"

    @patch('ddi_consultas.requests.get')
    def test_sem_sancao_retorna_lista_vazia(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = []

        result = ddi_consultas._buscar_ceis("11222333000181")

        assert result == []

    @patch('ddi_consultas._get_cgu_key', return_value=None)
    def test_sem_chave_retorna_lista_vazia(self, mock_key):
        result = ddi_consultas._buscar_ceis("11222333000181")

        assert result == []

    @patch('ddi_consultas.requests.get')
    def test_timeout_retorna_lista_vazia(self, mock_get):
        import requests as req_lib
        mock_get.side_effect = req_lib.exceptions.Timeout()

        result = ddi_consultas._buscar_ceis("11222333000181")

        assert result == []
```

- [ ] **Passo 2: Rodar e verificar que falha**

```bash
cd ~/Documents/Daysival && pytest tests/test_ddi_consultas.py::TestBuscarCeis -v
```

Resultado esperado: FAILED

- [ ] **Passo 3: Implementar _buscar_ceis em ddi_consultas.py**

Substituir o `pass` de `_buscar_ceis`:
```python
def _buscar_ceis(cnpj: str) -> list:
    chave = _get_cgu_key()
    if not chave:
        return []
    try:
        resp = requests.get(
            "https://api.portaldatransparencia.gov.br/api-de-dados/ceis",
            params={"cnpjSancionado": cnpj, "pagina": 1},
            headers={"chave-api": chave, "Accept": "application/json"},
            timeout=_TIMEOUT,
        )
        if resp.status_code != 200:
            return []
        return [
            {
                "nomeInfrator": r.get("nomeInfrator", ""),
                "orgaoSancionador": (r.get("orgaoSancionador") or {}).get("nome", ""),
                "dataInicioSancao": r.get("dataInicioSancao", ""),
                "dataFimSancao": r.get("dataFimSancao", ""),
                "situacaoAtual": r.get("situacaoAtual", ""),
                "fundamentacaoLegal": r.get("fundamentacaoLegal", ""),
            }
            for r in (resp.json() or [])
        ]
    except requests.exceptions.RequestException:
        return []
```

- [ ] **Passo 4: Rodar e verificar que passa**

```bash
cd ~/Documents/Daysival && pytest tests/test_ddi_consultas.py::TestBuscarCeis -v
```

Resultado esperado: 4 testes PASSED

- [ ] **Passo 5: Commitar**

```bash
git add ddi_consultas.py tests/test_ddi_consultas.py
git commit -m "feat(ddi): CEIS integration"
```

---

### Task 5: Integração com CNEP

**Files:**
- Modify: `ddi_consultas.py`
- Modify: `tests/test_ddi_consultas.py`

- [ ] **Passo 1: Adicionar testes ao final de test_ddi_consultas.py**

```python
class TestBuscarCnep:
    @patch('ddi_consultas.requests.get')
    def test_com_punicao(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = [{
            "nomeInfrator": "EMPRESA TESTE LTDA",
            "orgaoSancionador": {"nome": "CGU"},
            "dataInicioSancao": "2022-06-01",
            "dataFimSancao": None,
            "situacaoAtual": "Ativo",
            "tipoPenalidade": "Multa",
            "fundamentacaoLegal": "Lei 12.846/2013, art. 6º",
        }]

        result = ddi_consultas._buscar_cnep("11222333000181")

        assert len(result) == 1
        assert result[0]["tipoPenalidade"] == "Multa"
        assert result[0]["situacaoAtual"] == "Ativo"

    @patch('ddi_consultas.requests.get')
    def test_sem_punicao(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = []

        result = ddi_consultas._buscar_cnep("11222333000181")

        assert result == []

    @patch('ddi_consultas._get_cgu_key', return_value=None)
    def test_sem_chave_retorna_lista_vazia(self, mock_key):
        result = ddi_consultas._buscar_cnep("11222333000181")

        assert result == []

    @patch('ddi_consultas.requests.get')
    def test_timeout_retorna_lista_vazia(self, mock_get):
        import requests as req_lib
        mock_get.side_effect = req_lib.exceptions.Timeout()

        result = ddi_consultas._buscar_cnep("11222333000181")

        assert result == []
```

- [ ] **Passo 2: Rodar e verificar que falha**

```bash
cd ~/Documents/Daysival && pytest tests/test_ddi_consultas.py::TestBuscarCnep -v
```

Resultado esperado: FAILED

- [ ] **Passo 3: Implementar _buscar_cnep em ddi_consultas.py**

Substituir o `pass` de `_buscar_cnep`:
```python
def _buscar_cnep(cnpj: str) -> list:
    chave = _get_cgu_key()
    if not chave:
        return []
    try:
        resp = requests.get(
            "https://api.portaldatransparencia.gov.br/api-de-dados/cnep",
            params={"cnpjSancionado": cnpj, "pagina": 1},
            headers={"chave-api": chave, "Accept": "application/json"},
            timeout=_TIMEOUT,
        )
        if resp.status_code != 200:
            return []
        return [
            {
                "nomeInfrator": r.get("nomeInfrator", ""),
                "orgaoSancionador": (r.get("orgaoSancionador") or {}).get("nome", ""),
                "dataInicioSancao": r.get("dataInicioSancao", ""),
                "dataFimSancao": r.get("dataFimSancao"),
                "situacaoAtual": r.get("situacaoAtual", ""),
                "tipoPenalidade": r.get("tipoPenalidade", ""),
                "fundamentacaoLegal": r.get("fundamentacaoLegal", ""),
            }
            for r in (resp.json() or [])
        ]
    except requests.exceptions.RequestException:
        return []
```

- [ ] **Passo 4: Rodar e verificar que passa**

```bash
cd ~/Documents/Daysival && pytest tests/test_ddi_consultas.py::TestBuscarCnep -v
```

Resultado esperado: 4 testes PASSED

- [ ] **Passo 5: Commitar**

```bash
git add ddi_consultas.py tests/test_ddi_consultas.py
git commit -m "feat(ddi): CNEP integration"
```

---

### Task 6: Empresa Pró-Ética + flag grande_vulto

**Files:**
- Modify: `ddi_consultas.py`
- Modify: `tests/test_ddi_consultas.py`

- [ ] **Passo 1: Adicionar testes ao final de test_ddi_consultas.py**

```python
class TestVerificarProEtica:
    @patch('ddi_consultas.requests.get')
    def test_empresa_consta_formatada(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = "...11.222.333/0001-81 EMPRESA TESTE..."

        result = ddi_consultas._verificar_pro_etica("11222333000181")

        assert result is True

    @patch('ddi_consultas.requests.get')
    def test_empresa_consta_sem_mascara(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = "...11222333000181 EMPRESA TESTE..."

        result = ddi_consultas._verificar_pro_etica("11222333000181")

        assert result is True

    @patch('ddi_consultas.requests.get')
    def test_empresa_nao_consta(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = "lista sem match algum"

        result = ddi_consultas._verificar_pro_etica("11222333000181")

        assert result is False

    @patch('ddi_consultas.requests.get')
    def test_erro_retorna_none(self, mock_get):
        import requests as req_lib
        mock_get.side_effect = req_lib.exceptions.Timeout()

        result = ddi_consultas._verificar_pro_etica("11222333000181")

        assert result is None


class TestEGrandeVulto:
    def test_acima_do_limite(self):
        assert ddi_consultas._e_grande_vulto(239_000_001.0) is True

    def test_abaixo_do_limite(self):
        assert ddi_consultas._e_grande_vulto(238_999_999.0) is False

    def test_igual_ao_limite_nao_e_grande_vulto(self):
        assert ddi_consultas._e_grande_vulto(239_000_000.0) is False
```

- [ ] **Passo 2: Rodar e verificar que falha**

```bash
cd ~/Documents/Daysival && pytest tests/test_ddi_consultas.py::TestVerificarProEtica tests/test_ddi_consultas.py::TestEGrandeVulto -v
```

Resultado esperado: `TestEGrandeVulto` passa (já implementado), `TestVerificarProEtica` falha

- [ ] **Passo 3: Implementar _verificar_pro_etica em ddi_consultas.py**

Substituir o `pass` de `_verificar_pro_etica`:
```python
def _verificar_pro_etica(cnpj: str) -> bool | None:
    cnpj_fmt = f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"
    try:
        resp = requests.get(_PRO_ETICA_URL, timeout=_TIMEOUT)
        if resp.status_code != 200:
            return None
        return cnpj_fmt in resp.text or cnpj in resp.text
    except requests.exceptions.RequestException:
        return None
```

- [ ] **Passo 4: Rodar e verificar que passa**

```bash
cd ~/Documents/Daysival && pytest tests/test_ddi_consultas.py::TestVerificarProEtica tests/test_ddi_consultas.py::TestEGrandeVulto -v
```

Resultado esperado: 7 testes PASSED

- [ ] **Passo 5: Commitar**

```bash
git add ddi_consultas.py tests/test_ddi_consultas.py
git commit -m "feat(ddi): Empresa Pro-Etica + grande_vulto flag"
```

---

### Task 7: Função principal consultar()

**Files:**
- Modify: `ddi_consultas.py`
- Modify: `tests/test_ddi_consultas.py`

- [ ] **Passo 1: Adicionar testes ao final de test_ddi_consultas.py**

```python
class TestConsultar:
    def test_cnpj_invalido_levanta_valor_error(self):
        with pytest.raises(ValueError, match="CNPJ inválido"):
            ddi_consultas.consultar("00000000000000", 100_000.0)

    @patch('ddi_consultas._buscar_receita')
    @patch('ddi_consultas._buscar_ceis')
    @patch('ddi_consultas._buscar_cnep')
    @patch('ddi_consultas._verificar_pro_etica')
    def test_resultado_consolidado(self, mock_pro, mock_cnep, mock_ceis, mock_receita):
        mock_receita.return_value = {
            "razao_social": "EMPRESA TESTE LTDA",
            "nome_fantasia": "",
            "situacao": "ATIVA",
            "porte": "MICRO EMPRESA",
            "cnae": "Desenvolvimento de software",
            "data_abertura": "2010-01-15",
            "socios": [],
        }
        mock_ceis.return_value = []
        mock_cnep.return_value = []
        mock_pro.return_value = False

        result = ddi_consultas.consultar("11222333000181", 100_000.0)

        assert result["razao_social"] == "EMPRESA TESTE LTDA"
        assert result["ceis"] == []
        assert result["cnep"] == []
        assert result["pro_etica"] is False
        assert result["grande_vulto"] is False
        assert result["valor_contrato"] == 100_000.0
        assert result["cnpj"] == "11222333000181"

    @patch('ddi_consultas._buscar_receita')
    @patch('ddi_consultas._buscar_ceis')
    @patch('ddi_consultas._buscar_cnep')
    @patch('ddi_consultas._verificar_pro_etica')
    def test_grande_vulto_flag(self, mock_pro, mock_cnep, mock_ceis, mock_receita):
        mock_receita.return_value = {
            "razao_social": "CONSTRUTORA GRANDE", "nome_fantasia": "",
            "situacao": "ATIVA", "porte": "GRANDE", "cnae": "Construção",
            "data_abertura": "2000-01-01", "socios": [],
        }
        mock_ceis.return_value = []
        mock_cnep.return_value = []
        mock_pro.return_value = False

        result = ddi_consultas.consultar("11222333000181", 300_000_000.0)

        assert result["grande_vulto"] is True

    @patch('ddi_consultas._buscar_receita', return_value=None)
    @patch('ddi_consultas._buscar_ceis', return_value=[])
    @patch('ddi_consultas._buscar_cnep', return_value=[])
    @patch('ddi_consultas._verificar_pro_etica', return_value=None)
    def test_receita_indisponivel_retorna_campos_vazios(self, *mocks):
        result = ddi_consultas.consultar("11222333000181", 100_000.0)

        assert result["razao_social"] == ""
        assert result["receita_disponivel"] is False
```

- [ ] **Passo 2: Rodar e verificar que falha**

```bash
cd ~/Documents/Daysival && pytest tests/test_ddi_consultas.py::TestConsultar -v
```

Resultado esperado: FAILED

- [ ] **Passo 3: Implementar consultar() em ddi_consultas.py**

Substituir o `pass` de `consultar`:
```python
def consultar(cnpj: str, valor_contrato: float) -> dict:
    cnpj_limpo = re.sub(r'\D', '', cnpj)
    if not _validar_cnpj(cnpj_limpo):
        raise ValueError(f"CNPJ inválido: {cnpj}")

    receita = _buscar_receita(cnpj_limpo)
    ceis = _buscar_ceis(cnpj_limpo)
    cnep = _buscar_cnep(cnpj_limpo)
    pro_etica = _verificar_pro_etica(cnpj_limpo)

    base = receita or {
        "razao_social": "", "nome_fantasia": "", "situacao": "",
        "porte": "", "cnae": "", "data_abertura": "", "socios": [],
    }
    return {
        **base,
        "cnpj": cnpj_limpo,
        "ceis": ceis,
        "cnep": cnep,
        "pro_etica": pro_etica,
        "grande_vulto": _e_grande_vulto(valor_contrato),
        "valor_contrato": valor_contrato,
        "receita_disponivel": receita is not None,
        "ceis_disponivel": _get_cgu_key() is not None,
    }
```

- [ ] **Passo 4: Rodar todos os testes até agora**

```bash
cd ~/Documents/Daysival && pytest tests/test_ddi_consultas.py -v
```

Resultado esperado: todos PASSED

- [ ] **Passo 5: Commitar**

```bash
git add ddi_consultas.py tests/test_ddi_consultas.py
git commit -m "feat(ddi): consultar() main function"
```

---

### Task 8: Regras de piso em ia_ddi.py

**Files:**
- Create: `ia_ddi.py`
- Create: `tests/test_ia_ddi.py`

- [ ] **Passo 1: Criar tests/test_ia_ddi.py**

```python
import ia_ddi


def _dados_base():
    return {
        "razao_social": "EMPRESA TESTE LTDA",
        "cnpj": "11222333000181",
        "situacao": "ATIVA",
        "ceis": [],
        "cnep": [],
        "pro_etica": False,
        "grande_vulto": False,
        "valor_contrato": 100_000.0,
    }


class TestAplicarPiso:
    def test_sem_ocorrencias_sem_risco(self):
        assert ia_ddi._aplicar_piso(_dados_base()) == "SEM RISCO IDENTIFICADO"

    def test_ceis_ativo_resulta_alto(self):
        dados = {**_dados_base(), "ceis": [{"situacaoAtual": "Ativo"}]}
        assert ia_ddi._aplicar_piso(dados) == "ALTO"

    def test_ceis_inativo_nao_eleva_risco(self):
        dados = {**_dados_base(), "ceis": [{"situacaoAtual": "Inativo"}]}
        assert ia_ddi._aplicar_piso(dados) == "SEM RISCO IDENTIFICADO"

    def test_cnep_ativo_resulta_medio(self):
        dados = {**_dados_base(), "cnep": [{"situacaoAtual": "Ativo"}]}
        assert ia_ddi._aplicar_piso(dados) == "MÉDIO"

    def test_situacao_suspensa_resulta_medio(self):
        dados = {**_dados_base(), "situacao": "SUSPENSA"}
        assert ia_ddi._aplicar_piso(dados) == "MÉDIO"

    def test_situacao_baixada_resulta_medio(self):
        dados = {**_dados_base(), "situacao": "BAIXADA"}
        assert ia_ddi._aplicar_piso(dados) == "MÉDIO"

    def test_ceis_prevalece_sobre_cnep(self):
        dados = {
            **_dados_base(),
            "ceis": [{"situacaoAtual": "Ativo"}],
            "cnep": [{"situacaoAtual": "Ativo"}],
        }
        assert ia_ddi._aplicar_piso(dados) == "ALTO"

    def test_grande_vulto_sem_pi_resulta_medio(self):
        dados = {**_dados_base(), "grande_vulto": True, "pro_etica": False}
        fid = {"q1": "Não", "q2": "Não", "q3": "Não", "q4": "Não", "q5": "Não"}
        assert ia_ddi._aplicar_piso(dados, fid) == "MÉDIO"

    def test_grande_vulto_com_pro_etica_nao_eleva(self):
        dados = {**_dados_base(), "grande_vulto": True, "pro_etica": True}
        fid = {"q1": "Sim", "q2": "Sim", "q3": "Sim", "q4": "Sim", "q5": "Sim"}
        assert ia_ddi._aplicar_piso(dados, fid) == "SEM RISCO IDENTIFICADO"

    def test_grande_vulto_com_fid_positivo_nao_eleva(self):
        dados = {**_dados_base(), "grande_vulto": True, "pro_etica": False}
        fid = {"q1": "Sim", "q2": "Sim", "q3": "Sim", "q4": "Não", "q5": "Não"}
        assert ia_ddi._aplicar_piso(dados, fid) == "SEM RISCO IDENTIFICADO"
```

- [ ] **Passo 2: Rodar e verificar que falha**

```bash
cd ~/Documents/Daysival && pytest tests/test_ia_ddi.py::TestAplicarPiso -v
```

Resultado esperado: `ModuleNotFoundError: No module named 'ia_ddi'`

- [ ] **Passo 3: Criar ia_ddi.py**

```python
import os, json, re, urllib.request, urllib.error
import streamlit as st

_MODELO_PADRAO = "claude-haiku-4-5-20251001"
_RISCO_ORDEM = ["SEM RISCO IDENTIFICADO", "BAIXO", "MÉDIO", "ALTO"]

_SISTEMA = (
    "Você é um analista sênior de integridade de fornecedores do governo federal brasileiro. "
    "Avalie o perfil de integridade do licitante com base nos dados fornecidos e nos seguintes "
    "instrumentos: Portaria SEGES/ME 8.678/2021 art. 2º III; Decreto 12.304/2024; "
    "Portaria Normativa SE/CGU 226/2025; Lei 14.133/2021 arts. 25 §4º, 60 IV, 156 §1º, 163; "
    "Lei 12.846/2013 e Decreto 8.420/2015. "
    "Responda SOMENTE com JSON válido no formato especificado. Não inclua texto fora do JSON."
)


def _get_api_key() -> str | None:
    chave = os.environ.get("ANTHROPIC_API_KEY")
    if chave:
        return chave
    try:
        return st.secrets.get("ANTHROPIC_API_KEY")
    except Exception:
        return None


def _get_modelo() -> str:
    return os.environ.get("IA_LICITA_MODELO", _MODELO_PADRAO)


def _risco_max(a: str, b: str) -> str:
    return a if _RISCO_ORDEM.index(a) >= _RISCO_ORDEM.index(b) else b


def _aplicar_piso(dados: dict, fid: dict | None = None) -> str:
    piso = "SEM RISCO IDENTIFICADO"

    if dados.get("ceis") and any(r.get("situacaoAtual") == "Ativo" for r in dados["ceis"]):
        piso = _risco_max(piso, "ALTO")

    if dados.get("cnep") and any(r.get("situacaoAtual") == "Ativo" for r in dados["cnep"]):
        piso = _risco_max(piso, "MÉDIO")

    if dados.get("situacao", "").upper() in ("SUSPENSA", "BAIXADA", "INAPTA"):
        piso = _risco_max(piso, "MÉDIO")

    if dados.get("grande_vulto"):
        tem_pi = dados.get("pro_etica") or (
            fid is not None and sum(1 for v in fid.values() if v == "Sim") >= 3
        )
        if not tem_pi:
            piso = _risco_max(piso, "MÉDIO")

    return piso


def _chamar_anthropic(prompt: str, api_key: str, modelo: str) -> str:
    corpo = json.dumps({
        "model": modelo,
        "max_tokens": 2000,
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
    with urllib.request.urlopen(req, timeout=60) as resp:
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


def analisar(dados: dict, fid: dict) -> dict:
    pass
```

- [ ] **Passo 4: Rodar e verificar que passa**

```bash
cd ~/Documents/Daysival && pytest tests/test_ia_ddi.py::TestAplicarPiso -v
```

Resultado esperado: 10 testes PASSED

- [ ] **Passo 5: Commitar**

```bash
git add ia_ddi.py tests/test_ia_ddi.py
git commit -m "feat(ddi): floor risk rules in ia_ddi"
```

---

### Task 9: Função analisar() — integração com API Anthropic

**Files:**
- Modify: `ia_ddi.py`
- Modify: `tests/test_ia_ddi.py`

- [ ] **Passo 1: Adicionar testes ao final de test_ia_ddi.py**

```python
from unittest.mock import patch, MagicMock
import json as _json
import urllib.error


def _parecer_ia_mock():
    return {
        "risco_geral": "BAIXO",
        "dimensoes": {
            "situacao_cadastral": {"status": "ok", "descricao": "Empresa ativa."},
            "sancoes": {"status": "ok", "achados": []},
            "programa_integridade": {
                "status": "alerta", "obrigatorio": False,
                "pro_etica": False, "descricao": "Sem PI declarado.",
            },
            "fid": {"status": "ok", "inconsistencias": [], "descricao": "Consistente."},
            "contexto_contrato": {
                "status": "ok", "grande_vulto": False,
                "descricao": "Abaixo do limite.",
            },
        },
        "resumo": "Empresa sem ocorrências graves.",
        "recomendacao": "Contratação pode prosseguir.",
        "base_legal": ["Portaria SEGES/ME 8.678/2021, art. 2º, III"],
        "validade_fid": "12 meses a partir da data desta consulta",
    }


class TestAnalisar:
    @patch('ia_ddi.urllib.request.urlopen')
    def test_retorna_estrutura_correta(self, mock_urlopen):
        resposta = _json.dumps({
            "content": [{"text": _json.dumps(_parecer_ia_mock())}]
        }).encode("utf-8")
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=resposta)))
        mock_cm.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_cm

        fid = {"q1": "Sim", "q2": "Sim", "q3": "Não", "q4": "Não sei", "q5": "Não"}
        resultado = ia_ddi.analisar(_dados_base(), fid)

        assert "risco_geral" in resultado
        assert "dimensoes" in resultado
        assert "resumo" in resultado
        assert "recomendacao" in resultado
        assert "base_legal" in resultado
        assert "validade_fid" in resultado

    @patch('ia_ddi.urllib.request.urlopen')
    def test_piso_prevalece_sobre_ia(self, mock_urlopen):
        parecer_baixo = _parecer_ia_mock()
        parecer_baixo["risco_geral"] = "BAIXO"
        resposta = _json.dumps({
            "content": [{"text": _json.dumps(parecer_baixo)}]
        }).encode("utf-8")
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=resposta)))
        mock_cm.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_cm

        dados = {**_dados_base(), "ceis": [{"situacaoAtual": "Ativo"}]}
        fid = {"q1": "Sim", "q2": "Sim", "q3": "Sim", "q4": "Sim", "q5": "Sim"}

        resultado = ia_ddi.analisar(dados, fid)

        assert resultado["risco_geral"] == "ALTO"

    @patch('ia_ddi._get_api_key', return_value=None)
    def test_sem_api_key_levanta_runtime_error(self, mock_key):
        fid = {"q1": "Sim", "q2": "Não", "q3": "Não", "q4": "Não", "q5": "Não"}

        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            ia_ddi.analisar(_dados_base(), fid)
```

Adicionar `import pytest` no topo do arquivo de teste se ainda não estiver.

- [ ] **Passo 2: Rodar e verificar que falha**

```bash
cd ~/Documents/Daysival && pytest tests/test_ia_ddi.py::TestAnalisar -v
```

Resultado esperado: FAILED — `analisar` retorna None

- [ ] **Passo 3: Implementar analisar() em ia_ddi.py**

Substituir o `pass` de `analisar`:
```python
_ESTRUTURA_PARECER = """{
  "risco_geral": "ALTO|MÉDIO|BAIXO|SEM RISCO IDENTIFICADO",
  "dimensoes": {
    "situacao_cadastral": {"status": "ok|alerta|critico", "descricao": "..."},
    "sancoes": {"status": "ok|alerta|critico", "achados": [{"fonte": "...", "descricao": "...", "gravidade": "alta|média|baixa"}]},
    "programa_integridade": {"status": "ok|alerta|critico", "obrigatorio": true, "pro_etica": false, "descricao": "..."},
    "fid": {"status": "ok|alerta|critico", "inconsistencias": [], "descricao": "..."},
    "contexto_contrato": {"status": "ok|alerta|critico", "grande_vulto": false, "descricao": "..."}
  },
  "resumo": "frase direta",
  "recomendacao": "orientação ao gestor",
  "base_legal": ["Portaria SEGES/ME 8.678/2021, art. 2º, III"],
  "validade_fid": "12 meses a partir da data desta consulta"
}"""


def analisar(dados: dict, fid: dict) -> dict:
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY ausente. Configure a chave para a análise DDI."
        )

    piso = _aplicar_piso(dados, fid)

    prompt = (
        f"Dados do licitante:\n{json.dumps(dados, ensure_ascii=False, indent=2)}\n\n"
        f"Respostas do FID:\n"
        f"- Código de Ética ou Conduta formal: {fid.get('q1', 'Não sei')}\n"
        f"- Canal de denúncias ativo: {fid.get('q2', 'Não sei')}\n"
        f"- Treinamentos periódicos de integridade: {fid.get('q3', 'Não sei')}\n"
        f"- Política de conflito de interesses: {fid.get('q4', 'Não sei')}\n"
        f"- Auditorias internas ou externas: {fid.get('q5', 'Não sei')}\n\n"
        f"Retorne o parecer no formato:\n{_ESTRUTURA_PARECER}"
    )

    try:
        bruto = _chamar_anthropic(prompt, api_key, _get_modelo())
        parecer = _extrair_json(bruto)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        raise RuntimeError(f"Falha na API Anthropic: {exc}") from exc
    except (ValueError, Exception) as exc:
        raise RuntimeError(f"Resposta inesperada da API: {exc}") from exc

    if _RISCO_ORDEM.index(piso) > _RISCO_ORDEM.index(
        parecer.get("risco_geral", "SEM RISCO IDENTIFICADO")
    ):
        parecer["risco_geral"] = piso

    return parecer
```

- [ ] **Passo 4: Rodar todos os testes de ia_ddi**

```bash
cd ~/Documents/Daysival && pytest tests/test_ia_ddi.py -v
```

Resultado esperado: todos PASSED

- [ ] **Passo 5: Commitar**

```bash
git add ia_ddi.py tests/test_ia_ddi.py
git commit -m "feat(ddi): analisar() with Anthropic API + floor enforcement"
```

---

### Task 10: Geração de PDF — relatorio_ddi.py

**Files:**
- Create: `relatorio_ddi.py`
- Create: `tests/test_relatorio_ddi.py`

- [ ] **Passo 1: Criar tests/test_relatorio_ddi.py**

```python
import relatorio_ddi


def _dados():
    return {
        "razao_social": "EMPRESA TESTE LTDA",
        "cnpj": "11222333000181",
        "situacao": "ATIVA",
        "porte": "MICRO EMPRESA",
        "cnae": "Desenvolvimento de software",
        "data_abertura": "2010-01-15",
        "socios": [{"nome": "FULANO DA SILVA", "cargo": "SÓCIO-ADMINISTRADOR"}],
        "ceis": [],
        "cnep": [],
        "pro_etica": False,
        "grande_vulto": False,
        "valor_contrato": 100_000.0,
    }


def _fid():
    return {"q1": "Sim", "q2": "Não", "q3": "Sim", "q4": "Não sei", "q5": "Não"}


def _parecer():
    return {
        "risco_geral": "BAIXO",
        "dimensoes": {
            "situacao_cadastral": {"status": "ok", "descricao": "Empresa ativa."},
            "sancoes": {"status": "ok", "achados": []},
            "programa_integridade": {
                "status": "alerta", "obrigatorio": False,
                "pro_etica": False, "descricao": "Sem PI declarado.",
            },
            "fid": {"status": "ok", "inconsistencias": [], "descricao": "Consistente."},
            "contexto_contrato": {
                "status": "ok", "grande_vulto": False, "descricao": "Abaixo do limite.",
            },
        },
        "resumo": "Empresa sem ocorrências graves.",
        "recomendacao": "Contratação pode prosseguir.",
        "base_legal": ["Portaria SEGES/ME 8.678/2021, art. 2º, III"],
        "validade_fid": "12 meses a partir da data desta consulta",
    }


class TestGerarPdf:
    def test_retorna_bytes(self):
        pdf = relatorio_ddi.gerar_pdf("11222333000181", 100_000.0, _dados(), _fid(), _parecer())
        assert isinstance(pdf, bytes)

    def test_comeca_com_magic_bytes_pdf(self):
        pdf = relatorio_ddi.gerar_pdf("11222333000181", 100_000.0, _dados(), _fid(), _parecer())
        assert pdf[:4] == b'%PDF'

    def test_tamanho_minimo(self):
        pdf = relatorio_ddi.gerar_pdf("11222333000181", 100_000.0, _dados(), _fid(), _parecer())
        assert len(pdf) > 2000

    def test_risco_alto_nao_levanta_erro(self):
        parecer_alto = {**_parecer(), "risco_geral": "ALTO"}
        pdf = relatorio_ddi.gerar_pdf("11222333000181", 300_000_000.0, _dados(), _fid(), parecer_alto)
        assert pdf[:4] == b'%PDF'
```

- [ ] **Passo 2: Rodar e verificar que falha**

```bash
cd ~/Documents/Daysival && pytest tests/test_relatorio_ddi.py -v
```

Resultado esperado: `ModuleNotFoundError: No module named 'relatorio_ddi'`

- [ ] **Passo 3: Criar relatorio_ddi.py**

```python
import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)

_COR_RISCO = {
    "ALTO": colors.HexColor("#C0392B"),
    "MÉDIO": colors.HexColor("#E67E22"),
    "BAIXO": colors.HexColor("#F39C12"),
    "SEM RISCO IDENTIFICADO": colors.HexColor("#27AE60"),
}
_COR_STATUS = {"ok": "#27AE60", "alerta": "#E67E22", "critico": "#C0392B"}
_LABEL_DIMENSAO = {
    "situacao_cadastral": "Situação Cadastral",
    "sancoes": "Sanções e Punições",
    "programa_integridade": "Programa de Integridade",
    "fid": "Autoavaliação (FID)",
    "contexto_contrato": "Contexto do Contrato",
}
_PERGUNTAS_FID = {
    "q1": "Código de Ética ou Conduta formal",
    "q2": "Canal de denúncias ativo",
    "q3": "Treinamentos periódicos de integridade",
    "q4": "Política de conflito de interesses",
    "q5": "Auditorias internas ou externas",
}


def _fmt_cnpj(cnpj: str) -> str:
    c = cnpj.replace(".", "").replace("/", "").replace("-", "")
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}" if len(c) == 14 else cnpj


def _fmt_brl(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def gerar_pdf(cnpj: str, valor_contrato: float, dados: dict, fid: dict, parecer: dict) -> bytes:
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

    story = []

    # Cabeçalho
    story.append(Paragraph("IA-Licita — RM Vértice Digital", titulo))
    story.append(Paragraph("Due Diligence de Integridade (DDI)", estilos["Heading1"]))
    story.append(Paragraph("Portaria SEGES/ME 8.678/2021, art. 2º, III · Decreto 12.304/2024", pequeno))
    story.append(Paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}", pequeno))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.grey, spaceAfter=8))

    # Identificação
    story.append(Paragraph("Identificação do Licitante", h2))
    linhas_id = [
        ["Razão Social", dados.get("razao_social", "—")],
        ["CNPJ", _fmt_cnpj(cnpj)],
        ["Situação Cadastral", dados.get("situacao", "—")],
        ["Porte", dados.get("porte", "—")],
        ["CNAE Principal", dados.get("cnae", "—")],
        ["Data de Abertura", dados.get("data_abertura", "—")],
        ["Valor do Contrato", _fmt_brl(valor_contrato)],
        ["Grande Vulto (> R$ 239M)", "Sim" if dados.get("grande_vulto") else "Não"],
    ]
    t = Table(linhas_id, colWidths=[5*cm, 12*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F2F2F2")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("PADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.4*cm))

    # Sócios
    socios = dados.get("socios", [])
    if socios:
        story.append(Paragraph("Quadro Societário", h2))
        for s in socios:
            story.append(Paragraph(f"• {s.get('nome', '—')} — {s.get('cargo', '—')}", corpo))
        story.append(Spacer(1, 0.3*cm))

    # Índice de risco
    risco = parecer.get("risco_geral", "SEM RISCO IDENTIFICADO")
    cor_risco = _COR_RISCO.get(risco, colors.grey)
    story.append(Paragraph("Índice de Risco Geral", h2))
    t_risco = Table(
        [[Paragraph(f"<b>{risco}</b>",
                    ParagraphStyle("r", fontSize=14, textColor=colors.white, alignment=1))]],
        colWidths=[17*cm]
    )
    t_risco.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), cor_risco),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("PADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(t_risco)
    story.append(Spacer(1, 0.4*cm))

    # Risco por dimensão
    story.append(Paragraph("Análise por Dimensão", h2))
    dims = parecer.get("dimensoes", {})
    for chave, label in _LABEL_DIMENSAO.items():
        dim = dims.get(chave, {})
        status = dim.get("status", "ok")
        cor = _COR_STATUS.get(status, "#000000")
        icone = {"ok": "✓", "alerta": "⚠", "critico": "✗"}.get(status, "•")
        story.append(Paragraph(
            f"<font color='{cor}'><b>{icone} {label}</b></font>: {dim.get('descricao', '—')}",
            corpo
        ))
        for achado in dim.get("achados", []):
            story.append(Paragraph(
                f"  → <b>{achado.get('fonte', '')}:</b> {achado.get('descricao', '')} "
                f"(gravidade: {achado.get('gravidade', '')})",
                corpo
            ))
    story.append(Spacer(1, 0.3*cm))

    # FID
    story.append(Paragraph("Formulário de Integridade e Diligência (FID)", h2))
    linhas_fid = [["Critério", "Resposta"]] + [
        [_PERGUNTAS_FID.get(k, k), v] for k, v in fid.items()
    ]
    t_fid = Table(linhas_fid, colWidths=[12*cm, 5*cm])
    t_fid.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t_fid)
    story.append(Spacer(1, 0.3*cm))

    # Programa de Integridade
    pi_dim = dims.get("programa_integridade", {})
    story.append(Paragraph("Programa de Integridade", h2))
    story.append(Paragraph(
        f"Empresa Pró-Ética (CGU): {'Sim ✓' if pi_dim.get('pro_etica') else 'Não'}",
        corpo
    ))
    story.append(Paragraph(
        f"PI obrigatório (Decreto 12.304/2024 — Grande Vulto): "
        f"{'Sim' if pi_dim.get('obrigatorio') else 'Não'}",
        corpo
    ))
    story.append(Spacer(1, 0.3*cm))

    # Parecer
    story.append(Paragraph("Parecer de Integridade", h2))
    story.append(Paragraph(parecer.get("resumo", "—"), corpo))
    story.append(Spacer(1, 0.2*cm))
    for bl in parecer.get("base_legal", []):
        story.append(Paragraph(f"• {bl}", corpo))
    story.append(Spacer(1, 0.3*cm))

    # Recomendação
    story.append(Paragraph("Recomendação ao Gestor", h2))
    story.append(Paragraph(parecer.get("recomendacao", "—"), corpo))
    story.append(Spacer(1, 0.4*cm))

    # Rodapé
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Paragraph(f"Validade do FID: {parecer.get('validade_fid', '12 meses')}", pequeno))
    story.append(Paragraph(
        "Gerado por IA-Licita — RM Vértice Digital. Sujeito à verificação humana. "
        "Não substitui parecer jurídico.",
        pequeno
    ))

    doc.build(story)
    return buf.getvalue()
```

- [ ] **Passo 4: Rodar e verificar que passa**

```bash
cd ~/Documents/Daysival && pytest tests/test_relatorio_ddi.py -v
```

Resultado esperado: 4 testes PASSED

- [ ] **Passo 5: Commitar**

```bash
git add relatorio_ddi.py tests/test_relatorio_ddi.py
git commit -m "feat(ddi): PDF report generation with reportlab"
```

---

### Task 11: Modificar app.py — Tab 2

**Files:**
- Modify: `app.py`

- [ ] **Passo 1: Localizar ponto de inserção no app.py**

```bash
grep -n "st.title\|st.write\|col_a\|file_uploader" ~/Documents/Daysival/app.py
```

Anotar a linha onde `st.title(...)` aparece — é o ponto onde as tabs serão inseridas.

- [ ] **Passo 2: Adicionar imports DDI no topo de app.py**

Logo após `import branding` (linha ~8), adicionar:
```python
import ddi_consultas
import ia_ddi
import relatorio_ddi
```

- [ ] **Passo 3: Substituir st.title() e st.write() por tabs**

Localizar as linhas:
```python
st.title("Auditoria de Edital — Lei nº 14.133/2021")
st.write("Envie o edital em PDF e receba a análise de conformidade com índice de risco, "
         "apontamentos com fundamento legal e relatório para download.")
```

Substituir por:
```python
st.title("IA-Licita — Conformidade e Integridade nas Contratações Públicas")

aba1, aba2 = st.tabs(["📄 Auditoria de Edital", "🔍 Due Diligence de Integridade"])

with aba1:
    st.subheader("Auditoria de Edital — Lei nº 14.133/2021")
    st.write("Envie o edital em PDF e receba a análise de conformidade com índice de risco, "
             "apontamentos com fundamento legal e relatório para download.")
```

Indentar todo o código restante do app.py com 4 espaços adicionais (dentro de `with aba1:`). O bloco `with aba1:` vai do `st.subheader(...)` até o final do arquivo.

- [ ] **Passo 4: Adicionar bloco with aba2: após o fechamento de with aba1:**

Após todo o código de aba1 (final do arquivo), adicionar:
```python
with aba2:
    st.subheader("Due Diligence de Integridade (DDI)")
    st.caption(
        "Portaria SEGES/ME 8.678/2021, art. 2º, III · "
        "Decreto 12.304/2024 · Portaria Normativa SE/CGU 226/2025"
    )

    if not ddi_consultas._get_cgu_key():
        st.warning(
            "⚠️ CGU_API_KEY não configurada — CEIS e CNEP não serão consultados. "
            "Cadastre sua chave gratuita em portaldatransparencia.gov.br/api-de-dados/swagger-ui.html"
        )

    col1, col2 = st.columns([2, 1])
    cnpj_input = col1.text_input(
        "CNPJ do licitante (14 dígitos, sem formatação)", max_chars=18, key="ddi_cnpj_input"
    )
    valor_input = col2.number_input(
        "Valor do contrato (R$)", min_value=0.0, format="%.2f", step=10_000.0, key="ddi_valor_input"
    )

    # Etapa 1 — Consulta automática
    if st.button("Consultar fontes públicas", type="primary", key="btn_ddi_consultar"):
        cnpj_limpo = "".join(c for c in cnpj_input if c.isdigit())
        if len(cnpj_limpo) != 14:
            st.error("Informe o CNPJ com 14 dígitos numéricos.")
        else:
            try:
                with st.spinner("Consultando Receita Federal, CEIS, CNEP e Empresa Pró-Ética..."):
                    dados = ddi_consultas.consultar(cnpj_limpo, valor_input)
                st.session_state["ddi_dados"] = dados
                st.session_state["ddi_cnpj"] = cnpj_limpo
                st.session_state["ddi_valor"] = valor_input
                st.session_state["ddi_etapa"] = 2
                nome = dados.get("razao_social") or "Empresa não localizada na Receita"
                st.success(f"Consulta concluída — {nome}")
            except ValueError as e:
                st.error(str(e))

    # Etapa 2 — FID
    if st.session_state.get("ddi_etapa", 0) >= 2:
        st.divider()
        st.subheader("Formulário de Integridade e Diligência (FID)")
        st.caption("Responda com base nos documentos disponíveis sobre o licitante. Validade: 12 meses.")

        q1 = st.radio(
            "1. A empresa possui Código de Ética ou Conduta formal e público?",
            ["Sim", "Não", "Não sei"], horizontal=True, key="ddi_q1"
        )
        q2 = st.radio(
            "2. Há canal de denúncias ativo e acessível a terceiros?",
            ["Sim", "Não", "Não sei"], horizontal=True, key="ddi_q2"
        )
        q3 = st.radio(
            "3. A empresa realiza treinamentos periódicos de integridade?",
            ["Sim", "Não", "Não sei"], horizontal=True, key="ddi_q3"
        )
        q4 = st.radio(
            "4. Há política de conflito de interesses documentada?",
            ["Sim", "Não", "Não sei"], horizontal=True, key="ddi_q4"
        )
        q5 = st.radio(
            "5. A empresa possui auditorias internas ou externas de integridade?",
            ["Sim", "Não", "Não sei"], horizontal=True, key="ddi_q5"
        )

        _dados_etapa2 = st.session_state.get("ddi_dados", {})
        if not _dados_etapa2.get("pro_etica"):
            pro_etica_manual = st.checkbox(
                "Empresa consta no Empresa Pró-Ética (CGU)? (marque se confirmado manualmente)",
                key="ddi_pro_etica_manual"
            )
        else:
            pro_etica_manual = False

        if st.button("Gerar Parecer DDI", type="primary", key="btn_ddi_parecer"):
            fid = {"q1": q1, "q2": q2, "q3": q3, "q4": q4, "q5": q5}
            _dados_analise = {**st.session_state["ddi_dados"]}
            if pro_etica_manual:
                _dados_analise = {**_dados_analise, "pro_etica": True}
            try:
                with st.spinner("Gerando parecer de integridade com IA..."):
                    parecer = ia_ddi.analisar(_dados_analise, fid)
                st.session_state["ddi_parecer"] = parecer
                st.session_state["ddi_fid"] = fid
                st.session_state["ddi_dados"] = _dados_analise
                st.session_state["ddi_etapa"] = 3
            except RuntimeError as e:
                st.error(str(e))

    # Etapa 3 — Resultado
    if st.session_state.get("ddi_etapa", 0) >= 3:
        parecer = st.session_state["ddi_parecer"]
        fid = st.session_state["ddi_fid"]
        dados = st.session_state["ddi_dados"]
        cnpj_final = st.session_state["ddi_cnpj"]
        valor_final = st.session_state["ddi_valor"]

        st.divider()
        risco = parecer.get("risco_geral", "SEM RISCO IDENTIFICADO")
        _icone_risco = {
            "ALTO": "🔴", "MÉDIO": "🟠",
            "BAIXO": "🟡", "SEM RISCO IDENTIFICADO": "🟢"
        }
        st.subheader(f"{_icone_risco.get(risco, '⚪')} Risco Geral: {risco}")

        dims = parecer.get("dimensoes", {})
        _label_dim = {
            "situacao_cadastral": "Situação Cadastral",
            "sancoes": "Sanções e Punições",
            "programa_integridade": "Programa de Integridade",
            "fid": "Autoavaliação (FID)",
            "contexto_contrato": "Contexto do Contrato",
        }
        _icone_status = {"ok": "✅", "alerta": "⚠️", "critico": "❌"}
        for chave, label in _label_dim.items():
            dim = dims.get(chave, {})
            icone = _icone_status.get(dim.get("status", "ok"), "ℹ️")
            with st.expander(f"{icone} {label}"):
                st.write(dim.get("descricao", "—"))
                for achado in dim.get("achados", []):
                    st.error(
                        f"**{achado.get('fonte')}:** {achado.get('descricao')} "
                        f"(gravidade: {achado.get('gravidade')})"
                    )

        st.subheader("Parecer")
        st.info(parecer.get("resumo", "—"))

        st.subheader("Recomendação ao Gestor")
        st.write(parecer.get("recomendacao", "—"))

        with st.expander("Base Legal"):
            for bl in parecer.get("base_legal", []):
                st.write(f"• {bl}")

        pdf_bytes = relatorio_ddi.gerar_pdf(cnpj_final, valor_final, dados, fid, parecer)
        st.download_button(
            label="Baixar Relatório PDF",
            data=pdf_bytes,
            file_name=f"DDI_{cnpj_final}.pdf",
            mime="application/pdf",
        )
```

- [ ] **Passo 5: Verificar sintaxe**

```bash
cd ~/Documents/Daysival && python -m py_compile app.py && echo "Sintaxe OK"
```

Resultado esperado: `Sintaxe OK`

- [ ] **Passo 6: Commitar**

```bash
git add app.py
git commit -m "feat(ddi): Tab 2 with 3-step DDI flow in app.py"
```

---

### Task 12: Smoke test — verificação final

**Files:** nenhum (execução e observação)

- [ ] **Passo 1: Rodar suite completa de testes**

```bash
cd ~/Documents/Daysival && pytest tests/ -v
```

Resultado esperado: todos PASSED. Nenhum FAILED ou ERROR.

- [ ] **Passo 2: Subir o app**

```bash
cd ~/Documents/Daysival && python -m streamlit run app.py
```

- [ ] **Passo 3: Verificar Tab 1 — regressão**

1. Acessar `http://localhost:8501`
2. Clicar na tab "📄 Auditoria de Edital"
3. Fazer upload de qualquer edital PDF
4. Confirmar que a análise roda normalmente — sem erros

- [ ] **Passo 4: Verificar Tab 2 — caminho feliz**

1. Clicar na tab "🔍 Due Diligence de Integridade"
2. Inserir CNPJ `11222333000181` e valor `100000`
3. Clicar "Consultar fontes públicas"
4. Verificar mensagem de sucesso com nome da empresa
5. Preencher todas as perguntas do FID
6. Clicar "Gerar Parecer DDI"
7. Verificar risco com ícone colorido e 5 dimensões expandíveis
8. Clicar "Baixar Relatório PDF" e abrir o arquivo

- [ ] **Passo 5: Verificar CNPJ inválido**

Inserir `12345678901234` e clicar "Consultar fontes públicas".
Resultado esperado: mensagem de erro "CNPJ inválido".

- [ ] **Passo 6: Commit final**

```bash
git add -A
git commit -m "feat(ddi): DDI module complete — smoke test passed"
```
