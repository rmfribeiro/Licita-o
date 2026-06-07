# tests/test_relatorio_tr.py
from __future__ import annotations
import relatorio_tr


def _parecer_servico() -> dict:
    return {
        "adequacao_geral": "ADEQUADO COM RESSALVAS",
        "dimensoes": {
            "descricao_objeto":         {"status": "ok",     "descricao": "Objeto claro."},
            "fundamentacao":            {"status": "ok",     "descricao": "Justificado."},
            "requisitos_tecnicos":      {"status": "alerta", "descricao": "Incompleto."},
            "modelo_execucao":          {"status": "ok",     "descricao": "Definido."},
            "modelo_gestao":            {"status": "ok",     "descricao": "Fiscalização prevista."},
            "criterio_medicao":         {"status": "ok",     "descricao": "Unidade definida."},
            "criterio_julgamento":      {"status": "ok",     "descricao": "Menor preço."},
            "estimativa_preco":         {"status": "alerta", "descricao": "Fontes insuficientes."},
            "qualificacao_habilitacao": {"status": "ok",     "descricao": "Proporcional."},
        },
        "pontos_criticos": ["Requisitos incompletos."],
        "recomendacoes": ["Detalhar especificações."],
        "base_legal": ["IN SEGES/MGI 81/2022", "Lei 14.133/2021, Art. 6º, XXIII"],
    }


class TestGerarPdf:
    def test_retorna_bytes_nao_vazios(self):
        pdf = relatorio_tr.gerar_pdf("Serviço de Limpeza", "servico", _parecer_servico())
        assert isinstance(pdf, bytes)
        assert len(pdf) > 0

    def test_comeca_com_magic_bytes_pdf(self):
        pdf = relatorio_tr.gerar_pdf("Aquisição de Computadores", "bem", {
            "adequacao_geral": "ADEQUADO",
            "dimensoes": {
                "especificacao_tecnica":    {"status": "ok", "descricao": "Completa."},
                "justificativa_quantidade": {"status": "ok", "descricao": "Histórico."},
                "qualificacao_tecnica":     {"status": "ok", "descricao": "INMETRO."},
                "garantia_assistencia":     {"status": "ok", "descricao": "24 meses."},
                "condicoes_entrega":        {"status": "ok", "descricao": "30 dias."},
                "criterio_julgamento":      {"status": "ok", "descricao": "Menor preço."},
                "estimativa_preco":         {"status": "ok", "descricao": "Pesquisa ok."},
                "sustentabilidade":         {"status": "ok", "descricao": "Critérios ok."},
            },
            "pontos_criticos": [],
            "recomendacoes": [],
            "base_legal": ["IN SEGES/MGI 81/2022"],
        })
        assert pdf[:4] == b"%PDF"

    def test_tamanho_minimo(self):
        pdf = relatorio_tr.gerar_pdf("Sistema de Gestão", "tic", {
            "adequacao_geral": "INADEQUADO",
            "dimensoes": {
                "alinhamento_pdtic":    {"status": "critico", "descricao": "Ausente."},
                "analise_viabilidade":  {"status": "critico", "descricao": "AVC ausente."},
                "solucao_ti":           {"status": "alerta",  "descricao": "Incompleta."},
                "criterios_aceite_ans": {"status": "ok",      "descricao": "ANS ok."},
                "equipe_tecnica":       {"status": "ok",      "descricao": "INTECTI ok."},
                "seguranca_lgpd":       {"status": "alerta",  "descricao": "LGPD parcial."},
                "modelo_execucao":      {"status": "ok",      "descricao": "Ágil."},
                "transicao_contratual": {"status": "critico", "descricao": "Ausente."},
                "estimativa_preco":     {"status": "ok",      "descricao": "Benchmark ok."},
            },
            "pontos_criticos": ["PDTIC ausente."],
            "recomendacoes": ["Elaborar PDTIC."],
            "base_legal": ["IN SGD/ME 21/2024"],
        })
        assert len(pdf) > 1024

    def test_todos_os_tipos_de_objeto_nao_levantam_excecao(self):
        parecer_base = {
            "adequacao_geral": "ADEQUADO",
            "dimensoes": {},
            "pontos_criticos": [],
            "recomendacoes": [],
            "base_legal": [],
        }
        for tipo in ("servico", "bem", "tic"):
            pdf = relatorio_tr.gerar_pdf("Objeto de teste", tipo, parecer_base)
            assert pdf[:4] == b"%PDF", f"Falhou para tipo={tipo}"
