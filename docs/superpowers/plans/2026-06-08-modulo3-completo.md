# Módulo 3 Completo — Avaliação de PI (Adm. Pública e OSCs) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Estender a aba5 ("🏢 Avaliação de PI") para suportar Administração Pública e OSCs além de Empresa Privada, completando o Módulo 3 conforme Decreto 12.304/2024, Art. 1º, I-III.

**Architecture:** Adicionar `TIPOS_ENTIDADE`, `HIPOTESES_POR_TIPO` e `_SISTEMA_POR_TIPO` em `ia_pi_empresas.py`; `avaliar()` ganha parâmetro `tipo_entidade` (default `"empresa_privada"` para manter backward compat); `relatorio_pi_empresas.gerar_pdf()` ganha parâmetro `tipo_entidade` opcional; `app.py` adiciona seletor de tipo antes do seletor de hipótese e filtra as opções de hipótese pelo tipo.

**Tech Stack:** Python 3.9, Streamlit, ReportLab, pytest, unittest.mock

---

## Arquivo map

| Arquivo | Ação |
|---|---|
| `ia_pi_empresas.py` | Modificar: + `TIPOS_ENTIDADE`, `HIPOTESES_POR_TIPO`, `_SISTEMA_POR_TIPO`; remove `HIPOTESES`; atualiza `avaliar()` |
| `relatorio_pi_empresas.py` | Modificar: import atualizado; `gerar_pdf()` ganha `tipo_entidade`; nova linha na tabela de identificação |
| `app.py` | Modificar: aba5 — seletor de tipo, filtro de hipóteses, passa `tipo_entidade` para `avaliar()` e `gerar_pdf()`, label no resultado |
| `tests/test_ia_pi_empresas.py` | Modificar: + 4 testes para novas constantes e comportamento de `avaliar()` |
| `tests/test_relatorio_pi_empresas.py` | Modificar: + 3 testes para novos tipos em `gerar_pdf()` |

---

## Task 1: Adicionar constantes e atualizar `avaliar()` em `ia_pi_empresas.py`

**Files:**
- Modify: `ia_pi_empresas.py`
- Test: `tests/test_ia_pi_empresas.py`

- [ ] **Step 1: Escrever testes que falham**

Abrir `tests/test_ia_pi_empresas.py` e acrescentar ao final do arquivo (os imports `json` e `patch` já existem no topo — não repetir):

```python
class TestTiposEHipoteses:
    def test_hipoteses_por_tipo_tem_tres_tipos(self):
        assert set(ia_pi_empresas.HIPOTESES_POR_TIPO.keys()) == {
            "empresa_privada", "administracao_publica", "osc"
        }

    def test_cada_tipo_tem_pelo_menos_tres_hipoteses(self):
        for tipo, hipoteses in ia_pi_empresas.HIPOTESES_POR_TIPO.items():
            assert len(hipoteses) >= 3, f"{tipo} tem menos de 3 hipóteses"

    def test_tipos_entidade_tem_tres_chaves(self):
        assert set(ia_pi_empresas.TIPOS_ENTIDADE.keys()) == {
            "empresa_privada", "administracao_publica", "osc"
        }


class TestAvaliarTipoEntidade:
    def test_tipo_administracao_publica_usa_sistema_correto(self):
        respostas = {p: "Implementado" for p in ia_pi_empresas.QUESTOES_PI}
        qualitativo = _qualitativo_mock()
        with patch(
            "ia_pi_empresas._chamar_anthropic",
            return_value=json.dumps(qualitativo),
        ) as mock_call:
            ia_pi_empresas.avaliar(
                respostas, "grande_vulto", None, "key",
                tipo_entidade="administracao_publica",
            )
        sistema = mock_call.call_args[0][3]
        assert "Administração Pública" in sistema

    def test_tipo_osc_usa_sistema_correto(self):
        respostas = {p: "Implementado" for p in ia_pi_empresas.QUESTOES_PI}
        qualitativo = _qualitativo_mock()
        with patch(
            "ia_pi_empresas._chamar_anthropic",
            return_value=json.dumps(qualitativo),
        ) as mock_call:
            ia_pi_empresas.avaliar(
                respostas, "termo_fomento", None, "key",
                tipo_entidade="osc",
            )
        sistema = mock_call.call_args[0][3]
        assert "OSC" in sistema

    def test_tipo_entidade_gravado_no_resultado(self):
        respostas = {p: "Implementado" for p in ia_pi_empresas.QUESTOES_PI}
        with patch(
            "urllib.request.urlopen",
            return_value=_mock_urlopen(_qualitativo_mock()),
        ):
            resultado = ia_pi_empresas.avaliar(
                respostas, "grande_vulto", None, "key",
                tipo_entidade="administracao_publica",
            )
        assert resultado["tipo_entidade"] == "administracao_publica"

    def test_tipo_desconhecido_levanta_key_error(self):
        respostas = {p: "Não existe" for p in ia_pi_empresas.QUESTOES_PI}
        with pytest.raises(KeyError):
            ia_pi_empresas.avaliar(
                respostas, "grande_vulto", None, "key",
                tipo_entidade="tipo_invalido",
            )
```

