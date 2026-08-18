from __future__ import annotations
import re
import ia_fid
import ia_utils
import relatorio_fid


def _texto_do_pdf(pdf: bytes) -> str:
    """Extrai o texto do PDF gerado. Conferir o objeto Python nao basta: o que o
    prefeito le e o PDF."""
    import pdfplumber
    import io
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        bruto = "\n".join((p.extract_text() or "") for p in doc.pages)
    # a quebra de linha do PDF parte frases no meio; para procurar texto,
    # normalizar o espaco em branco evita falso negativo
    return re.sub(r"\s+", " ", bruto)


def _dados():
    return {"razao_social": "Empresa XPTO Ltda", "cnpj": "12345678000195",
            "numero_edital": "PE 042/2024", "objeto": "Serviços de TI",
            "orgao": "Prefeitura Exemplo"}


def _parecer(**kw):
    base = {
        "necessita_diligencia": "SIM",
        "documentos_solicitados": [{
            "documento": "Certidão FGTS", "situacao": "vencido",
            "fundamento_legal": "Art. 64, I, Lei 14.133/2021", "prazo_dias": None,
        }],
        "pontos_de_atencao": [],
        "minuta_oficio": "OFÍCIO DE DILIGÊNCIA Nº ____",
        "prazo_resposta_sugerido": None,
        "conclusao": "Necessária a complementação.",
        "base_legal": ["Art. 64, I e II, Lei 14.133/2021"],
        "_documentos_analisados": [],
        "_conferencia_oficio": [],
    }
    base.update(kw)
    return base


class TestPrazo:
    def test_prazo_ausente_nunca_imprime_5(self):
        txt = _texto_do_pdf(relatorio_fid.gerar_pdf(_dados(), "habilitacao", _parecer()))
        assert "5 dias" not in txt
        assert "a fixar" in txt
        assert "não fixa prazo geral" in txt

    def test_prazo_presente_vem_com_ressalva_de_origem(self):
        p = _parecer(prazo_resposta_sugerido=10,
                     _documentos_analisados=[{"arquivo": "edital.pdf", "chars": 900}])
        txt = _texto_do_pdf(relatorio_fid.gerar_pdf(_dados(), "habilitacao", p))
        assert "10 dias" in txt
        assert "confirme na fonte" in txt.lower()
        assert "úteis ou corridos" in txt


class TestLastro:
    def test_sem_documento_anexado_o_aviso_aparece(self):
        txt = _texto_do_pdf(relatorio_fid.gerar_pdf(_dados(), "habilitacao", _parecer()))
        assert "NENHUM DOCUMENTO FOI ANEXADO" in txt

    def test_com_documento_o_manifesto_lista_os_arquivos(self):
        p = _parecer(_documentos_analisados=[{"arquivo": "fgts.pdf", "chars": 4321}])
        txt = _texto_do_pdf(relatorio_fid.gerar_pdf(_dados(), "habilitacao", p))
        assert "fgts.pdf" in txt
        assert "NENHUM DOCUMENTO FOI ANEXADO" not in txt


class TestNaoAvaliado:
    def test_badge_e_corpo_dizem_a_mesma_coisa(self):
        """A lição do Diagnóstico de Integridade: o selo foi corrigido e o corpo
        continuou afirmando o contrário."""
        p = _parecer(necessita_diligencia=ia_fid.RESULTADO_NAO_AVALIADO,
                     documentos_solicitados=[])
        txt = _texto_do_pdf(relatorio_fid.gerar_pdf(_dados(), "habilitacao", p))
        assert "NÃO AVALIADO" in txt
        assert "NÃO conclui pela necessidade nem pela desnecessidade" in txt
        assert "DILIGÊNCIA NECESSÁRIA" not in txt

    def test_divergencia_da_ia_e_impressa(self):
        p = _parecer(_divergencia_ia="NÃO")
        txt = _texto_do_pdf(relatorio_fid.gerar_pdf(_dados(), "habilitacao", p))
        assert "Divergência entre as duas leituras" in txt


