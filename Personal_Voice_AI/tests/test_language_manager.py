import json

import pytest

from core.language_manager import LanguageManager, UnsupportedLanguageError


def test_seventeen_documented_languages():
    lm = LanguageManager()
    assert lm.count() == 17
    assert "zh-cn" in lm.codes() and "hi" in lm.codes() and "ur" not in lm.codes()


def test_urdu_is_rejected_without_substitution():
    with pytest.raises(UnsupportedLanguageError) as err:
        LanguageManager().validate("ur")
    assert "Urdu" in str(err.value) and "substitute" in str(err.value)


def test_engine_restriction():
    with pytest.raises(UnsupportedLanguageError):
        LanguageManager().validate("fr", engine_codes=["en"])


def test_override_file(tmp_path):
    path = tmp_path / "languages.json"
    path.write_text(json.dumps([{"code": "en", "name": "English", "char_limit": 100}]))
    lm = LanguageManager(path)
    assert lm.codes() == ["en"] and lm.char_limit("en") == 100
