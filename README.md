# IA-Licita — Auditoria de Editais

Ferramenta de auditoria automática de editais de licitação pública com base na **Lei 14.133/2021** (Nova Lei de Licitações). Desenvolvida pela **RM Vértice Digital**.

---

## O que faz

- Recebe um edital em PDF e gera um relatório de conformidade em segundos
- Detecta inconformidades, alertas e pontos a revisar com fundamento no texto da lei
- Calcula um índice de risco de nulidade (0–100)
- Gera relatório em HTML para download e envio ao cliente
- Suporta editais de qualquer modalidade (pregão, concorrência, credenciamento) e tamanho (testado de 0.5 MB a 22 MB)

### Duas camadas de análise

| Camada | O que faz | Requisito |
|--------|-----------|-----------|
| Regras automáticas | 30 checklist items com regex e lógica determinística | Nenhum |
| IA semântica | Análise contextual com Claude Haiku, detecta incoerências internas, erros aritméticos, datas conflitantes, URLs malformadas | Chave de API Anthropic |

---

## Como rodar localmente

### Requisitos

- Python 3.9+
- Conta na [Anthropic](https://console.anthropic.com) com créditos (opcional, para análise por IA)

### Instalação

```bash
git clone https://github.com/rmfribeiro/Licita-o.git
cd Licita-o
pip install -r requirements-dev.txt   # inclui pytest para rodar os testes
```

### Rodar os testes

```bash
python3 -m pytest tests/ -v
```

### Executar

```bash
# Configure os segredos locais (chaves de API, senha)
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edite .streamlit/secrets.toml com seus valores reais

streamlit run app.py
```

Acesse `http://localhost:8501`, envie um PDF e aguarde o resultado.

---

## Estrutura

```
app.py                    — Interface Streamlit (6 abas)
analisador.py             — Motor de regras e cálculo de risco de edital
ia_semantica.py           — Análise semântica de edital (Claude)
ia_utils.py               — Utilitários compartilhados: API Anthropic, helpers
ia_integridade.py         — Diagnóstico de integridade do processo licitatório
ia_etp.py                 — Análise do Estudo Técnico Preliminar (ETP)
ia_ddi.py                 — Due Diligence de Integridade do licitante
ia_contratos.py           — Análise de alterações contratuais (reajuste/repactuação/reequilíbrio)
ia_recebimento.py         — Monitor de Recebimento Contratual (Art. 140 Lei 14.133/2021)
ia_pi_empresas.py         — Avaliação de Programa de Integridade
ddi_consultas.py          — Consultas CGU: CEIS, CNEP, Pro-Ética, CNPJ
etp_extrator.py           — Extração de texto de ETP em PDF/DOCX
rag.py                    — Busca semântica nos artigos da lei
branding.py               — Logo e identidade visual
relatorio_contratos.py    — PDF de alterações contratuais
relatorio_ddi.py          — PDF de Due Diligence de Integridade
relatorio_etp.py          — PDF de análise de ETP
relatorio_integridade.py  — PDF de diagnóstico de integridade
relatorio_pi_empresas.py  — PDF de avaliação de PI
relatorio_recebimento.py  — PDF de recebimento contratual
regras_14133.json         — Checklist de regras da Lei 14.133/2021
base_juridica.json        — Artigos da lei para fundamentos legais
branding.json             — Configuração de marca (nome, logo, cores)
requirements.txt          — Dependências de produção
requirements-dev.txt      — Dependências de desenvolvimento (pytest)
DEPLOY.md                 — Guia de publicação no Streamlit Community Cloud
```

---

## Configuração avançada

| Variável de ambiente | Padrão | Descrição |
|---------------------|--------|-----------|
| `ANTHROPIC_API_KEY` | — | Chave de API para análise por IA |
| `IA_LICITA_MODELO` | `claude-haiku-4-5-20251001` | Modelo Claude a usar |

---

## Deploy na nuvem

Veja [DEPLOY.md](DEPLOY.md) para publicar gratuitamente no **Streamlit Community Cloud**.

---

## Aviso legal

Ferramenta de apoio — não substitui o parecer jurídico. Os apontamentos devem ser confirmados por profissional habilitado.

---

**RM Vértice Digital** — contato@rmverticedigital.com.br