class TestConferenciaNoPDF:
    def test_alertas_da_conferencia_saem_no_relatorio(self):
        p = _parecer(_conferencia_oficio=["A minuta fixa prazo sem lastro."])
        txt = _texto_do_pdf(relatorio_fid.gerar_pdf(_dados(), "habilitacao", p))
        assert "Conferência automática da minuta" in txt
        assert "A minuta fixa prazo sem lastro." in txt

    def test_sem_alertas_a_secao_nao_aparece(self):
        txt = _texto_do_pdf(relatorio_fid.gerar_pdf(_dados(), "habilitacao", _parecer()))
        assert "Conferência automática da minuta" not in txt


class TestTabelaNaoTransborda:
    """Defeito real do 1º teste: as células iam como string crua, que no
    ReportLab não quebra linha — transborda e escreve por cima da coluna
    vizinha. Saiu 'com vavleidnacdideo vigente' no PDF entregue."""

    def _parecer_com_texto_longo(self):
        return _parecer(documentos_solicitados=[{
            "documento": ("Esclarecimento sobre divergência de CNPJ entre a proposta "
                          "e a nota fiscal apresentada como atestado de capacidade técnica"),
            "situacao": "pendente",
            "fundamento_legal": "Art. 59, §2º e Art. 64, II, Lei 14.133/2021",
            "prazo_dias": None,
        }])

    def test_nenhuma_palavra_sai_embaralhada(self):
        """O defeito antigo embaralhava CARACTERES de colunas vizinhas
        ('validade' + 'vencido' = 'vavleidnacdideo'). Como a extração de PDF lê
        a tabela linha a linha, a frase não sai contígua nem quando está certa —
        então o que se verifica é que cada palavra chega inteira."""
        txt = _texto_do_pdf(relatorio_fid.gerar_pdf(
            _dados(), "habilitacao", self._parecer_com_texto_longo()))
        palavras = set(txt.split())
        for p in ("Esclarecimento", "divergência", "proposta", "fiscal",
                  "apresentada", "atestado", "capacidade", "técnica", "pendente"):
            assert p in palavras, f"palavra '{p}' saiu quebrada ou colada em outra"

    def test_fundamento_legal_nao_e_atropelado(self):
        """A coluna do fundamento também quebra em duas linhas dentro da célula;
        o que importa é que os tokens cheguem inteiros, sem letras de outra
        coluna no meio."""
        txt = _texto_do_pdf(relatorio_fid.gerar_pdf(
            _dados(), "habilitacao", self._parecer_com_texto_longo()))
        palavras = set(txt.split())
        for p in ("Art.", "59,", "§2º", "64,", "II,", "Lei", "14.133/2021"):
            assert p in palavras, p

    def test_cabecalho_da_tabela_integro(self):
        txt = _texto_do_pdf(relatorio_fid.gerar_pdf(
            _dados(), "habilitacao", self._parecer_com_texto_longo()))
        for col in ("Documento / Informação", "Situação", "Fundamento Legal", "Prazo"):
            assert col in txt, col


class TestSituacaoDeclaradaNoPDF:
    def test_pendente_declarado_explica_o_motivo(self):
        p = _parecer(documentos_solicitados=[{
            "documento": "Certidão FGTS", "situacao": "pendente",
            "_situacao_declarada": "vencido",
            "fundamento_legal": "Art. 64, I", "prazo_dias": None}])
        txt = _texto_do_pdf(relatorio_fid.gerar_pdf(_dados(), "habilitacao", p))
        assert "(declarado: vencido)" in txt
        assert "Situação registrada como pendente porque o vício indicado foi apenas" in txt
        assert "sem comprovação documental anexada" in txt

    def test_situacao_com_lastro_nao_ganha_ressalva(self):
        p = _parecer(_documentos_analisados=[{"arquivo": "fgts.pdf", "chars": 500}],
                     documentos_solicitados=[{
                         "documento": "Certidão FGTS", "situacao": "vencido",
                         "fundamento_legal": "Art. 64, I", "prazo_dias": None}])
        txt = _texto_do_pdf(relatorio_fid.gerar_pdf(_dados(), "habilitacao", p))
        assert "declarado:" not in txt
        assert "Situação registrada como pendente" not in txt


