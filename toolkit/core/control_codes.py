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
                # If completely missing and was in source, restore based on position
                if source.strip().startswith(canonical):
                    result = canonical + result
                elif source.strip().endswith(canonical):
                    result = result + canonical
                else:
                    result = result + f" {canonical}"

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

    # 4. Check and restore RPG Maker leading and trailing escape codes
    # Capture escape sequences like \C[1], \N[2], \., \!, \|, \^, \{, \}, \>, \<
    rpgm_pattern = re.compile(r"\\(?:[A-Za-z]+\[[^\]]*\]|[A-Za-z]+|[.|\$!><{}^])")
    source_tokens = rpgm_pattern.findall(source)
    if source_tokens:
        # Check leading sequence in source
        leading_tokens: list[str] = []
        pos = 0
        s_stripped = source.lstrip()
        while pos < len(s_stripped):
            m = rpgm_pattern.match(s_stripped, pos)
            if m:
                leading_tokens.append(m.group(0))
                pos = m.end()
            elif s_stripped[pos] in " \t:：":
                pos += 1
            else:
                break
        
        # If result lacks these leading tokens, prefix them
        for tok in leading_tokens:
            if tok not in result:
                result = tok + result

        # Check trailing sequence in source
        trailing_tokens: list[str] = []
        s_rev = source.rstrip()
        all_matches = list(rpgm_pattern.finditer(s_rev))
        if all_matches and all_matches[-1].end() == len(s_rev):
            for match in reversed(all_matches):
                if match.end() == len(s_rev):
                    trailing_tokens.insert(0, match.group(0))
                    s_rev = s_rev[:match.start()].rstrip()
                else:
                    break
        for tok in trailing_tokens:
            if tok not in result:
                result = result + tok

    # 5. Check and restore MTool $1, $2 placeholders
    mtool_tokens = MTOOL_PARAM_RE.findall(source)
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


# Control code prefix & suffix pattern for peeling
# Note: Never include Japanese quotes 「」 or 『』!
CONTROL_PREFIX_RE = re.compile(
    r"^(?:(?:\\|\x1b)[A-Za-z]+<[^>]*>|(?:\\|\x1b)[A-Za-z]+\[[^\]]*\]|(?:\\|\x1b)(?:fb|fi|FB|FI)|(?:\\|\x1b)[><.!|^$\\]|【[^】]+】|\[[^\]]+\]|[\s\u3000]+)+"
)
CONTROL_SUFFIX_RE = re.compile(
    r"(?:(?:\\|\x1b)[A-Za-z]+\[[^\]]*\]|(?:\\|\x1b)(?:fb|fi|FB|FI)|(?:\\|\x1b)[><.!|^$\\]|[\s\u3000]+)+$"
)
SPEAKER_BOX_RE = re.compile(r"(\\+|\x1b+)[Nn]<([^>]+)>")


def build_expanded_translation_index(raw_mapping: dict[str, str]) -> tuple[dict[str, str], dict[str, str]]:
    """Build an expanded lookup index from a raw translation mapping.

    1. Preserves all original key-value pairs.
    2. Expands multiline entries line-by-line when source and target have matching line counts.
    3. Returns (exact_map, stripped_map).
    """
    exact_map: dict[str, str] = dict(raw_mapping)
    for k, v in raw_mapping.items():
        if "\n" in k and isinstance(v, str) and "\n" in v:
            k_lines = k.split("\n")
            v_lines = v.split("\n")
            if len(k_lines) == len(v_lines):
                for kl, vl in zip(k_lines, v_lines):
                    kl_s = kl.strip()
                    vl_s = vl.strip()
                    if kl_s and vl_s:
                        if kl not in exact_map:
                            exact_map[kl] = vl
                        if kl_s not in exact_map:
                            exact_map[kl_s] = vl
    stripped_map = {k.strip(): v for k, v in exact_map.items() if k.strip()}
    return exact_map, stripped_map


def match_source_translation(
    source: str,
    exact_map: dict[str, str],
    stripped_map: dict[str, str],
) -> str | None:
    """Find the best translation for a source string using multi-stage matching:
    1. Exact match
    2. Stripped match
    3. De-escaped match (\\x1b -> \\)
    4. Control code & speaker tag prefix/suffix peeling (reconstructing with translated speaker & core)
    5. Multiline recursive match
    """
    if not source or not str(source).strip():
        return None
    source = str(source)

    # 1. Exact
    t = exact_map.get(source)
    if t:
        return t

    # 2. Stripped
    s_s = source.strip()
    t = stripped_map.get(s_s)
    if t:
        return t

    # 3. De-escaped
    de = source.replace("\x1b", "\\")
    if de != source:
        t = exact_map.get(de) or stripped_map.get(de.strip())
        if t:
            return t

    # 4. Control code prefix/suffix peeling
    m_pre = CONTROL_PREFIX_RE.match(source)
    prefix = m_pre.group(0) if m_pre else ""
    rem = source[len(prefix):]
    m_suf = CONTROL_SUFFIX_RE.search(rem)
    suffix = m_suf.group(0) if m_suf else ""
    core = rem[:len(rem) - len(suffix)] if suffix else rem

    if core.strip():
        core_t = exact_map.get(core) or stripped_map.get(core.strip())
        if not core_t and "\x1b" in core:
            cde = core.replace("\x1b", "\\")
            core_t = exact_map.get(cde) or stripped_map.get(cde.strip())
        if core_t:
            def rep_spk(m: re.Match) -> str:
                sl = m.group(1)
                nm = m.group(2)
                t_nm = exact_map.get(nm) or stripped_map.get(nm.strip()) or nm
                return f"{sl}N<{t_nm}>"

            tp = SPEAKER_BOX_RE.sub(rep_spk, prefix)
            tp = re.sub(
                r"【([^】]+)】",
                lambda m: f"【{exact_map.get(m.group(1)) or stripped_map.get(m.group(1).strip()) or m.group(1)}】",
                tp,
            )
            return f"{tp}{core_t}{suffix}"

    # 5. Multiline handling
    if "\n" in source:
        lines = source.split("\n")
        any_c = False
        res = []
        for l in lines:
            tl = match_source_translation(l, exact_map, stripped_map)
            if tl and tl != l:
                any_c = True
                res.append(tl)
            else:
                res.append(l)
        if any_c:
            return "\n".join(res)

    return None
