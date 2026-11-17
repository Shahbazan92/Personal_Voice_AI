"""Sentence-aware text chunking.

XTTS-v2 degrades on long inputs, so text is split into chunks. To protect voice
consistency, chunks are packed as large as the per-language limit allows (fewer
joins) and every chunk is synthesised from the SAME cached speaker latents.
"""
from __future__ import annotations

import re

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…؟।])\s+|(?<=[。！？])\s*")
_SOFT_BREAKS = ",;:،、，；： "
_CJK = re.compile(r"[\u3000-\u9fff\uff00-\uffef]")


def split_sentences(text: str) -> list[str]:
    flat = re.sub(r"\s+", " ", text).strip()
    return [s.strip() for s in _SENTENCE_SPLIT.split(flat) if s and s.strip()]


def _hard_split(sentence: str, limit: int) -> list[str]:
    pieces: list[str] = []
    rest = sentence
    while len(rest) > limit:
        cut = max((rest.rfind(ch, 0, limit) for ch in _SOFT_BREAKS), default=-1)
        if cut < limit // 3:  # no sensible break point: cut hard
            cut = limit
        else:
            cut += 1
        pieces.append(rest[:cut].strip())
        rest = rest[cut:].strip()
    if rest:
        pieces.append(rest)
    return [p for p in pieces if p]


def _join(a: str, b: str) -> str:
    if _CJK.match(b[:1]) or _CJK.match(a[-1:]):
        return a + b
    return f"{a} {b}"


def chunk_text(text: str, max_chars: int) -> list[str]:
    """Split ``text`` into chunks of at most ``max_chars`` characters."""
    if max_chars < 5:
        raise ValueError("max_chars must be at least 5")
    chunks: list[str] = []
    current = ""
    for sentence in split_sentences(text):
        if len(sentence) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_hard_split(sentence, max_chars))
            continue
        if not current:
            current = sentence
        elif len(current) + 1 + len(sentence) <= max_chars:
            current = _join(current, sentence)
        else:
            chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    return chunks