- [ ] **Step 2: Verificar que os testes falham**

```bash
cd ~/Documents/Daysival && python3 -m pytest tests/test_ia_pi_empresas.py::TestTiposEHipoteses tests/test_ia_pi_empresas.py::TestAvaliarTipoEntidade -v
```

Esperado: `FAILED` em todos os 7 novos testes com `AttributeError: module 'ia_pi_empresas' has no attribute 'HIPOTESES_POR_TIPO'`.

- [ ] **Step 3: Implementar as mudanças em `ia_pi_empresas.py`**

**3a.** Substituir o bloco `HIPOTESES = MappingProxyType(...)` existente (linha ~52-56) pelo seguinte bloco de constantes (inserir logo após `PESOS_DIMENSAO`):

```python
TIPOS_ENTIDADE: types.MappingProxyType[str, str] = types.MappingProxyType({
    "empresa_privada":       "Empresa Privada",
    "administracao_publica": "Administração Pública",
    "osc":                   "Organização da Sociedade Civil (OSC)",
})

HIPOTESES_POR_TIPO: types.MappingProxyType[str, types.MappingProxyType] = types.MappingProxyType({
    "empresa_privada": types.MappingProxyType({
        "grande_vulto":  "Grande Vulto (Decreto 12.304/2024, Art. 4º)",
        "desempate":     "Desempate por PI (Lei 14.133/2021, Art. 60, IV)",
        "reabilitacao":  "Reabilitação de Fornecedor (Lei 14.133/2021, Art. 163, Par. Único)",
    }),
    "administracao_publica": types.MappingProxyType({
        "grande_vulto": "Contratação de Grande Vulto (Decreto 12.304/2024, Art. 4º)",
        "convenio":     "Convênio ou Transferência Voluntária",
        "cooperacao":   "Cooperação Técnica Internacional",
    }),
    "osc": types.MappingProxyType({
        "termo_fomento":     "Termo de Fomento (Lei 13.019/2014, Art. 16)",
        "termo_colaboracao": "Termo de Colaboração (Lei 13.019/2014, Art. 16)",
        "acordo_cooperacao": "Acordo de Cooperação (Lei 13.019/2014, Art. 16)",
    }),
})

HIPOTESES = HIPOTESES_POR_TIPO["empresa_privada"]  # alias temporário — removido na Task 3
```

**3b.** Substituir a constante `_SISTEMA` existente por `_SISTEMA_POR_TIPO`:

Remover:
```python
_SISTEMA = (
    "Você é um consultor sênior especialista em Programas de Integridade para empresas "
    "privadas e organismos que contratam com a Administração Pública brasileira. "
    "Avalie o Programa de Integridade da empresa com base nas respostas do questionário "
    "e nos documentos fornecidos, à luz do Decreto 12.304/2024, da Lei 12.846/2013 "
    "(art. 7º, IV) e da Lei 14.133/2021. "
    "Responda SOMENTE com JSON válido no formato especificado. Não inclua texto fora do JSON."
)
```

