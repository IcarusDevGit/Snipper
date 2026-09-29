import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from config import SnipperConfig
from document import Question
from nlp import LexicalMatcher, detect_language


class MockParagraph:
    def __init__(self, text: str):
        self.text = text


def test_language_detection():
    en_text = "What is the capital of France and who founded ACME Corp?"
    pt_text = "Qual é a capital da França e quem fundou a empresa com patente?"
    assert detect_language(en_text) == "en"
    assert detect_language(pt_text) == "pt-BR"


def test_english_lemma_matching():
    cfg = SnipperConfig(language="en", palette=["#FFFF00", "#00FFFF"])
    matcher = LexicalMatcher(cfg)
    matcher.initialize_language("sample text")

    q1 = Question(id=1, text="What patents did the investors file in Boston?", paragraph_idx=1, color="#FFFF00")
    questions = [q1]
    q_map = {1: q1}

    lemmas = matcher.extract_question_lemmas(questions)
    # Check that nouns/proper nouns are extracted and lemmatized
    assert "patent" in lemmas
    assert "investor" in lemmas
    assert "boston" in lemmas
    # Check verbs and prepositions are excluded
    assert "file" not in lemmas
    assert "in" not in lemmas
    assert "what" not in lemmas

    # Body contains plural and singular
    body = [
        (10, MockParagraph("The firm filed a major patent in Boston yesterday.")),
        (11, MockParagraph("All investors reviewed the document.")),
    ]

    matches = matcher.scan_body(body, lemmas, q_map)
    assert len(matches) >= 3

    matched_texts = [m.text for m in matches]
    assert "patent" in matched_texts
    assert "Boston" in matched_texts
    assert "investors" in matched_texts


def test_portuguese_lemma_matching():
    cfg = SnipperConfig(language="pt-BR", palette=["#FFFF00"])
    matcher = LexicalMatcher(cfg)
    matcher.initialize_language("texto de exemplo")

    q1 = Question(id=1, text="Quantas patentes os investidores registraram em São Paulo?", paragraph_idx=1, color="#FFFF00")
    questions = [q1]
    q_map = {1: q1}

    lemmas = matcher.extract_question_lemmas(questions)
    assert "patente" in lemmas
    assert "investidor" in lemmas

    body = [
        (10, MockParagraph("A empresa registrou uma patente importante.")),
        (11, MockParagraph("Os investidores aprovaram o projeto.")),
    ]

    matches = matcher.scan_body(body, lemmas, q_map)
    assert len(matches) >= 2
    matched_texts = [m.text for m in matches]
    assert "patente" in matched_texts
    assert "investidores" in matched_texts


if __name__ == "__main__":
    test_language_detection()
    test_english_lemma_matching()
    test_portuguese_lemma_matching()
    print("NLP lemmatizer tests passed!")
