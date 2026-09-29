import sys
from pathlib import Path
import tempfile
import docx

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from config import SnipperConfig
from document import Question
from highlighter import DocumentHighlighter, highlight_paragraph_spans
from nlp import LemmaMatch


def test_highlight_paragraph_spans_hex():
    doc = docx.Document()
    p = doc.add_paragraph()
    r1 = p.add_run("The quick ")
    r2 = p.add_run("brown fox ")
    r2.bold = True
    r3 = p.add_run("jumps over.")

    # "quick brown" spans: "quick " (4-10) in r1, "brown" (10-15) in r2
    # Let's highlight "brown" which is at chars 10-15
    highlight_paragraph_spans(p, [(10, 15, "#FFFF7F", False)], default_palette_mode="hex")

    assert p.text == "The quick brown fox jumps over."
    runs = p.runs
    assert len(runs) >= 3

    # Find the run containing "brown"
    brown_run = next(r for r in runs if "brown" in r.text)
    assert brown_run.bold is True
    # Verify XML shading exists
    rPr = brown_run._r.get_or_add_rPr()
    shd = rPr.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}shd")
    assert shd is not None
    assert shd.attrib["{http://schemas.openxmlformats.org/wordprocessingml/2006/main}fill"] == "FFFF7F"


def test_document_highlighter_flow(tmp_path: Path):
    doc_path = tmp_path / "highlight_test.docx"
    doc = docx.Document()
    p = doc.add_paragraph("Alan Turing was a mathematician in London.")
    doc.save(doc_path)

    doc = docx.Document(doc_path)
    p_obj = doc.paragraphs[0]

    matches = [
        LemmaMatch(
            paragraph_idx=0,
            start_char=0,
            end_char=11,
            text="Alan Turing",
            lemma="alan turing",
            question_ids=[1],
            color="#7FFFFF",
        )
    ]

    cfg = SnipperConfig(palette_mode="hex")
    highlighter = DocumentHighlighter(cfg)
    highlighter.highlight_matches([(0, p_obj)], matches)

    doc.save(doc_path)

    # Re-open and verify
    reopened = docx.Document(doc_path)
    reopened_p = reopened.paragraphs[0]
    assert reopened_p.text == "Alan Turing was a mathematician in London."
    first_run = reopened_p.runs[0]
    assert first_run.text == "Alan Turing"
    rPr = first_run._r.get_or_add_rPr()
    shd = rPr.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}shd")
    assert shd is not None
    assert shd.attrib["{http://schemas.openxmlformats.org/wordprocessingml/2006/main}fill"] == "7FFFFF"


def test_document_highlighter_keywords(tmp_path: Path):
    doc_path = tmp_path / "kw_highlight_test.docx"
    doc = docx.Document()
    p = doc.add_paragraph("Alan Turing was a mathematician in London.")
    doc.save(doc_path)

    doc = docx.Document(doc_path)
    p_obj = doc.paragraphs[0]

    q1 = Question(id=1, text="Who was Alan Turing?", paragraph_idx=0, color="#FFFF7F", keywords=["Alan Turing", "London"])
    cfg = SnipperConfig(palette_mode="hex")
    highlighter = DocumentHighlighter(cfg)
    highlighter.highlight_keywords([(0, p_obj)], [q1])

    doc.save(doc_path)

    # Re-open and verify only keywords got highlighted
    reopened = docx.Document(doc_path)
    reopened_p = reopened.paragraphs[0]
    runs = reopened_p.runs
    
    # "Alan Turing" should be highlighted
    turing_run = next(r for r in runs if "Alan Turing" in r.text)
    rPr_turing = turing_run._r.get_or_add_rPr()
    shd_turing = rPr_turing.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}shd")
    assert shd_turing is not None
    assert shd_turing.attrib["{http://schemas.openxmlformats.org/wordprocessingml/2006/main}fill"] == "FFFF7F"

    # "London" should be highlighted
    london_run = next(r for r in runs if "London" in r.text)
    rPr_london = london_run._r.get_or_add_rPr()
    shd_london = rPr_london.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}shd")
    assert shd_london is not None

    # "mathematician" should NOT have shading
    math_run = next(r for r in runs if "mathematician" in r.text)
    rPr_math = math_run._r.get_or_add_rPr()
    shd_math = rPr_math.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}shd")
    assert shd_math is None


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as td:
        tpath = Path(td)
        test_highlight_paragraph_spans_hex()
        test_document_highlighter_flow(tpath)
        test_document_highlighter_keywords(tpath)
    print("Highlighter tests passed!")
