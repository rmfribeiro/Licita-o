# Módulo DDI — Due Diligence de Integridade
**IA-Licita / RM Vértice Digital**
**Data:** 2026-06-03 (revisado após mapeamento normativo completo)

---

## Arcabouço Legal e Normativo

| Instrumento | Data | Papel no módulo |
|---|---|---|
| Lei 12.846/2013 | 01/08/2013 | Fundação — responsabilidade objetiva de PJ por atos lesivos à APF |
| Decreto 8.420/2015 | 18/03/2015 | 16 parâmetros do Programa de Integridade |
| Portaria SEGES/ME 8.678/2021 | 19/07/2021 | Define DDI (art. 2º, III) como procedimento de verificação de risco de integridade |
| Lei 14.133/2021 | 01/04/2021 | Arts. 25 §4º (PI obrigatório), 60 IV (desempate), 156 §1º (sanções), 163 (reabilitação) |
| Decreto 12.304/2024 | 09/12/2024 | Regulamenta arts. 25/60/163 — grande vulto: contratos > R$ 239M; CGU avalia e monitora |
| Portaria Normativa CGU 203/2025 | 15/04/2025 | Programa Empresa Pró-Ética — reconhecimento público de PI voluntário e exemplar |
| IN CGU 46/2025 | Abril/2025 | Parâmetros de avaliação do PI para o ciclo Empresa Pró-Ética 2025-2026 |
| Portaria Normativa SE/CGU 226/2025 | 09/09/2025 | Metodologia e prazos para avaliação de PI em contratos de grande vulto |
| SERPRO GR-009 v.02 | Agosto/2025 | Framework de referência — avaliação de integridade de terceiros |

---

## 1. Objetivo

Adicionar ao IA-Licita um módulo independente de Due Diligence de Integridade (DDI) que, dado um CNPJ e o valor do contrato, consulta automaticamente fontes públicas, processa um FID simplificado preenchido pelo usuário, aciona a IA para emitir um parecer de integridade multidimensional fundamentado no arcabouço normativo completo e disponibiliza relatório em PDF para download.

---

## 2. Integração com o App Existente

- Abordagem: **tabs** no `app.py` existente via `st.tabs()`
- Tab 1: `📄 Auditoria de Edital` — código atual sem nenhuma alteração (zero risco de regressão)
- Tab 2: `🔍 Due Diligence de Integridade` — novo módulo DDI

O conteúdo atual do `app.py` é envolvido em `with aba1:` sem qualquer outra modificação.

---

## 3. Arquivos Novos

| Arquivo | Responsabilidade |
|---|---|
| `ddi_consultas.py` | Consulta APIs: Receita Federal, CEIS, CNEP, Empresa Pró-Ética; lógica de grande vulto |
| `ia_ddi.py` | Prompt DDI multidimensional + chamada Anthropic API → parecer JSON estruturado |
| `relatorio_ddi.py` | Geração de PDF com reportlab (já no requirements.txt) |

---

## 4. Fluxo Completo

```
Usuário: CNPJ + Valor do contrato
      ↓
[ddi_consultas.py]
  → Receita Federal (publica.cnpj.ws) — dados cadastrais e societários
  → CEIS (Portal Transparência) — sanções/impedimentos
  → CNEP (Portal Transparência) — punições Lei 12.846
  → Empresa Pró-Ética (CGU) — reconhecimento voluntário de PI
  → Lógica local: valor > R$ 239M? → grande_vulto = True
      ↓
[app.py — Tab 2, Etapa 2]
  → FID simplificado — usuário responde 5 perguntas sobre o licitante
      ↓
[ia_ddi.py]
  → Anthropic API (claude-haiku-4-5-20251001)
  → Parecer JSON multidimensional (5 dimensões)
      ↓
[app.py — Tab 2, Etapa 3]
  → Exibe resultado: badges de risco por dimensão + achados + parecer
  → Botão "Baixar Relatório PDF"
      ↓
[relatorio_ddi.py]
  → PDF para download
```

