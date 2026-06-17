from __future__ import annotations
import json
import logging as _logging
import re
import types
import urllib.error
import urllib.request

COR_STATUS_HEX: types.MappingProxyType[str, str] = types.MappingProxyType({
    "ok":      "#27AE60",
    "alerta":  "#E67E22",
    "critico": "#C0392B",
})

COR_ADEQUACAO_HEX: types.MappingProxyType[str, str] = types.MappingProxyType({
    "ADEQUADO":               COR_STATUS_HEX["ok"],
    "ADEQUADO COM RESSALVAS": "#F39C12",
    "INADEQUADO":             COR_STATUS_HEX["critico"],
})


def as_list(v) -> list:
    return v if isinstance(v, list) else []


def safe_float(v) -> float:
    if v is None:
        return 0.0
    try:
        return float(v)
    except (ValueError, TypeError):
        return 0.0


def optional_float(v) -> float | None:
    return None if v is None else safe_float(v)


def fmt_brl_opcional(v, default: str = "-") -> str:
    if v is None:
        return default
    try:
        return fmt_brl(float(v))
    except (ValueError, TypeError):
        return default


def fmt_brl(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def chamar_anthropic(
    prompt: str,
    api_key: str,
    modelo: str,
    sistema: str,
    *,
    max_tokens: int = 4000,
) -> str:
    corpo = json.dumps({
        "model": modelo,
        "max_tokens": max_tokens,
        "system": sistema,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=corpo,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        raw_bytes = resp.read()
    try:
        dados = json.loads(raw_bytes.decode("utf-8"))
    except ValueError as exc:
        raise RuntimeError(f"Resposta da API não é JSON válido: {exc}") from exc
    return "".join(b.get("text", "") for b in (dados.get("content") or []) if isinstance(b, dict))


def chamar_api(prompt: str, api_key: str, modelo: str, sistema: str, *, max_tokens: int = 4000) -> dict:
    try:
        bruto = chamar_anthropic(prompt, api_key, modelo, sistema, max_tokens=max_tokens)
    except RuntimeError:
        raise
    except urllib.error.HTTPError as exc:
        _body = ""
        try:
            _body = exc.read().decode("utf-8", errors="replace")
        except (OSError, IOError):
            pass
        raise RuntimeError(
            f"Falha na API Anthropic: HTTP {exc.code} {exc.reason} — {_body}"
        ) from exc
    except (urllib.error.URLError, OSError) as exc:
        raise RuntimeError(f"Falha na API Anthropic: {exc}") from exc

    try:
        resultado = extrair_json(bruto)
    except ValueError as exc:
        raise RuntimeError(f"Resposta da API não contém JSON válido: {exc}") from exc

    if not isinstance(resultado, dict):
        raise RuntimeError(
            f"Resposta inesperada da API: objeto JSON esperado, "
            f"recebeu {type(resultado).__name__}"
        )
    return resultado


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
    # Só tenta se err_pos > 2 — posições menores não têm conteúdo recuperável
    # (e.g. err_pos=1 produziria '{}' vazio silenciosamente para '{bad json}').
    if err_pos is None or err_pos <= 2:
        raise ValueError("Resposta sem JSON reconhecível após tentativas de reparo")

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
            _repaired = json.loads(trunc + closing)
            # Rejeita resultado vazio ou não-dict — conteúdo recuperável produz sempre um dict com chaves
            if not isinstance(_repaired, dict) or not _repaired:
                raise ValueError("Resposta sem JSON reconhecível após tentativas de reparo")
            return _repaired
        except json.JSONDecodeError:
            pass

    raise ValueError("Resposta sem JSON reconhecível após tentativas de reparo")


_ADEQ_VALIDOS: frozenset[str] = frozenset({"ADEQUADO", "ADEQUADO COM RESSALVAS", "INADEQUADO"})
_AVISO_CAMPO_VAZIO = "campo em branco"


def normalizar_adequacao(parecer: dict, modulo: str) -> None:
    """Pop stale advisory key, normalize adequacao_geral, set advisory when value is unrecognized."""
    parecer.pop("_aviso_adequacao", None)
    _raw = parecer.get("adequacao_geral")
    _adeq = "INADEQUADO" if _raw is None else str(_raw).strip().upper()
    if _adeq not in _ADEQ_VALIDOS:
        _logging.warning(
            "%s: adequacao_geral inesperada %r — normalizado para INADEQUADO", modulo, _raw
        )
        parecer["_aviso_adequacao"] = _raw
        _adeq = "INADEQUADO"
    parecer["adequacao_geral"] = _adeq


def aviso_adequacao_story(parecer: dict, estilo) -> list:
    """Return ReportLab story elements for the _aviso_adequacao advisory, or []."""
    val = parecer.get("_aviso_adequacao")
    if val is None:
        return []
    if estilo is None:
        raise TypeError("aviso_adequacao_story: estilo não pode ser None")
    import html as _html
    from reportlab.platypus import Paragraph, Spacer
    from reportlab.lib.units import cm
    _label = f"'{_html.escape(str(val))}'" if val else _AVISO_CAMPO_VAZIO
    return [
        Paragraph(
            f"⚠ Valor de adequacao_geral não reconhecido: {_label}"
            " — registrado como INADEQUADO. Verifique manualmente.",
            estilo,
        ),
        Spacer(1, 0.2 * cm),
    ]
