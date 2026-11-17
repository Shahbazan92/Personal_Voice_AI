"""Supported-language registry.

The defaults are the 17 languages documented for Coqui XTTS-v2. The list is
configurable: drop a ``languages.json`` file into the data directory with a list
of ``{"code": ..., "name": ..., "char_limit": ...}`` objects to override it.

Urdu is deliberately NOT in the defaults: it is not an officially documented
XTTS-v2 language, and this app never substitutes Hindi or Arabic silently.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import config


class UnsupportedLanguageError(ValueError):
    """Raised when a language code is not supported. Message is user-safe."""


@dataclass(frozen=True)
class Language:
    code: str
    name: str
    char_limit: int  # soft per-chunk limit recommended by the XTTS tokenizer


DEFAULT_LANGUAGES: tuple[Language, ...] = (
    Language("en", "English", 250),
    Language("es", "Spanish", 239),
    Language("fr", "French", 273),
    Language("de", "German", 253),
    Language("it", "Italian", 213),
    Language("pt", "Portuguese", 203),
    Language("pl", "Polish", 224),
    Language("tr", "Turkish", 226),
    Language("ru", "Russian", 182),
    Language("nl", "Dutch", 251),
    Language("cs", "Czech", 186),
    Language("ar", "Arabic", 166),
    Language("zh-cn", "Chinese (Simplified)", 82),
    Language("ja", "Japanese", 71),
    Language("hu", "Hungarian", 224),
    Language("ko", "Korean", 95),
    Language("hi", "Hindi", 150),
)

# Languages users commonly ask for that XTTS-v2 does not document.
KNOWN_UNSUPPORTED = {
    "ur": "Urdu",
    "bn": "Bengali",
    "fa": "Persian",
    "pa": "Punjabi",
    "ta": "Tamil",
    "id": "Indonesian",
    "vi": "Vietnamese",
    "th": "Thai",
}


class LanguageManager:
    def __init__(self, override_path: Path | None = None) -> None:
        self._languages = self._load(override_path or config.LANGUAGES_OVERRIDE_PATH)
        self._by_code = {lang.code: lang for lang in self._languages}

    @staticmethod
    def _load(path: Path) -> tuple[Language, ...]:
        if path and Path(path).is_file():
            try:
                raw = json.loads(Path(path).read_text(encoding="utf-8"))
                langs = tuple(
                    Language(str(i["code"]), str(i["name"]), int(i.get("char_limit", 200)))
                    for i in raw
                )
                if langs:
                    return langs
            except (OSError, ValueError, KeyError, TypeError) as exc:
                raise ValueError(f"Invalid languages override file {path}: {exc}") from exc
        return DEFAULT_LANGUAGES

    # ------------------------------------------------------------------ queries
    def all(self) -> list[Language]:
        return list(self._languages)

    def codes(self) -> list[str]:
        return [lang.code for lang in self._languages]

    def count(self) -> int:
        return len(self._languages)

    def get(self, code: str) -> Language:
        self.validate(code)
        return self._by_code[code]

    def name_for(self, code: str) -> str:
        lang = self._by_code.get(code)
        return lang.name if lang else code

    def char_limit(self, code: str) -> int:
        return self.get(code).char_limit

    def for_codes(self, codes: list[str]) -> list[Language]:
        """Languages from this registry that are also in ``codes`` (engine support)."""
        allowed = set(codes)
        return [lang for lang in self._languages if lang.code in allowed]

    def validate(self, code: str, engine_codes: list[str] | None = None) -> str:
        """Return ``code`` if supported, otherwise raise ``UnsupportedLanguageError``."""
        key = (code or "").strip()
        base = key.split("-")[0].lower()
        if key not in self._by_code:
            if base in KNOWN_UNSUPPORTED:
                raise UnsupportedLanguageError(
                    f"{KNOWN_UNSUPPORTED[base]} ('{base}') is not an officially supported "
                    "XTTS-v2 language. This app will not substitute Hindi, Arabic or any "
                    "other language automatically. Pick one of the supported languages."
                )
            raise UnsupportedLanguageError(
                f"Language code '{key}' is not supported. Supported: {', '.join(self.codes())}."
            )
        if engine_codes is not None and key not in engine_codes:
            raise UnsupportedLanguageError(
                f"The selected engine does not support {self._by_code[key].name} ('{key}')."
            )
        return key
