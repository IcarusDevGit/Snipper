import sys
from pathlib import Path
import tempfile
import docx

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from cli import main


def test_cli_highlight_subcommand(tmp_path: Path):
    doc_path = tmp_path / "highlight_sample.docx"
    doc = docx.Document()
    
    doc.add_paragraph("Questions")
    doc.add_paragraph("1. Who founded ACME Corp?")
    doc.add_paragraph("Body")
    doc.add_paragraph("In 1984, John Doe founded ACME Corp in Boston.")
    doc.save(doc_path)

    # Execute CLI with primary 'highlight' subcommand
    ret = main(["highlight", str(doc_path)])
    assert ret == 0

    # Verify modified document
    modified_doc = docx.Document(doc_path)
    body_p = modified_doc.paragraphs[3]
    p_shd = [r.text for r in body_p.runs if r._r.xpath(".//w:shd")]
    matched_text = " ".join(p_shd)
    assert "ACME" in matched_text or "Corp" in matched_text


def test_cli_lexical_only_english(tmp_path: Path):
    doc_path = tmp_path / "en_sample.docx"
    doc = docx.Document()
    
    # Header
    doc.add_paragraph("Questions")
    doc.add_paragraph("1. Who founded ACME Corp?")
    doc.add_paragraph("2. What patents were filed in Boston?")
    
    doc.add_paragraph("Body")
    doc.add_paragraph("In 1984, John Doe founded ACME Corp.")
    doc.add_paragraph("The company filed three patents in Boston.")
    doc.save(doc_path)

    # Execute CLI with --lexical-only
    ret = main(["run", str(doc_path), "--lexical-only"])
    assert ret == 0

    # Verify modified document
    modified_doc = docx.Document(doc_path)
    body_p1 = modified_doc.paragraphs[4]  # "In 1984, John Doe founded ACME Corp."
    body_p2 = modified_doc.paragraphs[5]  # "The company filed three patents in Boston."

    # Look for highlighted runs in body
    p1_shd = [r.text for r in body_p1.runs if r._r.xpath(".//w:shd")]
    p2_shd = [r.text for r in body_p2.runs if r._r.xpath(".//w:shd")]

    assert "ACME Corp" in " ".join(p1_shd) or "Corp" in " ".join(p1_shd) or "ACME" in " ".join(p1_shd)
    assert "patents" in p2_shd or "Boston" in p2_shd


def test_cli_match_subcommand_portuguese(tmp_path: Path):
    doc_path = tmp_path / "pt_sample.docx"
    doc = docx.Document()
    
    doc.add_paragraph("Perguntas")
    doc.add_paragraph("1. Quantas patentes os investidores registraram em São Paulo?")
    
    doc.add_paragraph("Corpo")
    doc.add_paragraph("Em 2020, os investidores registraram uma patente em São Paulo.")
    doc.save(doc_path)

    # Execute CLI with 'match' subcommand (alias)
    ret = main(["match", str(doc_path)])
    assert ret == 0

    # Verify modified document
    modified_doc = docx.Document(doc_path)
    body_p = modified_doc.paragraphs[3]

    p_shd = [r.text for r in body_p.runs if r._r.xpath(".//w:shd")]
    matched_text = " ".join(p_shd)
    assert "investidores" in matched_text or "patente" in matched_text or "Paulo" in matched_text


def test_cli_full_pipeline_with_findings(tmp_path: Path):
    doc_path = tmp_path / "full_pipeline.docx"
    findings_path = tmp_path / "findings.json"
    
    doc = docx.Document()
    doc.add_paragraph("Questions")
    doc.add_paragraph("1. Who founded ACME Corp?")
    doc.add_paragraph("Body")
    doc.add_paragraph("In 1984, John Doe founded ACME Corp.")
    doc.save(doc_path)

    findings_content = """{
        "findings": [
            {
                "question_numbers": [1],
                "snippet_text": "In 1984, John Doe founded ACME Corp.",
                "web_sources": ["https://example.com/acme"]
            }
        ],
        "unanswered_questions": []
    }"""
    findings_path.write_text(findings_content, encoding="utf-8")

    # Run CLI with --findings
    ret = main(["run", str(doc_path), "--findings", str(findings_path)])
    assert ret == 0

    # Verify mutated document
    mutated = docx.Document(doc_path)
    all_paras = [p.text for p in mutated.paragraphs]

    # Check Questions & Answers summary section exists
    assert any("Questions & Answers" in p for p in all_paras)
    assert any("Q1: Who founded ACME Corp?" in p for p in all_paras)
    assert any("https://example.com/acme" in p for p in all_paras)

    # Check Body paragraph contains bold match inside snippet
    body_idx = next(i for i, p in enumerate(mutated.paragraphs) if p.text.strip().lower() == "body")
    body_p = mutated.paragraphs[body_idx + 1]
    bold_runs = [r.text for r in body_p.runs if r.bold]
    assert any("ACME" in t or "Corp" in t for t in bold_runs)


