from __future__ import annotations

import re
from collections.abc import Iterable

from .models import TranslationEntry


def _normalise_source(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def nearby_translation_sources(
    entries: list[TranslationEntry],
    anchor_source: str,
    translations: dict[str, str],
    window_size: int,
    budget_by_category: Iterable[str],
) -> list[str]:
    """Return untranslated entries following an anchor in the same extracted file."""
    anchor = _normalise_source(anchor_source)
    if not anchor or not entries:
        return []
    anchor_index = next(
        (index for index, entry in enumerate(entries) if _normalise_source(entry.source) == anchor),
        -1,
    )
    if anchor_index < 0:
        return []
    limit = max(1, min(int(window_size), 1000))
    categories = set(budget_by_category)
    anchor_file = str(entries[anchor_index].file or "")
    translated = {_normalise_source(source) for source, target in translations.items() if str(target or "").strip()}
    translated.update(
        _normalise_source(entry.source)
        for entry in entries
        if str(entry.target or "").strip()
    )
    result: list[str] = []
    seen = {anchor}
    for entry in entries[anchor_index + 1 :]:
        file_name = str(entry.file or "")
        if anchor_file and file_name and file_name != anchor_file:
            break
        source = str(entry.source or "").strip()
        normalized = _normalise_source(source)
        if (
            not normalized
            or normalized in seen
            or normalized in translated
            or str(entry.category or "") not in categories
        ):
            continue
        result.append(source)
        seen.add(normalized)
        if len(result) >= limit:
            break
    return result
