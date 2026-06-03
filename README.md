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
pip install -r requirements.txt
```

### Executar

```bash
# Sem IA (só regras automáticas)
streamlit run app.py

# Com IA
ANTHROPIC_API_KEY="sk-ant-..." streamlit run app.py
```

Acesse `http://localhost:8501`, envie um PDF e aguarde o resultado.

---

## Estrutura

```
app.py              — Interface Streamlit
analisador.py       — Motor de regras e cálculo de risco
ia_semantica.py     — Integração com API Anthropic (Claude)
rag.py              — Busca semântica nos artigos da lei
branding.py         — Logo e identidade visual
regras_14133.json   — 30 regras da Lei 14.133/2021
base_juridica.json  — Artigos da lei para fundamentos legais
requirements.txt    — Dependências Python
DEPLOY.md           — Instruções para publicar no Streamlit Cloud
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
