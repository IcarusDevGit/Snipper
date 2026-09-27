"""Multilingual NLP lemmatization and lexical matching using spaCy."""

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional, Set, Tuple
import spacy
from spacy.language import Language

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from config import SnipperConfig
from document import Question


# Common stop words/markers for language heuristic
PT_MARKERS = {"que", "para", "com", "não", "em", "um", "uma", "onde", "quando", "qual", "como", "quem", "por", "sobre"}
EN_MARKERS = {"the", "and", "is", "where", "what", "who", "when", "which", "how", "with", "from", "about"}

MODELS = {
    "en": "en_core_web_sm",
    "pt-BR": "pt_core_news_sm",
    "pt": "pt_core_news_sm",
}

_MODEL_CACHE: Dict[str, Language] = {}


def detect_language(text: str) -> str:
    """Heuristic language detection between Brazilian Portuguese and English."""
    words = set(re.findall(r"\b\w+\b", text.lower()))
    pt_score = len(words & PT_MARKERS)
    en_score = len(words & EN_MARKERS)
    return "pt-BR" if pt_score > en_score else "en"


def load_spacy_model(lang: str) -> Language:
    """Loads a spaCy model, downloading it if not present."""
    model_name = MODELS.get(lang, "en_core_web_sm")
    if model_name in _MODEL_CACHE:
        return _MODEL_CACHE[model_name]

    try:
        nlp = spacy.load(model_name)
    except OSError:
        subprocess.run([sys.executable, "-m", "spacy", "download", model_name], check=True)
        nlp = spacy.load(model_name)

    _MODEL_CACHE[model_name] = nlp
    return nlp


@dataclass
class LemmaMatch:
    paragraph_idx: int
    start_char: int
    end_char: int
    text: str
    lemma: str
    question_ids: List[int]
    color: str


class LexicalMatcher:
    """Extracts target lemmas from questions and locates matches in body text."""

    def __init__(self, config: Optional[SnipperConfig] = None):
        self.config = config or SnipperConfig()
        self.nlp: Optional[Language] = None
        self.resolved_lang: Optional[str] = None

    def initialize_language(self, sample_text: str):
        if self.config.language and self.config.language.lower() != "auto":
            lang = self.config.language
        else:
            lang = detect_language(sample_text)
        self.resolved_lang = lang
        self.nlp = load_spacy_model(lang)

    def extract_question_lemmas(self, questions: List[Question]) -> Dict[str, List[int]]:
        """Extracts noun/proper-noun lemmas mapped to question IDs."""
        if self.nlp is None:
            raise RuntimeError("LexicalMatcher language not initialized.")

        lemma_to_questions: Dict[str, List[int]] = {}

        for q in questions:
            if q.keywords:
                for kw in q.keywords:
                    doc = self.nlp(kw)
                    for token in doc:
                        if token.is_stop or token.is_punct or token.is_space:
                            continue
                        lemma = token.lemma_.lower().strip()
                        if not lemma:
                            continue
                        if lemma not in lemma_to_questions:
                            lemma_to_questions[lemma] = []
                        if q.id not in lemma_to_questions[lemma]:
                            lemma_to_questions[lemma].append(q.id)
            else:
                doc = self.nlp(q.text)
                for token in doc:
                    if token.is_stop or token.is_punct or token.is_space:
                        continue
                    if token.pos_ in ("VERB", "ADP", "CCONJ", "SCONJ", "AUX"):
                        continue

                    if self.config.proper_nouns_only:
                        if token.pos_ != "PROPN":
                            continue
                    else:
                        if token.pos_ not in ("NOUN", "PROPN"):
                            continue

                    lemma = token.lemma_.lower().strip()
                    if not lemma:
                        continue

                    if lemma not in lemma_to_questions:
                        lemma_to_questions[lemma] = []
                    if q.id not in lemma_to_questions[lemma]:
                        lemma_to_questions[lemma].append(q.id)

        return lemma_to_questions

    def scan_body(
        self,
        body_paragraphs: List[Tuple[int, Any]],
        lemma_to_questions: Dict[str, List[int]],
        questions_by_id: Dict[int, Question],
    ) -> List[LemmaMatch]:
        """Scans body paragraphs for question lemmas and returns character spans."""
        if self.nlp is None:
            raise RuntimeError("LexicalMatcher language not initialized.")

        matches: List[LemmaMatch] = []

        for p_idx, p_obj in body_paragraphs:
            text = p_obj.text
            if not text.strip():
                continue

            doc = self.nlp(text)
            for token in doc:
                if token.is_stop or token.is_punct or token.is_space:
                    continue

                lemma = token.lemma_.lower().strip()
                if lemma in lemma_to_questions:
                    q_ids = lemma_to_questions[lemma]
                    primary_q_id = q_ids[0]
                    color = questions_by_id[primary_q_id].color

                    matches.append(
                        LemmaMatch(
                            paragraph_idx=p_idx,
                            start_char=token.idx,
                            end_char=token.idx + len(token.text),
                            text=token.text,
                            lemma=lemma,
                            question_ids=list(q_ids),
                            color=color,
                        )
                    )

        return matches