---

## 5. Camada de Dados (`ddi_consultas.py`)

### Funções públicas
```python
def consultar(cnpj: str, valor_contrato: float) -> dict
def _validar_cnpj(cnpj: str) -> bool          # validação local antes de qualquer chamada
def _buscar_receita(cnpj: str) -> dict | None
def _buscar_ceis(cnpj: str) -> list
def _buscar_cnep(cnpj: str) -> list
def _verificar_pro_etica(cnpj: str) -> bool | None
```

### Fonte 1 — Receita Federal (`publica.cnpj.ws/cnpj/{cnpj}` — sem chave)
- Razão social, nome fantasia
- Situação cadastral: ATIVA / SUSPENSA / BAIXADA / INAPTA
- CNAE principal e secundários, porte, data de abertura, endereço
- Quadro societário completo (sócios e administradores)

### Fonte 2 — CEIS (`api.portaldatransparencia.gov.br/api-de-dados/ceis` — requer `CGU_API_KEY`)
- Registros de impedimento ou suspensão de contratar com a APF
- Órgão sancionador, fundamentação legal, período da sanção, situação atual

### Fonte 3 — CNEP (`api.portaldatransparencia.gov.br/api-de-dados/cnep` — requer `CGU_API_KEY`)
- Punições pela Lei Anticorrupção (Lei 12.846/2013)
- Tipo: multa, proibição de contratar, acordo de leniência

### Fonte 4 — Empresa Pró-Ética (CGU — sem API pública documentada)
- Estratégia primária: scraping da lista pública disponível no portal CGU
- Estratégia de fallback: campo toggle na UI — "Empresa consta no Empresa Pró-Ética?"
- Retorna `True` (consta), `False` (não consta) ou `None` (não verificável automaticamente)

### Lógica local — Grande Vulto
- `valor_contrato > 239_000_000` → `grande_vulto = True`
- Fundamentação: Decreto 12.304/2024 — PI obrigatório em até 6 meses após assinatura
- Não requer chamada externa

### Tratamento de erros
- CNPJ inválido: validação local (14 dígitos + verificação dos dígitos verificadores) antes de qualquer chamada de rede
- API fora do ar / timeout (10s por fonte): resultado parcial com aviso explícito; análise prossegue com fontes disponíveis
- Empresa não encontrada em fonte: retorna `None`; IA trata ausência como dado e informa no parecer

### Configuração
- `CGU_API_KEY`: via `st.secrets` ou variável de ambiente (mesmo padrão da `ANTHROPIC_API_KEY` já existente)
- Sem `CGU_API_KEY`: CEIS e CNEP são pulados com aviso de consulta parcial na tela

---

## 6. FID Simplificado — Formulário de Integridade e Diligência

Baseado no framework SERPRO GR-009 v.02, adaptado para 5 perguntas objetivas.
Preenchido pelo usuário na Tab 2 (Etapa 2), após a consulta automática.

| # | Pergunta | Opções |
|---|---|---|
| 1 | A empresa possui Código de Ética ou Conduta formal e público? | Sim / Não / Não sei |
| 2 | Há canal de denúncias ativo e acessível a terceiros? | Sim / Não / Não sei |
| 3 | A empresa realiza treinamentos periódicos de integridade? | Sim / Não / Não sei |
| 4 | Há política de conflito de interesses documentada? | Sim / Não / Não sei |
| 5 | A empresa possui auditorias internas ou externas de integridade? | Sim / Não / Não sei |

As respostas são incluídas no payload enviado à IA como a Dimensão 4 do parecer.
Validade do FID: 12 meses (informado ao usuário no relatório, conforme framework SERPRO).

---

## 7. Camada de IA (`ia_ddi.py`)

### Função principal
```python
def analisar(dados: dict, fid: dict) -> dict
```