Substituir por:
```python
_SISTEMA_POR_TIPO: types.MappingProxyType[str, str] = types.MappingProxyType({
    "empresa_privada": (
        "Você é um consultor sênior especialista em Programas de Integridade para empresas "
        "privadas e organismos que contratam com a Administração Pública brasileira. "
        "Avalie o Programa de Integridade da empresa com base nas respostas do questionário "
        "e nos documentos fornecidos, à luz do Decreto 12.304/2024 (Art. 1º, I), da "
        "Lei 12.846/2013 (art. 7º, IV) e da Lei 14.133/2021. "
        "Responda SOMENTE com JSON válido no formato especificado. Não inclua texto fora do JSON."
    ),
    "administracao_publica": (
        "Você é um consultor sênior especialista em Programas de Integridade para órgãos e "
        "entidades da Administração Pública brasileira. "
        "Avalie o Programa de Integridade do órgão ou entidade com base nas respostas do "
        "questionário e nos documentos fornecidos, à luz do Decreto 12.304/2024 (Art. 1º, II) "
        "e da Lei 12.846/2013 (art. 7º, IV). "
        "Responda SOMENTE com JSON válido no formato especificado. Não inclua texto fora do JSON."
    ),
    "osc": (
        "Você é um consultor sênior especialista em Programas de Integridade para Organizações "
        "da Sociedade Civil (OSC) nos termos da Lei 13.019/2014. "
        "Avalie o Programa de Integridade da OSC com base nas respostas do questionário "
        "e nos documentos fornecidos, à luz do Decreto 12.304/2024 (Art. 1º, III), da "
        "Lei 13.019/2014 e da Lei 12.846/2013 (art. 7º, IV). "
        "Responda SOMENTE com JSON válido no formato especificado. Não inclua texto fora do JSON."
    ),
})
```

**3c.** Atualizar a assinatura e o corpo de `avaliar()`:

Substituir a definição atual de `avaliar()`:
```python
def avaliar(
    respostas: dict,
    hipotese: str,
    texto_docs: str | None,
    api_key: str,
    modelo: str = _MODELO_PADRAO,
) -> dict:
```

Por:
```python
def avaliar(
    respostas: dict,
    hipotese: str,
    texto_docs: str | None,
    api_key: str,
    modelo: str = _MODELO_PADRAO,
    tipo_entidade: str = "empresa_privada",
) -> dict:
    _sistema = _SISTEMA_POR_TIPO[tipo_entidade]
```

Na linha que chama `_chamar_anthropic`, substituir `_SISTEMA` por `_sistema`:
```python
    bruto = _chamar_anthropic("\n".join(partes), api_key, modelo, _sistema)
```

No return final, acrescentar `"tipo_entidade"` ao dict:
```python
    return {
        **qualitativo,
        "scores":        scores,
        "hipotese":      hipotese,
        "tipo_entidade": tipo_entidade,
    }
```

- [ ] **Step 4: Verificar que os novos testes passam e os antigos continuam verdes**

```bash
cd ~/Documents/Daysival && python3 -m pytest tests/test_ia_pi_empresas.py -v
```

Esperado: todos os testes passam (incluindo os 7 novos e os existentes).

- [ ] **Step 5: Commit**

```bash
cd ~/Documents/Daysival && git add ia_pi_empresas.py tests/test_ia_pi_empresas.py && git commit -m "feat(pi): adiciona TIPOS_ENTIDADE, HIPOTESES_POR_TIPO e tipo_entidade em avaliar()"
```

---

## Task 2: Atualizar `relatorio_pi_empresas.py` + testes

**Files:**
- Modify: `relatorio_pi_empresas.py`
- Test: `tests/test_relatorio_pi_empresas.py`

- [ ] **Step 1: Escrever testes que falham**

Acrescentar ao final de `tests/test_relatorio_pi_empresas.py`:

```python
class TestGerarPdfTipoEntidade:
    def test_pdf_administracao_publica_retorna_bytes(self):
        parecer = _parecer_minimo()
        pdf = relatorio_pi_empresas.gerar_pdf(
            cnpj="00394460000141",
            razao_social="MINISTERIO DA FAZENDA",
            hipotese="grande_vulto",
            parecer=parecer,
            tipo_entidade="administracao_publica",
        )
        assert isinstance(pdf, bytes)
        assert len(pdf) > 1000
        assert pdf[:4] == b"%PDF"

    def test_pdf_osc_retorna_bytes(self):
        parecer = _parecer_minimo()
        pdf = relatorio_pi_empresas.gerar_pdf(
            cnpj="11222333000181",
            razao_social="ASSOCIACAO TESTE",
            hipotese="termo_fomento",
            parecer=parecer,
            tipo_entidade="osc",
        )
        assert isinstance(pdf, bytes)
        assert len(pdf) > 1000
        assert pdf[:4] == b"%PDF"

    def test_pdf_empresa_privada_com_parametro_explicito_retorna_bytes(self):
        parecer = _parecer_minimo()
        pdf = relatorio_pi_empresas.gerar_pdf(
            cnpj="11222333000181",
            razao_social="EMPRESA TESTE LTDA",
            hipotese="grande_vulto",
            parecer=parecer,
            tipo_entidade="empresa_privada",
        )
        assert isinstance(pdf, bytes)
        assert len(pdf) > 1000
        assert pdf[:4] == b"%PDF"
```