class TestRessalvaNaConclusao:
    """Defeito real do 3º teste: a tabela já saía 'pendente — declarado' e a
    conclusão, logo abaixo, afirmava os mesmos vícios como constatados
    ('vícios identificados', 'certidão vencida'). É a conclusão que a pessoa lê
    e para; o aviso em maiúsculas ficava na última página."""

    def test_sem_lastro_a_ressalva_aparece_colada_na_conclusao(self):
        p = _parecer(conclusao="A diligência é necessária em razão de vícios "
                               "identificados: certidão de FGTS vencida.")
        txt = _texto_do_pdf(relatorio_fid.gerar_pdf(_dados(), "habilitacao", p))
        assert "RESSALVA OBRIGATÓRIA À CONCLUSÃO ACIMA" in txt
        assert "declarado no formulário e não conferido" in txt
        # tem de vir DEPOIS da conclusão, não no fim do documento
        assert txt.index("vícios identificados") < txt.index("RESSALVA OBRIGATÓRIA")
        assert txt.index("RESSALVA OBRIGATÓRIA") < txt.index("Prazo de Resposta")

    def test_com_documento_anexado_nao_ha_ressalva(self):
        p = _parecer(conclusao="Vícios identificados nos documentos anexados.",
                     _documentos_analisados=[{"arquivo": "fgts.pdf", "chars": 800}])
        txt = _texto_do_pdf(relatorio_fid.gerar_pdf(_dados(), "habilitacao", p))
        assert "RESSALVA OBRIGATÓRIA" not in txt

    def test_sem_conclusao_nao_ha_ressalva_orfa(self):
        p = _parecer(conclusao="")
        txt = _texto_do_pdf(relatorio_fid.gerar_pdf(_dados(), "habilitacao", p))
        assert "RESSALVA OBRIGATÓRIA" not in txt


class TestIdentificacaoNaoVaza:
    """Terceira aparição do mesmo defeito, achada no T3a: a tabela de
    Identificação também usava string crua. Nos testes o objeto era curto
    ('Serviços de TI') e nada aparecia — mas o objeto de uma licitação real tem
    duas ou três linhas. O campo mais comprido do formulário era o menos
    testado."""

    _OBJETO = ("Registro de preços para eventual aquisição de material de expediente, "
               "papelaria, suprimentos de informática e materiais de consumo destinados "
               "às unidades administrativas e escolares do Município")
    _ORGAO = ("Prefeitura Municipal de Exemplo — Secretaria Municipal de Administração "
              "e Planejamento")

    def _pdf(self):
        d = {**_dados(), "objeto": self._OBJETO, "orgao": self._ORGAO,
             "razao_social": "Alfa Comércio de Materiais de Expediente e "
                             "Suprimentos de Informática Ltda ME"}
        return relatorio_fid.gerar_pdf(d, "habilitacao", _parecer())

    def test_objeto_longo_quebra_dentro_da_celula(self):
        import io
        import pdfplumber
        with pdfplumber.open(io.BytesIO(self._pdf())) as doc:
            pagina = doc.pages[0]
            largura = pagina.width
            # nenhuma palavra pode terminar fora da margem direita da pagina
            for w in pagina.extract_words():
                assert w["x1"] <= largura - 40, f"'{w['text']}' vaza da margem (x1={w['x1']:.0f})"

    def test_texto_do_objeto_chega_inteiro(self):
        txt = _texto_do_pdf(self._pdf())
        # a pontuacao gruda no token ("papelaria,"), entao compara-se sem ela
        palavras = {w.strip(".,;:—-") for w in txt.split()}
        for p in ("Registro", "preços", "papelaria", "suprimentos",
                  "administrativas", "escolares", "Município"):
            assert p in palavras, p