### Regras de piso automático (aplicadas antes da chamada à IA)
Garantem um risco mínimo independente do parecer da IA:
- Registro ativo no CEIS → risco mínimo **ALTO**
- Registro ativo no CNEP → risco mínimo **MÉDIO**
- Situação cadastral SUSPENSA, BAIXADA ou INAPTA → alerta obrigatório, risco mínimo **MÉDIO**
- Grande vulto + nenhuma evidência de PI (Empresa Pró-Ética = False + FID negativo) → alerta obrigatório **MÉDIO**

### Cinco dimensões do parecer
O prompt instrui o modelo a avaliar cada dimensão separadamente e emitir um risco consolidado:

```
Dimensão 1 — Situação Cadastral       (fonte: Receita Federal)
Dimensão 2 — Sanções e Punições       (fonte: CEIS + CNEP)
Dimensão 3 — Programa de Integridade  (fonte: Empresa Pró-Ética + lógica grande_vulto)
Dimensão 4 — Autoavaliação (FID)      (fonte: respostas do formulário)
Dimensão 5 — Contexto do Contrato     (fonte: valor informado pelo usuário)
```

### Estrutura do parecer (JSON)
```json
{
  "risco_geral": "ALTO | MÉDIO | BAIXO | SEM RISCO IDENTIFICADO",
  "dimensoes": {
    "situacao_cadastral": {
      "status": "ok | alerta | critico",
      "descricao": "..."
    },
    "sancoes": {
      "status": "ok | alerta | critico",
      "achados": [
        {"fonte": "CEIS | CNEP", "descricao": "...", "gravidade": "alta | média | baixa"}
      ]
    },
    "programa_integridade": {
      "status": "ok | alerta | critico",
      "obrigatorio": true,
      "pro_etica": false,
      "descricao": "..."
    },
    "fid": {
      "status": "ok | alerta | critico",
      "inconsistencias": ["..."],
      "descricao": "..."
    },
    "contexto_contrato": {
      "status": "ok | alerta | critico",
      "grande_vulto": true,
      "descricao": "..."
    }
  },
  "resumo": "frase direta sobre o perfil de integridade",
  "recomendacao": "orientação objetiva ao gestor público",
  "base_legal": [
    "Portaria SEGES/ME 8.678/2021, art. 2º, III",
    "Decreto 12.304/2024",
    "Portaria Normativa SE/CGU 226/2025",
    "Lei 14.133/2021, art. 25 §4º"
  ],
  "validade_fid": "12 meses a partir da data desta consulta"
}
```

### Modelo
`claude-haiku-4-5-20251001` — configurável via variável de ambiente `IA_LICITA_MODELO`

---

## 8. Relatório PDF (`relatorio_ddi.py`)

### Função principal
```python
def gerar_pdf(cnpj: str, valor_contrato: float, dados: dict, fid: dict, parecer: dict) -> bytes
```

### Estrutura do documento
1. **Cabeçalho**: logo RM Vértice Digital + data/hora da consulta
2. **Identificação do licitante**: razão social, CNPJ, situação cadastral, porte, CNAE, sócios
3. **Índice de Risco Geral**: destaque visual colorido
   - ALTO → vermelho | MÉDIO → laranja | BAIXO → amarelo | SEM RISCO → verde
4. **Risco por Dimensão**: 5 badges coloridos (um por dimensão)
5. **Achados Detalhados**: tabela fonte / descrição / gravidade
6. **FID — Respostas e Análise**: perguntas + respostas + interpretação da IA
7. **Programa de Integridade**: status Empresa Pró-Ética + obrigatoriedade por valor
8. **Parecer de Integridade**: texto fundamentado com base legal completa
9. **Recomendação ao Gestor**: orientação objetiva
10. **Validade**: "Este FID tem validade de 12 meses a partir de [data]"
11. **Rodapé**: `"Gerado por IA-Licita — RM Vértice Digital. Sujeito à verificação humana."`

