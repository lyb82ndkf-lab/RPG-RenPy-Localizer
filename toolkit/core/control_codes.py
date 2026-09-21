from __future__ import annotations

import re
from typing import Sequence

# Regex patterns for MTool, RPG Maker, and Ren'Py control tokens
MTOOL_PARAM_RE = re.compile(r"\$[0-9]+")
RPGM_VAR_RE = re.compile(r"\\[VvNnCcGgIi]\[[0-9]+\]")
RPGM_ESC_RE = re.compile(r"\\[.|\$|\\!><{}^]")
RENPY_INTERP_RE = re.compile(r"\[[a-zA-Z0-9_.]+\]")
C_FORMAT_RE = re.compile(r"%[0-9]*\$?[sdf]")
BRACKET_NUM_RE = re.compile(r"\{[0-9]+\}")


def extract_control_codes(text: str) -> list[str]:
    """Extract all control codes, escape tokens, and placeholders from a source string."""
    if not text or not isinstance(text, str):
        return []
    tokens: list[str] = []
    for pattern in (MTOOL_PARAM_RE, RPGM_VAR_RE, RPGM_ESC_RE, RENPY_INTERP_RE, C_FORMAT_RE, BRACKET_NUM_RE):
        tokens.extend(pattern.findall(text))
    return tokens


def repair_control_codes(source: str, target: str) -> str:
    """Validate and automatically repair corrupted control codes and missing placeholders in AI translations.
    
    Common LLM failure modes handled:
    1. RPG Maker \\N[x] mistakenly lowercased to \\n[x] (which causes a literal newline in some parsers).
    2. RPG Maker \\V[x], \\C[x], \\I[x] missing leading backslash or replaced with forward slash: /V[1], V[1].
    3. MTool $1, $2 placeholders missing or translated into Chinese numbers.
    4. Ren'Py [var] converted to full-width Chinese brackets 【var】.
    5. C-style format strings converted to full-width %: ％s, ％d.
    """
    if not source or not target or not isinstance(source, str) or not isinstance(target, str):
        return target

    result = target

    # 1. Fix full-width format specifiers (e.g. ％s -> %s, ％d -> %d)
    result = re.sub(r"％([0-9]*\$?[sdf])", r"%\1", result)

    # 2. Fix Ren'Py full-width brackets on variables: 【player_name】 -> [player_name]
    renpy_tokens = RENPY_INTERP_RE.findall(source)
    for token in renpy_tokens:
        inner = token[1:-1]
        chinese_bracket = f"【{inner}】"
        if chinese_bracket in result and token not in result:
            result = result.replace(chinese_bracket, token)
        # Also fix missing brackets if the exact variable name appears standalone
        elif token not in result and f" {inner} " in result:
            result = re.sub(rf"(?<!\[)\b{re.escape(inner)}\b(?!\])", token, result, count=1)

    # 3. Fix RPG Maker \V[x], \N[x], \C[x], \I[x] corruptions
    rpgm_tokens = RPGM_VAR_RE.findall(source)
    for token in rpgm_tokens:
        # Standardize token casing according to RPG Maker convention (V, N, C, G, I uppercase)
        tag = token[1].upper()
        num = re.search(r"\[([0-9]+)\]", token).group(1)
        canonical = f"\\{tag}[{num}]"

        # Case 3a: Model wrote /V[1] or \v[1]
        wrong_slash = f"/{tag}[{num}]"
        lower_token = f"\\{tag.lower()}[{num}]"
        no_slash = f"{tag}[{num}]"
        chinese_tok = f"【{tag}[{num}]】"

        if canonical not in result:
            if wrong_slash in result:
                result = result.replace(wrong_slash, canonical)
            elif lower_token in result:
                result = result.replace(lower_token, canonical)
            elif chinese_tok in result:
                result = result.replace(chinese_tok, canonical)
            elif re.search(rf"(?<!\\)\b{re.escape(no_slash)}\b", result):
                result = re.sub(rf"(?<!\\)\b{re.escape(no_slash)}\b", canonical, result, count=1)
            else:
                # If completely missing and was in source, append or align at end
                pass

    # Fix \N[x] corrupted into literal newline + [x]
    for m in re.finditer(r"\\N\[([0-9]+)\]", source, re.IGNORECASE):
        num = m.group(1)
        canonical = f"\\N[{num}]"
        if canonical not in result:
            # Check if there is \n[1] or newline followed by [1]
            if f"\\n[{num}]" in result:
                result = result.replace(f"\\n[{num}]", canonical)
            elif f"\n[{num}]" in result:
                result = result.replace(f"\n[{num}]", canonical)

    # 4. Check and restore MTool $1, $2 placeholders
    mtool_tokens = MTOOL_PARAM_RE.findall(source)
    # Filter unique while preserving order
    seen_mtool = []
    for tok in mtool_tokens:
        if tok not in seen_mtool:
            seen_mtool.append(tok)

    for tok in seen_mtool:
        if tok not in result:
            num = tok[1:]
            # Check if model translated to 1$ or ＄1 or $ 1
            if f"{num}$" in result:
                result = result.replace(f"{num}$", tok)
            elif f"＄{num}" in result:
                result = result.replace(f"＄{num}", tok)
            elif f"$ {num}" in result:
                result = result.replace(f"$ {num}", tok)
            elif f"【{num}】" in result:
                result = result.replace(f"【{num}】", tok)
            else:
                # If completely omitted by LLM, restore placeholder
                # If source ends with $1, place at end; otherwise append
                if source.strip().endswith(tok):
                    result = result.rstrip() + " " + tok
                elif source.strip().startswith(tok):
                    result = tok + " " + result.lstrip()
                else:
                    result = result + f" {tok}"

    return result
