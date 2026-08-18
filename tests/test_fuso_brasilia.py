# -*- coding: utf-8 -*-
"""Fuso horario dos relatorios e dos calculos de data.

DEFEITO REAL (18/08/2026): os relatorios carimbavam `datetime.now()` sem fuso.
O Streamlit Cloud roda em UTC e o usuario esta em Aracaju (UTC-3), entao todo
relatorio gerado entre 21h e meia-noite saia datado do DIA SEGUINTE. Dois
testes reais do FID, rodados as 23:11 e 23:13 de 17/08, sairam carimbados
"18/08/2026 as 02:11 / 02:13".

Num documento que entra em processo administrativo isso nao e cosmetico. E o
mesmo `date.today()` alimentava o prazo do art. 163 e o fechamento do mes de
cobranca — onde um dia de erro muda conclusao e dinheiro.
"""
from __future__ import annotations
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import ia_utils


class TestHelpers:
    def test_agora_traz_fuso(self):
        assert ia_utils.agora_brasilia().tzinfo is not None

    def test_offset_e_menos_tres_horas(self):
        assert ia_utils.agora_brasilia().utcoffset() == timedelta(hours=-3)

    def test_carimbo_diz_qual_e_o_fuso(self):
        """O relatorio pode ser lido meses depois por um controlador."""
        c = ia_utils.carimbo_brasilia()
        assert "horário de Brasília" in c
        assert c.startswith("Gerado em: ")

    def test_carimbo_no_formato_brasileiro(self):
        import re
        assert re.search(r"\d{2}/\d{2}/\d{4} às \d{2}:\d{2}", ia_utils.carimbo_brasilia())


class TestViradaDoDia:
    """O caso que produziu o defeito: 23h em Brasilia ja e o dia seguinte em UTC."""

    UTC_DEPOIS_DA_MEIA_NOITE = datetime(2026, 8, 18, 2, 11, tzinfo=timezone.utc)

    def test_hoje_brasilia_nao_avanca_o_dia(self):
        with patch("ia_utils._datetime") as m:
            m.now.side_effect = lambda tz=None: self.UTC_DEPOIS_DA_MEIA_NOITE.astimezone(tz)
            assert ia_utils.hoje_brasilia() == date(2026, 8, 17)

    def test_carimbo_usa_o_dia_certo(self):
        with patch("ia_utils._datetime") as m:
            m.now.side_effect = lambda tz=None: self.UTC_DEPOIS_DA_MEIA_NOITE.astimezone(tz)
            c = ia_utils.carimbo_brasilia()
        assert "17/08/2026 às 23:11" in c, c
        assert "18/08" not in c


class TestMesDeCobranca:
    """Fatura fechada em fuso de servidor diverge do que o cliente viu na tela."""

    def test_janela_do_mes_comeca_a_meia_noite_de_brasilia(self):
        import uso_db
        ini, fim = uso_db._limites_mes(2026, 8)
        # 1o de agosto 00:00 em Brasilia = 03:00 UTC do mesmo dia
        assert datetime.fromisoformat(ini) == datetime(2026, 8, 1, 3, 0, tzinfo=timezone.utc)
        assert datetime.fromisoformat(fim) == datetime(2026, 9, 1, 3, 0, tzinfo=timezone.utc)

    def test_relatorio_das_22h_do_dia_31_conta_no_mes_certo(self):
        """Era este o erro: 22h de 31/08 em Brasilia = 01h de 01/09 em UTC,
        e o uso caia na fatura do mes seguinte."""
        import uso_db
        ini, fim = uso_db._limites_mes(2026, 8)
        gerado = datetime(2026, 9, 1, 1, 0, tzinfo=timezone.utc)   # 22h de 31/08 BRT
        assert datetime.fromisoformat(ini) <= gerado < datetime.fromisoformat(fim)

    def test_dezembro_vira_para_janeiro_do_ano_seguinte(self):
        import uso_db
        _ini, fim = uso_db._limites_mes(2026, 12)
        assert datetime.fromisoformat(fim) == datetime(2027, 1, 1, 3, 0, tzinfo=timezone.utc)


class TestNenhumRelatorioUsaORelogioDoServidor:
    """Trava de regressao: o proximo relatorio criado nao pode reintroduzir o
    `datetime.now()` sem fuso."""

    def test_nenhum_modulo_de_producao_chama_now_sem_fuso(self):
        import pathlib
        import re
        raiz = pathlib.Path(__file__).resolve().parent.parent
        padrao = re.compile(r"(?<!ia_utils\.)\b(?:datetime\.)?datetime\.now\(\s*\)"
                            r"|(?<!ia_utils\.)\bdate\.today\(\s*\)")
        culpados = []
        for py in sorted(raiz.glob("*.py")):
            if py.name == "ia_utils.py":       # e la que o fuso e resolvido
                continue
            for n, linha in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
                if padrao.search(linha) and "tzinfo" not in linha:
                    culpados.append(f"{py.name}:{n}: {linha.strip()}")
        assert not culpados, "usar ia_utils.agora_brasilia()/hoje_brasilia():\n" + "\n".join(culpados)
