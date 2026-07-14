# Módulo 5 — Auditoria de Termo de Referência (TR)

## Objetivo

Analisar automaticamente Termos de Referência de licitações públicas brasileiras, identificando conformidade com a IN SEGES 81/2022 e a Lei 14.133/2021. Para TRs de TIC, aplica adicionalmente a IN SGD 21/2024.

O módulo recebe o TR em PDF ou DOCX, classifica o tipo de objeto (serviço, bem ou TIC) e retorna um parecer estruturado por dimensões obrigatórias, pontos críticos e recomendações, com geração de relatório em PDF.

---

## Arquitetura

Padrão type-aware idêntico ao `ia_recebimento.py`. Um único módulo de análise com `_SISTEMA_POR_TIPO` que despacha para o system prompt correto conforme o tipo de objeto selecionado pelo usuário.

```
upload (PDF/DOCX)
       │
       ▼
etp_extrator.py          ← reutilizado sem modificação
       │
       ▼
ia_tr.analisar_tr(texto, tipo_objeto, api_key, modelo)
       │
       ├── tipo="servico" → _SISTEMA_POR_TIPO["servico"] → 9 dimensões
       ├── tipo="bem"     → _SISTEMA_POR_TIPO["bem"]     → 8 dimensões
       └── tipo="tic"     → _SISTEMA_POR_TIPO["tic"]     → 9 dimensões
                │
                ▼
          dict (parecer)
                │
        ┌───────┴────────┐
        ▼                ▼
    app.py          relatorio_tr.py
   (UI Streamlit)    (PDF ReportLab)
```

---

## Arquivos

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `ia_tr.py` | Criar | Análise IA type-aware — 3 tipos, system prompts, normalização |
| `relatorio_tr.py` | Criar | Geração de PDF do parecer de TR |
| `app.py` | Modificar | Nova aba7 "📝 Auditoria de TR" |
| `tests/test_ia_tr.py` | Criar | 8 testes unitários do analisador |
| `tests/test_relatorio_tr.py` | Criar | 4 testes de geração de PDF |
| `etp_extrator.py` | Reutilizar | Extração de texto PDF/DOCX (sem modificação) |
| `ia_utils.py` | Reutilizar | `chamar_anthropic`, `extrair_json` (sem modificação) |

---

## Tipos de objeto

```python
TIPOS_OBJETO_TR = {
    "servico": "Serviço",
    "bem":     "Bem / Material",
    "tic":     "Serviço de TIC",
}
```

---

## Dimensões por tipo

### Serviços — 9 dimensões (IN SEGES 81/2022, Art. 6º XXIII + Lei 14.133/2021 Art. 18)

| Chave JSON | O que avalia |
|---|---|
| `descricao_objeto` | Clareza da descrição, vinculação ao PCA, código CATMAT/CATSER |
| `fundamentacao` | Necessidade da contratação, alinhamento com planejamento institucional |
| `requisitos_tecnicos` | Especificações de qualidade, desempenho, compatibilidade |
| `modelo_execucao` | Local, prazo, frequência, materiais/equipamentos, regras de subcontratação |
| `modelo_gestao` | Fiscalização, indicadores de desempenho (ANS), forma de recebimento |
| `criterio_medicao` | Unidade de medida, forma de pagamento, periodicidade |
| `criterio_julgamento` | Tipo de licitação, critério (menor preço / técnica e preço), ponderação |
| `estimativa_preco` | Metodologia de pesquisa, fontes (PNCP, painéis), valor total e unitário |
| `qualificacao_habilitacao` | Requisitos de habilitação técnica e jurídica proporcionais ao objeto |

### Bens/Materiais — 8 dimensões (IN SEGES 81/2022)

| Chave JSON | O que avalia |
|---|---|
| `especificacao_tecnica` | Descrição completa, marca de referência com justificativa quando necessária |
| `justificativa_quantidade` | Histórico de consumo, previsão de demanda, sazonalidade |
| `qualificacao_tecnica` | Homologação, certificações INMETRO/ABNT obrigatórias |
| `garantia_assistencia` | Prazo, condições, rede autorizada, fornecimento de peças |
| `condicoes_entrega` | Prazo, local, embalagem, frete, responsabilidades |
| `criterio_julgamento` | Menor preço ou maior desconto, estratégia de lote vs item |
| `estimativa_preco` | Pesquisa de mercado, fontes válidas, memória de cálculo |
| `sustentabilidade` | Critérios ambientais obrigatórios (IN SLTI 01/2010, Art. 225 CF/88) |

