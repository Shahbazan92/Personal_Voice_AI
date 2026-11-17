"""The app must start (and not crash) even when the model stack / model are missing."""
import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402


def test_every_page_renders_without_exception():
    at = AppTest.from_file("app.py", default_timeout=60).run()
    assert not at.exception
    for page in ("🎤 Voice Profiles", "🗣️ Generate Speech", "📚 Audio Library", "⚙️ Settings", "ℹ️ About", "🏠 Dashboard"):
        at.radio(key="nav").set_value(page).run()
        assert not at.exception, f"{page}: {at.exception}"