- [ ] **Step 2: Verificar que os testes novos falham**

```bash
cd ~/Documents/Daysival && python3 -m pytest tests/test_relatorio_pi_empresas.py::TestGerarPdfTipoEntidade -v
```

Esperado: `FAILED` com `TypeError: gerar_pdf() got an unexpected keyword argument 'tipo_entidade'`.

- [ ] **Step 3: Atualizar o import em `relatorio_pi_empresas.py`**

Substituir a linha de import:
```python
from ia_pi_empresas import DIMENSOES_PI, HIPOTESES, QUESTOES_PI
```

Por:
```python
from ia_pi_empresas import DIMENSOES_PI, HIPOTESES_POR_TIPO, QUESTOES_PI, TIPOS_ENTIDADE
```

- [ ] **Step 4: Atualizar a assinatura de `gerar_pdf()`**

Substituir:
```python
def gerar_pdf(cnpj: str, razao_social: str, hipotese: str, parecer: dict) -> bytes:
```

Por:
```python
def gerar_pdf(
    cnpj: str,
    razao_social: str,
    hipotese: str,
    parecer: dict,
    tipo_entidade: str = "empresa_privada",
) -> bytes:
```

- [ ] **Step 5: Atualizar a tabela de identificação dentro de `gerar_pdf()`**

Substituir o bloco `linhas_id`:
```python
    linhas_id = [
        ["Razão Social", html.escape(str(razao_social or "-"))],
        ["CNPJ", _fmt_cnpj(cnpj)],
        ["Hipótese Avaliada", html.escape(str(HIPOTESES.get(hipotese, hipotese)))],
    ]
```

Por:
```python
    _label_tipo = TIPOS_ENTIDADE.get(tipo_entidade, tipo_entidade)
    _label_hip  = (HIPOTESES_POR_TIPO.get(tipo_entidade) or {}).get(hipotese, hipotese)
    linhas_id = [
        ["Razão Social",    html.escape(str(razao_social or "-"))],
        ["CNPJ",            _fmt_cnpj(cnpj)],
        ["Tipo de Entidade", html.escape(_label_tipo)],
        ["Hipótese Avaliada", html.escape(str(_label_hip))],
    ]
```

- [ ] **Step 6: Verificar que todos os testes de relatorio_pi_empresas passam**

```bash
cd ~/Documents/Daysival && python3 -m pytest tests/test_relatorio_pi_empresas.py -v
```

Esperado: todos os testes passam (3 antigos + 3 novos = 6 total).

- [ ] **Step 7: Commit**

```bash
cd ~/Documents/Daysival && git add relatorio_pi_empresas.py tests/test_relatorio_pi_empresas.py && git commit -m "feat(relatorio-pi): adiciona tipo_entidade em gerar_pdf() e linha no PDF"
```

---

## Task 3: Atualizar `app.py` e remover alias `HIPOTESES`

**Files:**
- Modify: `app.py`
- Modify: `ia_pi_empresas.py` (remoção do alias)

- [ ] **Step 1: Substituir o layout de Etapa 1 da aba5 no `app.py`**

Localizar o bloco que começa em `st.markdown("### Etapa 1 — Identificação da Empresa")` e vai até `_hipotese_pi = _hip_chaves[_hip_idx]` (linhas 551–564). Substituir pelo seguinte:

```python
    st.markdown("### Etapa 1 — Identificação da Entidade")
    _col_cnpj, _col_tipo = st.columns([2, 3])
    _cnpj_pi = _col_cnpj.text_input(
        "CNPJ da entidade", key="pi_cnpj_input", placeholder="00.000.000/0000-00"
    )
    _tipo_opcoes = list(ia_pi_empresas.TIPOS_ENTIDADE.keys())
    _tipo_labels = list(ia_pi_empresas.TIPOS_ENTIDADE.values())
    _tipo_idx = _col_tipo.selectbox(
        "Tipo de Entidade",
        options=range(len(_tipo_opcoes)),
        format_func=lambda i: _tipo_labels[i],
        key="pi_tipo_select",
    )
    _tipo_entidade_pi = _tipo_opcoes[_tipo_idx]

    _hip_opcoes = dict(ia_pi_empresas.HIPOTESES_POR_TIPO[_tipo_entidade_pi])
    _hip_chaves = list(_hip_opcoes.keys())
    _hip_labels_pi = list(_hip_opcoes.values())
    _hip_idx = st.selectbox(
        "Hipótese legal",
        options=range(len(_hip_chaves)),
        format_func=lambda i: _hip_labels_pi[i],
        key="pi_hipotese_select",
    )
    _hipotese_pi = _hip_chaves[_hip_idx]
```

