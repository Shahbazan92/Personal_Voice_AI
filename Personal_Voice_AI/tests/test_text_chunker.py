from core.text_chunker import chunk_text, split_sentences


def test_short_text_single_chunk():
    assert chunk_text("Hello, how are you today?", 200) == ["Hello, how are you today?"]


def test_chunks_respect_limit_and_keep_all_words():
    text = " ".join(f"Sentence number {i} is here." for i in range(40))
    chunks = chunk_text(text, 100)
    assert all(len(c) <= 100 for c in chunks) and len(chunks) > 1
    assert " ".join(chunks).split() == text.split()


def test_decimal_numbers_not_split():
    assert split_sentences("Pi is 3.14 roughly. Next one.") == ["Pi is 3.14 roughly.", "Next one."]


def test_very_long_sentence_is_hard_split():
    chunks = chunk_text("word " * 200, 80)
    assert all(len(c) <= 80 for c in chunks)


def test_cjk_sentences():
    chunks = chunk_text("你好。今天天气很好。我们去公园吧。", 8)
    assert all(len(c) <= 8 for c in chunks) and "".join(chunks) == "你好。今天天气很好。我们去公园吧。"
