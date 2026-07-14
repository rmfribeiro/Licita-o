#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG leve (offline) sobre a base juridica da Lei 14.133/2021.
--------------------------------------------------------------
Implementa recuperacao por TF-IDF + cosseno, em Python puro (sem dependencias),
para o piloto poder rodar sem servico externo. No piloto real, esta camada pode
ser trocada por embeddings semanticos via API mantendo a mesma interface buscar().

Uso:
    from rag import BaseRAG
    rag = BaseRAG("base_juridica.json")
    for art, score, texto in rag.buscar("garantia de execucao percentual", k=2):
        ...
"""
import json, re, math, unicodedata, os
from collections import Counter

def _norm(s):
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return s.lower()

_STOP = set("de da do das dos a o e que em para com no na nos nas ao aos por se os as um uma "
            "sera serao deste desta neste nesta entre sobre ou the".split())

def _tokens(s):
    return [t for t in re.findall(r"[a-z0-9]+", _norm(s)) if t not in _STOP and len(t) > 1]

class BaseRAG:
    def __init__(self, caminho):
        with open(caminho, encoding="utf-8") as f:
            self.base = json.load(f)
        if "artigos" not in self.base:
            raise ValueError(f"base_juridica.json invalido: chave 'artigos' ausente em {caminho}")
        self.docs = self.base["artigos"]
        self.N = len(self.docs)
        # tf por doc e df global
        self.tf, df = [], Counter()
        for i, d in enumerate(self.docs):
            if not all(k in d for k in ("art", "tema", "texto")):
                raise ValueError(f"Artigo #{i} em {caminho} sem campo obrigatorio (art/tema/texto)")
            toks = _tokens(d["tema"] + " " + d["texto"])
            c = Counter(toks)
            self.tf.append(c)
            for t in set(toks):
                df[t] += 1
        self.idf = {t: math.log((self.N + 1) / (df_t + 1)) + 1 for t, df_t in df.items()}
        self.vecs = [self._vec(c) for c in self.tf]
        self.norms = [math.sqrt(sum(v * v for v in vec.values())) or 1.0 for vec in self.vecs]

    def _vec(self, counter):
        return {t: (1 + math.log(f)) * self.idf.get(t, 0.0) for t, f in counter.items()}

    def buscar(self, consulta, k=2):
        q = self._vec(Counter(_tokens(consulta)))
        if not q:
            return []
        qn = math.sqrt(sum(v * v for v in q.values())) or 1.0
        scores = []
        for i, vec in enumerate(self.vecs):
            dot = sum(q.get(t, 0.0) * v for t, v in vec.items())
            scores.append((dot / (qn * self.norms[i]), i))
        scores.sort(reverse=True)
        out = []
        for sc, i in scores[:k]:
            d = self.docs[i]
            out.append((d["art"], round(sc, 3), d["texto"]))
        return out

if __name__ == "__main__":
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "base_juridica.json")
    rag = BaseRAG(base)
    for consulta in ["prazo minimo de divulgacao do edital de pregao",
                     "garantia de execucao acima de cinco por cento",
                     "impugnacao do edital prazo",
                     "indicacao de marca direcionamento"]:
        print(f"\nCONSULTA: {consulta}")
        for art, sc, txt in rag.buscar(consulta, k=2):
            print(f"  -> Art. {art} (score {sc}): {txt[:90]}...")