### TIC — 9 dimensões (IN SGD 21/2024 + IN SEGES 81/2022)

| Chave JSON | O que avalia |
|---|---|
| `alinhamento_pdtic` | PDTIC vigente, catálogo de soluções de TIC, vínculo com portfólio |
| `analise_viabilidade` | AVC completa: make-or-buy, análise de mercado, alternativas descartadas |
| `solucao_ti` | Solução escolhida com justificativa técnica, padrões de interoperabilidade |
| `criterios_aceite_ans` | ANS/SLA definidos, indicadores mensuráveis, penalidades por descumprimento |
| `equipe_tecnica` | INTECTI designada (Portaria SGD), competências exigidas da contratada |
| `seguranca_lgpd` | Requisitos de segurança da informação, classificação de dados, LGPD (Lei 13.709/2018) |
| `modelo_execucao` | Metodologia (ágil/cascata), marcos, entregáveis, critérios de aceite por fase |
| `transicao_contratual` | Plano de transição no início e no encerramento, knowledge transfer |
| `estimativa_preco` | Benchmark de mercado, composição de custos, métricas (UCP/PF/hora) |

---

## Interface `ia_tr.py`

```python
TIPOS_OBJETO_TR: types.MappingProxyType[str, str]
# {"servico": "Serviço", "bem": "Bem / Material", "tic": "Serviço de TIC"}

def analisar_tr(
    texto: str,
    tipo_objeto: str,       # "servico" | "bem" | "tic"
    api_key: str,
    modelo: str = "claude-haiku-4-5-20251001",
) -> dict:
    """
    Retorna dict com:
      adequacao_geral: "ADEQUADO" | "ADEQUADO COM RESSALVAS" | "INADEQUADO"
      dimensoes: {chave: {"status": "ok"|"alerta"|"critico", "descricao": str}}
      pontos_criticos: list[str]
      recomendacoes: list[str]
      base_legal: list[str]
    Levanta ValueError para tipo_objeto inválido.
    Levanta RuntimeError para falha de API ou JSON inválido.
    """
```

### Formato JSON de saída

```json
{
  "adequacao_geral": "ADEQUADO | ADEQUADO COM RESSALVAS | INADEQUADO",
  "dimensoes": {
    "<chave>": {"status": "ok|alerta|critico", "descricao": "texto da avaliação"}
  },
  "pontos_criticos": ["item 1", "item 2"],
  "recomendacoes": ["recomendação 1"],
  "base_legal": ["IN SEGES 81/2022", "Lei 14.133/2021, art. 6º, XXIII"]
}
```

### Normalização de `adequacao_geral`

Valores válidos: `{"ADEQUADO", "ADEQUADO COM RESSALVAS", "INADEQUADO"}`.
Qualquer valor fora desse conjunto é normalizado para `"INADEQUADO"`.
Idêntico ao padrão de `ia_etp.py`.

### Tratamento de erros (padrão split try/except)

```python
try:
    bruto = _chamar_anthropic(...)
except urllib.error.HTTPError as exc:
    # lê body, levanta RuntimeError("Falha na API Anthropic: HTTP {code}...")
except (urllib.error.URLError, OSError) as exc:
    raise RuntimeError(f"Falha na API Anthropic: {exc}") from exc

try:
    parecer = _extrair_json(bruto)
except ValueError as exc:
    raise RuntimeError(f"Resposta da API não contém JSON válido: {exc}") from exc
```

---

## Interface `relatorio_tr.py`

```python
def gerar_pdf(
    nome_objeto: str,       # título/descrição do TR
    tipo_objeto: str,       # "servico" | "bem" | "tic"
    parecer: dict,
) -> bytes:
    """Retorna bytes do PDF gerado."""
```

