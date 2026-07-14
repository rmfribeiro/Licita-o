#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
 TESTE DE INTEGRACAO  -  pncp_busca.py + ia_pesquisa_mercado.py
 RM IA-Licita / RM Vertice Digital
=============================================================================
 Objetivo: confirmar, no SEU Mac, que o modulo pncp_busca.py funciona de
 verdade - buscando no PNCP real E reaproveitando o seu ia_pesquisa_mercado.

 COMO RODAR:
   1. Coloque este arquivo (teste_integracao_pncp.py) e o pncp_busca.py
      na MESMA pasta do seu projeto (onde estao app.py e ia_pesquisa_mercado.py).
   2. No Terminal, va ate essa pasta e rode:
        python3 teste_integracao_pncp.py
   3. Ele pergunta o termo. Digite (ex: notebook) e aguarde.

 Ao final, copie TODA a saida e cole para o Claude.
=============================================================================
"""
import sys

print("=" * 70)
print("  TESTE DE INTEGRACAO - pncp_busca + ia_pesquisa_mercado")
print("=" * 70)

# 1. Verificar que os modulos do projeto estao acessiveis
try:
    import ia_pesquisa_mercado
    print("  [OK] ia_pesquisa_mercado importado")
except Exception as e:
    print(f"  [ERRO] nao achei ia_pesquisa_mercado.py: {e}")
    print("  >>> Coloque este teste na MESMA pasta do seu projeto.")
    sys.exit(1)

try:
    import pncp_busca
    print("  [OK] pncp_busca importado")
except Exception as e:
    print(f"  [ERRO] nao achei pncp_busca.py: {e}")
    print("  >>> Coloque o pncp_busca.py na mesma pasta.")
    sys.exit(1)

print()
termo = input(">>> Termo a pesquisar (ex: notebook): ").strip() or "notebook"
print(f"\n==> Buscando '{termo}' no PNCP real... (1-3 min)\n")

def progresso(i, total, texto):
    print(f"    [{i}/{total}] {texto}...")

try:
    r = pncp_busca.buscar_precos_pncp(
        termo, unidade="un", quantidade_estimada=10, progresso=progresso
    )
except Exception as e:
    print(f"\n  [ERRO] durante a busca: {type(e).__name__}: {e}")
    import traceback; traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 70)
print("  RESULTADO")
print("=" * 70)
print(f"  Status geral: {r['status_geral']}")
print(f"  Fonte: {r['fonte']}")
print(f"  Diagnostico: {r['diagnostico']}")
print(f"  Orgaos de referencia: {len(r['fornecedores'])}")

item = r["itens_avaliados"][0] if r["itens_avaliados"] else None
if item:
    ref = item["preco_referencia"]
    print(f"\n  PRECO DE REFERENCIA (mediana): "
          f"{'R$ %.2f' % ref if ref is not None else 'INSUFICIENTE'}")
    print(f"  Cotacoes validas: {len(item['cotacoes_validas'])}")
    print(f"  Cotacoes excluidas: {len(item['cotacoes_excluidas'])}")
    if item["subtotal_estimado"]:
        print(f"  Subtotal (x10 un): R$ {item['subtotal_estimado']:.2f}")

print(f"\n  PARECER:\n  {r['parecer_narrativo']}")

# Verificar compatibilidade com os geradores de PDF
print("\n  --- Verificacao de compatibilidade ---")
esperadas = {"item_id","descricao","unidade","quantidade_estimada",
             "cotacoes_detalhadas","preco_referencia","cotacoes_validas",
             "cotacoes_excluidas","status","subtotal_estimado"}
if item:
    faltando = esperadas - set(item.keys())
    if not faltando:
        print("  [OK] item_avaliado tem todas as chaves p/ gerar os PDFs")
    else:
        print(f"  [ATENCAO] faltam chaves: {faltando}")

# Tentar gerar os PDFs de verdade (se os modulos estiverem acessiveis)
try:
    import relatorio_pesquisa_mercado
    pdf = relatorio_pesquisa_mercado.gerar_relatorio_pesquisa(
        f"Pesquisa de precos: {termo}",
        r["itens_avaliados"], r["fornecedores"],
        r["parecer_narrativo"], r["status_geral"], r["valor_total_estimado"],
    )
    with open(f"teste_relatorio_{termo}.pdf", "wb") as f:
        f.write(pdf)
    print(f"  [OK] PDF gerado: teste_relatorio_{termo}.pdf ({len(pdf)} bytes)")
    print("  >>> Abra esse PDF para ver o relatorio real!")
except Exception as e:
    print(f"  [info] nao gerou PDF automaticamente ({type(e).__name__}). "
          f"Sem problema, o importante e a estrutura acima.")

print("\n" + "=" * 70)
print("  FIM - copie TODA esta saida e cole para o Claude.")
print("=" * 70)
