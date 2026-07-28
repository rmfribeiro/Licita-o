# RM Lisura — Conformidade e Integridade nas Contratações Públicas

Plataforma de auditoria e apoio à decisão em contratações públicas, com base na
**Lei 14.133/2021**. Desenvolvida pela **RM Vértice Digital Inova Simples (I.S.)**
(CNPJ 68.118.290/0001-06). Marca depositada no INPI (processo nº 944589618).

> O nome vem de *lisura do certame* — é isso que a ferramenta ajuda a garantir.

---

## O que faz

Recebe documentos do processo licitatório e devolve, em minutos, relatórios
técnicos em PDF com fundamento legal citado artigo por artigo.

**Onde atua:** enquanto outras plataformas ajudam o órgão a *elaborar* os
documentos da fase preparatória, o RM Lisura **audita** o que já está pronto e
acompanha também a execução, a sanção e a defesa.

### Módulos

| Módulo | O que entrega |
|---|---|
| Auditoria de Edital | Conformidade com a Lei 14.133/2021 + índice de risco de nulidade (0–100) |
| Auditoria de TR | 9 dimensões obrigatórias (IN SEGES/MGI 81/2022) |
| Auditoria de ETP | Análise do Estudo Técnico Preliminar |
| Pesquisa de Mercado | Preços reais do **PNCP** ou de orçamentos, com mapa de preços e mediana saneada (IN SEGES/MGI 65/2021) |
| Due Diligence de Integridade | Consultas CEIS, CNEP, Pro-Ética e situação cadastral |
| Diagnóstico de Integridade | Maturidade do processo licitatório do órgão |
| Avaliação de PI | Programa de Integridade de empresas |
| Alterações Contratuais | Reajuste, repactuação e reequilíbrio |
| Monitor de Recebimento | Art. 140 da Lei 14.133/2021 |
| Dosimetria de Sanções | Dosimetria e minuta de decisão |
| Reabilitação de Fornecedor | Requisitos e minuta |
| Instituto da Diligência | Saneamento de falhas formais |

### Duas camadas de análise

| Camada | O que faz | Requisito |
|--------|-----------|-----------|
| Regras automáticas | Checklist determinístico com regex e lógica | Nenhum |
| IA semântica | Incoerências internas, erros aritméticos, datas conflitantes | Chave de API Anthropic |

---

## Acesso e cobrança

- **Cadastro com aprovação**: quem se cadastra fica pendente até o administrador liberar.
- **Login** por usuário ou e-mail, senha em bcrypt, recuperação por código enviado por e-mail.
- **Cobrança por uso**: cada relatório é registrado com nível e preço de referência.
  Planos: Avulso (3 relatórios de cortesia, uma única vez), Básico (20/mês),
  Profissional (50/mês) e Ilimitado. Ao atingir o limite, a geração é bloqueada.
- Painel do administrador mostra uso e cobrança sugerida por cliente.

Configuração completa em [CONFIGURAR_ACESSO.md](CONFIGURAR_ACESSO.md).

---

## Como rodar localmente

```bash
git clone https://github.com/rmfribeiro/Licita-o.git
cd Licita-o
pip install -r requirements.txt

cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# preencha SUPABASE_URL, SUPABASE_SERVICE_KEY, ANTHROPIC_API_KEY e (opcional) SMTP

python3 -m streamlit run app.py
```

Testes: `python3 -m pytest tests/ -q`

---

## Estrutura

```
app.py                      — Interface Streamlit (11 módulos em abas)
auth_db.py                  — Autenticação (Supabase): cadastro, aprovação, senha
uso_db.py                   — Contador de relatórios e limites por plano
precos.py                   — Tabela de preços, níveis e planos
analisador.py               — Motor de regras e índice de risco do edital
ia_*.py                     — Análises por IA de cada módulo
relatorio_*.py              — Geradores de PDF
pncp_busca.py               — Busca de preços reais no PNCP
ddi_consultas.py            — Consultas CGU (CEIS, CNEP, Pro-Ética)
schema_supabase.sql.txt— Schema do banco (usuários e uso)
```

---

## Publicação

Streamlit Community Cloud a partir deste repositório; segredos no painel de
Secrets. Ver [DEPLOY.md](DEPLOY.md). Uma rotina do GitHub Actions
(`.github/workflows/manter-acordado.yml`) visita o app a cada 4 horas para
evitar a hibernação do plano gratuito.

---

## Aviso legal

Ferramenta de apoio — **não substitui o parecer jurídico**. Os apontamentos,
cálculos e fundamentos legais, gerados inclusive por inteligência artificial,
devem ser conferidos e validados por profissional habilitado antes de qualquer
uso oficial.

---

**RM Vértice Digital** — contato@rmverticedigital.com.br