Layout idêntico ao `relatorio_etp.py`:
- Cabeçalho: "IA-Licita — RM Vértice Digital" + "Auditoria de Termo de Referência"
- Metadados: tipo de objeto, data de geração
- Badge colorido de `adequacao_geral` (verde/laranja/vermelho)
- Tabela de dimensões com ícone de status [OK] / [ALERTA] / [CRITICO]
- Seção de pontos críticos (lista numerada)
- Seção de recomendações (lista numerada)
- Base legal
- Rodapé: "Gerado por IA-Licita — RM Vértice Digital. Sujeito a verificação humana."

Cores de badge: `COR_STATUS_HEX` de `ia_utils.py` — `ok` → verde, `alerta` → laranja, `critico` → vermelho.

---

## UI — aba7 em `app.py`

Aba: `"📝 Auditoria de TR"`

Adicionada em `st.tabs([..., "📝 Auditoria de TR"])` como sétimo elemento.

Fluxo dentro da aba:
1. `st.subheader("Auditoria de Termo de Referência — IN SEGES 81/2022")`
2. `st.radio("Tipo de objeto", ["Serviço", "Bem / Material", "Serviço de TIC"])` → mapeia para `"servico"`, `"bem"`, `"tic"`
3. `st.file_uploader("Envie o TR em PDF ou DOCX", type=["pdf", "docx"])`
4. Botão "Analisar TR" — desabilitado se `_get_api_key()` retornar `None`
5. Ao clicar: extrai texto com `texto, avisos = etp_extrator.extrair_texto([arquivo])` (retorna `tuple[str, list[str]]`), exibe avisos se houver, chama `ia_tr.analisar_tr()`, exibe resultado
6. Resultado: badge de adequação geral, expandir/colapsar por dimensão, pontos críticos, recomendações
7. `st.download_button` para PDF gerado por `relatorio_tr.gerar_pdf()`

Reutiliza `_get_api_key()` e `_safe_md()` já definidos em `app.py`.

---

## Testes

### `tests/test_ia_tr.py` — 8 testes

| Teste | Verifica |
|---|---|
| `test_retorna_estrutura_correta_servico` | Chaves obrigatórias presentes para tipo "servico" |
| `test_retorna_estrutura_correta_bem` | Chaves obrigatórias para tipo "bem" |
| `test_retorna_estrutura_correta_tic` | Chaves obrigatórias para tipo "tic" |
| `test_tipo_invalido_levanta_value_error` | `ValueError` para tipo desconhecido |
| `test_adequacao_invalida_normalizada` | Valor fora do enum → `"INADEQUADO"` |
| `test_httperror_inclui_body_na_mensagem` | HTTP 401 → `RuntimeError` com body |
| `test_resposta_sem_json_levanta_runtime_error` | Resposta não-JSON → `RuntimeError` claro |
| `test_content_null_nao_quebra` | `{"content": null}` na resposta → `RuntimeError` |

Todos usam `@patch("ia_utils.urllib.request.urlopen")` — padrão estabelecido.

### `tests/test_relatorio_tr.py` — 4 testes

| Teste | Verifica |
|---|---|
| `test_retorna_bytes_nao_vazios` | `gerar_pdf()` retorna `bytes` com len > 0 |
| `test_comeca_com_magic_bytes_pdf` | Primeiros bytes são `b"%PDF"` |
| `test_tamanho_minimo` | PDF tem pelo menos 1 KB |
| `test_todos_os_tipos_de_objeto_nao_quebram` | Serviço, Bem e TIC geram PDF sem exceção |

---

## Base legal por tipo

**Serviços:**
- IN SEGES/MGI 81/2022 (Termo de Referência e Projeto Básico)
- Lei 14.133/2021, Art. 6º, XXIII (definição de TR)
- Lei 14.133/2021, Art. 40 (conteúdo do edital e TR)

**Bens:**
- IN SEGES/MGI 81/2022
- Lei 14.133/2021, Art. 6º, XXIII
- IN SLTI/MPOG 01/2010 (sustentabilidade ambiental)

**TIC:**
- IN SGD/ME 21/2024 (contratações de soluções de TIC)
- IN SEGES/MGI 81/2022
- Lei 14.133/2021, Art. 6º, XXIII
- Lei 13.709/2018 — LGPD (proteção de dados)
