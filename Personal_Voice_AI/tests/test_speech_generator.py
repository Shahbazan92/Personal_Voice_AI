import pytest

from core.engines.base import SynthesisSettings
from core.language_manager import LanguageManager, UnsupportedLanguageError
from core.speech_generator import SpeechGenerator
from utils.validators import ValidationError


@pytest.fixture
def generator(db, storage, profiles):
    return SpeechGenerator(db, storage, LanguageManager(), profiles)


def test_generation_saves_file_and_history(generator, profiles, speech_wav, fake_engine, storage, db):
    pid, _ = profiles.create("Voice", "v.wav", speech_wav, True)
    result = generator.generate(engine=fake_engine, profile_id=pid, text="Hola, ¿cómo estás?", language="es",
                                settings=SynthesisSettings(), output_format="wav")
    assert storage.exists(result.key) and result.duration_sec > 0
    assert db.get_generation(result.generation_id)["language"] == "es"
    assert fake_engine.calls[0][2] == "es"


def test_unsupported_language_and_empty_text(generator, profiles, speech_wav, fake_engine):
    pid, _ = profiles.create("Voice", "v.wav", speech_wav, True)
    with pytest.raises(UnsupportedLanguageError):
        generator.generate(engine=fake_engine, profile_id=pid, text="x", language="ur", settings=SynthesisSettings())
    with pytest.raises(UnsupportedLanguageError):
        generator.generate(engine=fake_engine, profile_id=pid, text="x", language="fr", settings=SynthesisSettings())
    with pytest.raises(ValidationError):
        generator.generate(engine=fake_engine, profile_id=pid, text="  ", language="en", settings=SynthesisSettings())


def test_long_text_is_chunked(generator, profiles, speech_wav, fake_engine):
    pid, _ = profiles.create("Voice", "v.wav", speech_wav, True)
    generator.generate(engine=fake_engine, profile_id=pid, text="This is a sentence. " * 60, language="en",
                       settings=SynthesisSettings())
    assert len(fake_engine.calls[0][0]) > 1


def test_delete_generation_removes_file(generator, profiles, speech_wav, fake_engine, storage):
    pid, _ = profiles.create("Voice", "v.wav", speech_wav, True)
    res = generator.generate(engine=fake_engine, profile_id=pid, text="Hello", language="en", settings=SynthesisSettings())
    assert generator.delete_generation(res.generation_id)
    assert not storage.exists(res.key)