- [ ] **Step 2: Adicionar `pi_tipo_entidade` ao cleanup no botão "Consultar empresa"**

Localizar o loop de limpeza de session_state no `if st.button("Consultar empresa", ...)`:
```python
        for _k in ("pi_etapa", "pi_dados", "pi_cnpj", "pi_hipotese",
                   "pi_respostas", "pi_parecer", "pi_pdf"):
            st.session_state.pop(_k, None)
```

Substituir por:
```python
        for _k in ("pi_etapa", "pi_dados", "pi_cnpj", "pi_hipotese",
                   "pi_tipo_entidade", "pi_respostas", "pi_parecer", "pi_pdf"):
            st.session_state.pop(_k, None)
```

E logo após `st.session_state["pi_hipotese"] = _hipotese_pi`, acrescentar:
```python
            st.session_state["pi_tipo_entidade"] = _tipo_entidade_pi
```

- [ ] **Step 3: Atualizar a chamada a `ia_pi_empresas.avaliar()` no `app.py`**

Localizar a chamada (em torno da linha 643):
```python
                        _parecer_pi = ia_pi_empresas.avaliar(
                            _respostas_pi,
                            st.session_state["pi_hipotese"],
                            _texto_pi,
                            _api_key_pi,
                            _modelo_pi,
                        )
```

Substituir por:
```python
                        _parecer_pi = ia_pi_empresas.avaliar(
                            _respostas_pi,
                            st.session_state["pi_hipotese"],
                            _texto_pi,
                            _api_key_pi,
                            _modelo_pi,
                            tipo_entidade=st.session_state.get(
                                "pi_tipo_entidade", "empresa_privada"
                            ),
                        )
```

- [ ] **Step 4: Atualizar a chamada a `relatorio_pi_empresas.gerar_pdf()` no `app.py`**

Localizar (em torno da linha 655):
```python
                        st.session_state["pi_pdf"] = relatorio_pi_empresas.gerar_pdf(
                            cnpj=st.session_state["pi_cnpj"],
                            razao_social=_razao_pi,
                            hipotese=st.session_state["pi_hipotese"],
                            parecer=_parecer_pi,
                        )
```

Substituir por:
```python
                        st.session_state["pi_pdf"] = relatorio_pi_empresas.gerar_pdf(
                            cnpj=st.session_state["pi_cnpj"],
                            razao_social=_razao_pi,
                            hipotese=st.session_state["pi_hipotese"],
                            parecer=_parecer_pi,
                            tipo_entidade=st.session_state.get(
                                "pi_tipo_entidade", "empresa_privada"
                            ),
                        )
```

- [ ] **Step 5: Adicionar label de tipo de entidade no resultado (Etapa 3)**

Localizar, dentro do bloco `if st.session_state.get("pi_etapa", 0) >= 3:`, logo após `st.markdown("### Resultado da Avaliação")`:

```python
        st.markdown("### Resultado da Avaliação")
```

Acrescentar imediatamente abaixo:
```python
        _tipo_label_pi = ia_pi_empresas.TIPOS_ENTIDADE.get(
            st.session_state.get("pi_tipo_entidade", "empresa_privada"), "Empresa Privada"
        )
        st.caption(f"Tipo de Entidade: {_tipo_label_pi}")
```

- [ ] **Step 6: Remover o alias `HIPOTESES` de `ia_pi_empresas.py`**

Localizar e remover a linha:
```python
HIPOTESES = HIPOTESES_POR_TIPO["empresa_privada"]  # alias temporário — removido na Task 3
```

- [ ] **Step 7: Rodar a suite completa de testes**

```bash
cd ~/Documents/Daysival && python3 -m pytest tests/ -v
```

Esperado: ~224 passed (214 originais + 7 novos em test_ia_pi_empresas + 3 novos em test_relatorio_pi_empresas), 0 falhas.

- [ ] **Step 8: Commit**

```bash
cd ~/Documents/Daysival && git add app.py ia_pi_empresas.py && git commit -m "feat(app): Módulo 3 completo — seletor de tipo de entidade (Adm. Pública e OSC) na aba5"
```
