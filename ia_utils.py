from __future__ import annotations
import json
import re
import types

COR_STATUS_HEX: types.MappingProxyType[str, str] = types.MappingProxyType({
    "ok":      "#27AE60",
    "alerta":  "#E67E22",
    "critico": "#C0392B",
})


def extrair_json(texto: str) -> dict:
    """Extrai e repara JSON da resposta bruta do LLM.

    Tenta em 3 etapas:
    1. Parse direto do bloco JSON encontrado.
    2. Remove trailing commas (vírgula antes de } ou ]).
    3. Trunca no ponto de erro (usando stack string-aware para respeitar
       strings e fechar delimitadores na ordem correta).
    """
    t = texto.strip()
    t = re.sub(r"\A```(?:json)?\s*|\s*```\Z", "", t, flags=re.IGNORECASE).strip()
    ini = t.find("{")
    if ini == -1:
        try:
            return json.loads(t)
        except json.JSONDecodeError:
            raise ValueError("Resposta sem JSON reconhecível")
    fim = t.rfind("}") + 1
    # fim==0 significa JSON truncado sem nenhum } — usa o texto inteiro para repair
    raw = t[ini:fim] if fim > 0 else t[ini:]

    # Try 1: parse direto
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Try 2: remove trailing commas
    cleaned = re.sub(r",\s*([}\]])", r"\1", raw)
    err_pos = None
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc2:
        err_pos = exc2.pos  # captura antes de PEP 3110 deletar exc2

    # Try 3: trunca no ponto de erro e fecha delimitadores na ordem correta.
    # Usa stack string-aware para não contar { e [ dentro de strings.
    trunc = cleaned[:err_pos]
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

    if stack or in_string:
        closer = {"[": "]", "{": "}"}
        closing = ('"' if in_string else "") + "".join(closer[c] for c in reversed(stack))
        try:
            return json.loads(trunc + closing)
        except json.JSONDecodeError:
            pass

    raise ValueError("Resposta sem JSON reconhecível após tentativas de reparo")
