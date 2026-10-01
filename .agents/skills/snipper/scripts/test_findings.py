import sys
from pathlib import Path
import tempfile

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from findings import (
    FindingsData,
    format_superscript_citations,
    to_superscript_num,
)


def test_superscript_formatting():
    assert to_superscript_num(1) == "¹"
    assert to_superscript_num(2) == "²"
    assert to_superscript_num(3) == "³"
    assert to_superscript_num(10) == "¹⁰"
    assert format_superscript_citations([1]) == "¹"
    assert format_superscript_citations([1, 2]) == "¹,²"
    assert format_superscript_citations([3, 1]) == "¹,³"
    assert format_superscript_citations(["Q1", "O1"]) == "O¹,Q¹"
    assert format_superscript_citations(["Q2", "Q1"]) == "Q¹,Q²"
    assert format_superscript_citations([]) == ""


def test_findings_validation():
    data = {
        "findings": [
            {
                "question_numbers": [1, 2],
                "snippet_text": "In 1984, John Doe founded ACME Corp in Boston.",
                "web_sources": ["https://example.com/acme"],
            }
        ],
        "unanswered_questions": [3],
    }

    fd = FindingsData.from_dict(data)
    assert len(fd.findings) == 1
    assert fd.findings[0].question_numbers == [1, 2]
    assert fd.findings[0].target_ids == ["Q1", "Q2"]
    assert "John Doe" in fd.findings[0].snippet_text
    assert fd.findings[0].web_sources == ["https://example.com/acme"]
    assert fd.unanswered_questions == [3]
    assert fd.unanswered_targets == ["Q3"]


def test_findings_from_file(tmp_path: Path):
    fpath = tmp_path / "findings.json"
    fpath.write_text(
        '{"findings": [{"question_numbers": [1], "snippet_text": "Sentence."}], "unanswered_questions": []}',
        encoding="utf-8",
    )
    fd = FindingsData.from_file(fpath)
    assert len(fd.findings) == 1
    assert fd.findings[0].question_numbers == [1]
    assert fd.findings[0].target_ids == ["Q1"]


def test_findings_with_keywords_and_concepts():
    data = {
        "findings": [
            {
                "question_numbers": [1],
                "snippet_text": "The company complies with GDPR right to erasure.",
                "keywords": ["GDPR", "erasure"],
                "concepts": [
                    {
                        "name": "Right to erasure",
                        "definition": "Right to have personal data erased under GDPR Article 17.",
                        "source_url": "https://ec.europa.eu/gdpr",
                    }
                ],
                "web_sources": ["https://ec.europa.eu/gdpr"],
            }
        ],
        "unanswered_questions": [],
    }

    fd = FindingsData.from_dict(data)
    assert len(fd.findings) == 1
    f = fd.findings[0]
    assert f.keywords == ["GDPR", "erasure"]
    assert len(f.concepts) == 1
    assert f.concepts[0].name == "Right to erasure"
    assert "Article 17" in f.concepts[0].definition
    assert f.concepts[0].source_url == "https://ec.europa.eu/gdpr"


def test_findings_with_target_ids():
    data = {
        "findings": [
            {
                "target_ids": ["Q1", "O2"],
                "snippet_text": "Audit trails must be enabled.",
                "keywords": ["audit", "trails"],
            }
        ],
        "unanswered_targets": ["O3"],
    }
    fd = FindingsData.from_dict(data)
    assert len(fd.findings) == 1
    assert fd.findings[0].target_ids == ["Q1", "O2"]
    assert fd.findings[0].question_numbers == [1, 2]
    assert fd.unanswered_targets == ["O3"]
    assert fd.unanswered_questions == [3]


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as td:
        tpath = Path(td)
        test_superscript_formatting()
        test_findings_validation()
        test_findings_from_file(tpath)
        test_findings_with_keywords_and_concepts()
        test_findings_with_target_ids()
    print("Findings tests passed!")