Usa `reportlab` (já presente em `requirements.txt`). Retorna `bytes` para `st.download_button`.

---

## 9. UI — Mudanças no `app.py`

### Imports adicionados
```python
import ddi_consultas
import ia_ddi
import relatorio_ddi
```

### Fluxo da Tab 2 em três etapas

**Etapa 1 — Identificação e consulta automática**
```python
cnpj = st.text_input("CNPJ do licitante (apenas números, 14 dígitos)")
valor = st.number_input("Valor do contrato (R$)", min_value=0.0, format="%.2f")
if st.button("Consultar fontes públicas", type="primary"):
    with st.spinner("Consultando Receita Federal, CEIS, CNEP e Empresa Pró-Ética..."):
        dados = ddi_consultas.consultar(cnpj, valor)
    st.session_state["ddi_dados"] = dados
    st.session_state["ddi_etapa"] = 2
```

**Etapa 2 — FID simplificado** (exibido após consulta bem-sucedida)
```python
if st.session_state.get("ddi_etapa") == 2:
    st.subheader("Formulário de Integridade e Diligência (FID)")
    # 5 perguntas via st.radio()
    if st.button("Gerar Parecer DDI", type="primary"):
        fid = {coletado do formulário}
        with st.spinner("Gerando parecer de integridade..."):
            parecer = ia_ddi.analisar(st.session_state["ddi_dados"], fid)
        st.session_state["ddi_parecer"] = parecer
        st.session_state["ddi_fid"] = fid
        st.session_state["ddi_etapa"] = 3
```

**Etapa 3 — Resultado**
```python
if st.session_state.get("ddi_etapa") == 3:
    # exibe risco geral colorido
    # exibe 5 badges de dimensão
    # exibe achados expandíveis
    # exibe parecer e recomendação
    pdf = relatorio_ddi.gerar_pdf(cnpj, valor, dados, fid, parecer)
    st.download_button("Baixar Relatório PDF", pdf, f"DDI_{cnpj}.pdf", "application/pdf")
```

---

## 10. Configuração

| Variável | Obrigatoriedade | Descrição |
|---|---|---|
| `ANTHROPIC_API_KEY` | Obrigatória | Já existente no projeto |
| `CGU_API_KEY` | Necessária para CEIS/CNEP | Nova — cadastro gratuito no Portal da Transparência |

Sem `CGU_API_KEY`: CEIS e CNEP são pulados; módulo roda com Receita Federal + Empresa Pró-Ética + FID e exibe aviso de consulta parcial.

---

## 11. Produto Completo — Roadmap

```
IA-Licita
├── Módulo 1 — Auditoria de Edital              ✅ pronto
├── Módulo 2 — DDI (este spec)                  🔧 próximo
├── Módulo 3 — Avaliação do PI (16 parâmetros)  ⬜ futuro
├── Módulo 4 — Monitor de Contratos             ⬜ futuro
├── Módulo 5 — Dosimetria de Sanções            ⬜ futuro
├── Módulo 6 — Reabilitação de Fornecedor       ⬜ futuro
├── Módulo 7 — Desempate por PI                 ⬜ futuro
├── Módulo 8 — Empresa Pró-Ética (standalone)   ⬜ futuro
└── Módulo 9 — FID completo (standalone)        ⬜ futuro
```

Módulos 8 e 9 estão incorporados de forma simplificada no Módulo 2 (este spec).

---

## 12. Fora de Escopo (nesta versão)

- Verificação de PEPs (Pessoas Expostas Politicamente) — requer API adicional
- Consulta ao SICAF — sem API pública disponível
- FID completo (21 parâmetros do Decreto 8.420) — Módulo 9 futuro
- Avaliação formal dos 16 parâmetros do PI — Módulo 3 futuro
- Monitoramento contínuo / alertas de mudança de status — Módulo 4 futuro
- Histórico de consultas DDI persistido em banco de dados
- Extensão para estados e municípios (proposta CGU em consulta pública, março/2026)
