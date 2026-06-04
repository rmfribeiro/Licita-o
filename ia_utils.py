from __future__ import annotations
import json
import re


def extrair_json(texto: str) -> dict:
    """Extrai e repara JSON da resposta bruta do LLM.

    Tenta em 3 etapas:
    1. Parse direto do bloco JSON encontrado.
    2. Remove trailing commas (vírgula antes de } ou ]).
    3. Trunca no ponto de erro (usando stack string-aware para respeitar
       strings e fechar delimitadores na ordem correta).
    """
    t = texto.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.IGNORECASE | re.MULTILINE).strip()
    ini = t.find("{")
    fim = t.rfind("}") + 1
    if ini == -1 or fim == 0:
        try:
            return json.loads(t)
        except json.JSONDecodeError:
            raise ValueError("Resposta sem JSON reconhecível")
    raw = t[ini:fim]

    # Try 1: parse direto
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Try 2: remove trailing commas
    cleaned = re.sub(r",\s*([}\]])", r"\1", raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc2:
        pass  # exc2.pos reaproveitado em Try 3

    # Try 3: trunca no ponto de erro e fecha delimitadores na ordem correta.
    # Usa stack string-aware para não contar { e [ dentro de strings.
    trunc = cleaned[:exc2.pos]
    stack: list[str] = []
    in_string = False
    escape = False
    for ch in trunc:
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in "{[":
            stack.append(ch)
        elif ch in "}]" and stack:
            stack.pop()

    if stack:
        closer = {"[": "]", "{": "}"}
        closing = "".join(closer[c] for c in reversed(stack))
        try:
            return json.loads(trunc + closing)
        except json.JSONDecodeError:
            pass

    raise ValueError("Resposta sem JSON reconhecível após tentativas de reparo")