def test_cli_full_pipeline_with_concepts_and_keywords(tmp_path: Path):
    doc_path = tmp_path / "cli_concepts_keywords.docx"
    findings_path = tmp_path / "findings_ck.json"

    doc = docx.Document()
    doc.add_paragraph("Questions")
    doc.add_paragraph("1. What is relativity?")
    doc.add_paragraph("- Keywords: relativity, spacetime")
    doc.add_paragraph("- Concepts: spacetime (web: true)")
    doc.add_paragraph("Body")
    doc.add_paragraph("Einstein formulated relativity. In physics, spacetime describes the unified fabric of the universe.")
    doc.save(doc_path)

    findings_content = """{
        "findings": [
            {
                "question_numbers": [1],
                "snippet_text": "Einstein formulated relativity. In physics, spacetime describes the unified fabric of the universe.",
                "web_sources": ["https://en.wikipedia.org/wiki/Spacetime"],
                "keywords": ["relativity", "spacetime"],
                "concepts": [
                    {
                        "name": "spacetime",
                        "definition": "Mathematical model joining space and time into a single continuum",
                        "source_url": "https://en.wikipedia.org/wiki/Spacetime"
                    }
                ]
            }
        ],
        "unanswered_questions": []
    }"""
    findings_path.write_text(findings_content, encoding="utf-8")

    ret = main(["run", str(doc_path), "--findings", str(findings_path)])
    assert ret == 0

    mutated = docx.Document(doc_path)
    all_paras = [p.text for p in mutated.paragraphs]

    assert any("Questions & Answers" in p for p in all_paras)
    assert any("Q1: What is relativity?" in p for p in all_paras)
    assert any("  * Keywords: relativity, spacetime" in p for p in all_paras)
    assert any("  * Concept: spacetime - Mathematical model joining space and time into a single continuum (Source: https://en.wikipedia.org/wiki/Spacetime)" in p for p in all_paras)
    assert any('  * Snippet: "Einstein formulated relativity. In physics, spacetime describes the unified fabric of the universe."' in p for p in all_paras)

    body_idx = next(i for i, p in enumerate(mutated.paragraphs) if p.text.strip().lower() == "body")
    body_p = mutated.paragraphs[body_idx + 1]
    bold_runs = [r.text for r in body_p.runs if r.bold]
    assert any("relativity" in t or "spacetime" in t for t in bold_runs)


def test_cli_dump_subcommand(tmp_path: Path):
    doc_path = tmp_path / "dump_sample.docx"
    doc = docx.Document()
    doc.add_paragraph("Questions")
    doc.add_paragraph("1. What is the SLA uptime?")
    doc.add_paragraph("Body")
    doc.add_paragraph("The service maintains 99.99% availability.")
    doc.save(doc_path)

    # 1. Test default dump
    ret = main(["dump", str(doc_path)])
    assert ret == 0
    default_txt = tmp_path / "dump_sample.snipper.txt"
    assert default_txt.exists()
    content = default_txt.read_text(encoding="utf-8")
    assert "=== QUESTIONS ===" in content
    assert "1. What is the SLA uptime?" in content
    assert "=== BODY ===" in content
    assert "[P0] The service maintains 99.99% availability." in content

    # 2. Test explicit output path
    custom_out = tmp_path / "custom.txt"
    ret = main(["dump", str(doc_path), "--output", str(custom_out)])
    assert ret == 0
    assert custom_out.exists()
    assert custom_out.read_text(encoding="utf-8") == content


def test_cli_auto_sync_txt(tmp_path: Path):
    doc_path = tmp_path / "auto_sync_sample.docx"
    doc = docx.Document()
    doc.add_paragraph("Questions")
    doc.add_paragraph("1. Who leads the project?")
    doc.add_paragraph("Body")
    doc.add_paragraph("Jane Smith leads the development team.")
    doc.save(doc_path)

    companion_txt = tmp_path / "auto_sync_sample.snipper.txt"
    assert not companion_txt.exists()

    # Running the pipeline should auto-generate the companion file
    ret = main(["run", str(doc_path), "--lexical-only"])
    assert ret == 0
    assert companion_txt.exists()
    txt_content = companion_txt.read_text(encoding="utf-8")
    assert "1. Who leads the project?" in txt_content
    assert "[P0] Jane Smith leads the development team." in txt_content


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as td:
        tpath = Path(td)
        test_cli_highlight_subcommand(tpath)
        test_cli_lexical_only_english(tpath)
        test_cli_match_subcommand_portuguese(tpath)
        test_cli_full_pipeline_with_findings(tpath)
        test_cli_full_pipeline_with_concepts_and_keywords(tpath)
        test_cli_dump_subcommand(tpath)
        test_cli_auto_sync_txt(tpath)
    print("All CLI tests passed!")
