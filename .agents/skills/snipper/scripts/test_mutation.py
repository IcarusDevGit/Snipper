import sys
from pathlib import Path
import tempfile
import docx

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from config import SnipperConfig
from document import DocumentParser, Question
from findings import Finding, FindingConcept, FindingsData
from mutation import DocumentMutator
from nlp import LemmaMatch


def test_document_mutator_end_to_end(tmp_path: Path):
    doc_path = tmp_path / "mutator_test.docx"
    doc = docx.Document()
    
    doc.add_paragraph("Questions")
    doc.add_paragraph("1. Who founded ACME Corp?")
    doc.add_paragraph("2. Where was it established?")
    doc.add_paragraph("3. What is the stock symbol?")
    
    doc.add_paragraph("Body")
    doc.add_paragraph("In 1984, John Doe founded ACME Corp in Boston.")
    doc.add_paragraph("The firm grew rapidly over the subsequent decade.")
    doc.save(doc_path)

    cfg = SnipperConfig(palette=["#FFFF7F", "#7FFFFF", "#7FFF7F"])
    parser = DocumentParser(cfg)
    parsed = parser.parse(doc_path)

    body_sample_text = "In 1984, John Doe founded ACME Corp in Boston."
    acme_idx = body_sample_text.find("ACME Corp")
    boston_idx = body_sample_text.find("Boston")

    # Lexical match for "ACME Corp" and "Boston"
    matches = [
        LemmaMatch(
            paragraph_idx=parsed.body_paragraphs[0][0],
            start_char=acme_idx,
            end_char=acme_idx + len("ACME Corp"),
            text="ACME Corp",
            lemma="acme corp",
            question_ids=[1],
            color="#FFFF7F",
        ),
        LemmaMatch(
            paragraph_idx=parsed.body_paragraphs[0][0],
            start_char=boston_idx,
            end_char=boston_idx + len("Boston"),
            text="Boston",
            lemma="boston",
            question_ids=[2],
            color="#7FFFFF",
        ),
    ]

    findings = FindingsData(
        findings=[
            Finding(
                question_numbers=[1],
                snippet_text="In 1984, John Doe founded ACME Corp in Boston.",
                web_sources=["https://example.com/source"],
            ),
            Finding(
                question_numbers=[2],
                snippet_text="in Boston",
                web_sources=[],
            ),
        ],
        unanswered_questions=[3],
    )

    mutator = DocumentMutator(cfg)
    mutator.mutate(parsed, matches, findings, output_path=doc_path)

    # Re-open and verify
    mutated = docx.Document(doc_path)
    all_paras = [p.text for p in mutated.paragraphs]

    # Check Summary block inserted
    assert any("Questions & Answers" in p for p in all_paras)
    assert any("Q1: Who founded ACME Corp?" in p for p in all_paras)
    assert any("Q2: Where was it established?" in p for p in all_paras)
    assert any("Q3: What is the stock symbol?" in p for p in all_paras)
    assert any("[No answering evidence found in text]" in p for p in all_paras)
    assert any("https://example.com/source" in p for p in all_paras)

    # Verify Body paragraph has bolding on match inside snippet
    body_idx = next(i for i, p in enumerate(mutated.paragraphs) if p.text.strip().lower() == "body")
    body_p = mutated.paragraphs[body_idx + 1]
    bold_runs = [r.text for r in body_p.runs if r.bold]
    assert any("ACME Corp" in t for t in bold_runs)


def test_mutator_renders_keywords_and_concepts_in_summary(tmp_path: Path):
    doc_path = tmp_path / "mutator_kw_concepts.docx"
    doc = docx.Document()
    
    doc.add_paragraph("Questions")
    doc.add_paragraph("1. What is quantum computing?")
    doc.add_paragraph("- Keywords: quantum computing, qubits")
    doc.add_paragraph("- Concepts: superposition (web: true)")
    doc.add_paragraph("2. Who coined the term qubit?")
    
    doc.add_paragraph("Body")
    doc.add_paragraph("Quantum computing utilizes qubits for calculations. Superposition allows multiple states.")
    doc.add_paragraph("Benjamin Schumacher coined the term qubit in 1995.")
    doc.add_paragraph("Later in 1996, Schumacher wrote another paper.")
    doc.save(doc_path)

    cfg = SnipperConfig()
    parser = DocumentParser(cfg)
    parsed = parser.parse(doc_path)

    findings = FindingsData(
        findings=[
            Finding(
                question_numbers=[1],
                snippet_text="Quantum computing utilizes qubits for calculations. Superposition allows multiple states.",
                keywords=["quantum computing", "qubits"],
                concepts=[
                    FindingConcept(
                        name="superposition",
                        definition="Physical principle of existing in multiple states simultaneously",
                        source_url="https://en.wikipedia.org/wiki/Quantum_superposition",
                    )
                ],
            ),
            Finding(
                question_numbers=[2],
                snippet_text="Benjamin Schumacher coined the term qubit in 1995.",
                keywords=["Schumacher", "qubit"],
            ),
        ]
    )

    mutator = DocumentMutator(cfg)
    mutator.mutate(parsed, matches=[], findings_data=findings, output_path=doc_path)

    mutated = docx.Document(doc_path)
    all_paras = [p.text for p in mutated.paragraphs]

    # Check Summary block contains Q1 details
    assert any("Q1: What is quantum computing?" in p for p in all_paras)
    assert any("  * Keywords: quantum computing, qubits" in p for p in all_paras)
    assert any("  * Concept: superposition - Physical principle of existing in multiple states simultaneously (Source: https://en.wikipedia.org/wiki/Quantum_superposition)" in p for p in all_paras)
    assert any('  * Snippet: "Quantum computing utilizes qubits for calculations. Superposition allows multiple states."' in p for p in all_paras)

    # Check Summary block contains Q2 details
    assert any("Q2: Who coined the term qubit?" in p for p in all_paras)
    assert any("  * Keywords: Schumacher, qubit" in p for p in all_paras)

    # Check bold runs in body paragraphs for keywords inside snippets
    body_idx = next(i for i, p in enumerate(mutated.paragraphs) if p.text.strip().lower() == "body")
    p1 = mutated.paragraphs[body_idx + 1]
    bold_runs_p1 = [r.text for r in p1.runs if r.bold]
    assert any("Quantum computing" in r or "qubits" in r for r in bold_runs_p1)

    p2 = mutated.paragraphs[body_idx + 2]
    bold_runs_p2 = [r.text for r in p2.runs if r.bold]
    assert any("Schumacher" in r or "qubit" in r for r in bold_runs_p2)

    # Check keywords outside snippets: p3 has "Schumacher", which must be highlighted but NOT bolded
    p3 = mutated.paragraphs[body_idx + 3]
    schumacher_run = next(r for r in p3.runs if "Schumacher" in r.text)
    assert schumacher_run.bold is not True
    shd = schumacher_run._r.get_or_add_rPr().find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}shd")
    assert shd is not None


def test_mutator_cross_paragraph_snippet(tmp_path: Path):
    doc_path = tmp_path / "mutator_cross_para.docx"
    doc = docx.Document()

    doc.add_paragraph("Questions")
    doc.add_paragraph("1. What are core beliefs?")

    doc.add_paragraph("Body")
    doc.add_paragraph("Core beliefs are our most central ideas about")
    doc.add_paragraph("ourselves, about others, and about the world.")
    doc.save(doc_path)

    cfg = SnipperConfig()
    parser = DocumentParser(cfg)
    parsed = parser.parse(doc_path)

    findings = FindingsData(
        findings=[
            Finding(
                question_numbers=[1],
                snippet_text="Core beliefs are our most central ideas about ourselves, about others, and about the world.",
                keywords=["Core beliefs"],
            )
        ]
    )

    mutator = DocumentMutator(cfg)
    mutator.mutate(parsed, matches=[], findings_data=findings, output_path=doc_path)

    mutated = docx.Document(doc_path)
    body_idx = next(i for i, p in enumerate(mutated.paragraphs) if p.text.strip().lower() == "body")
    p1 = mutated.paragraphs[body_idx + 1]
    p2 = mutated.paragraphs[body_idx + 2]

    # Verify both paragraphs have runs highlighted with Q1 color
    p1_shd = [r._r.get_or_add_rPr().find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}shd") for r in p1.runs]
    p2_shd = [r._r.get_or_add_rPr().find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}shd") for r in p2.runs]
    assert any(s is not None for s in p1_shd)
    assert any(s is not None for s in p2_shd)

    # Verify superscript citation appears only on the trailing paragraph p2
    assert not any("¹" in r.text for r in p1.runs)
    assert any("¹" in r.text for r in p2.runs)


def test_idempotent_remutation(tmp_path: Path):
    doc_path = tmp_path / "remutate_test.docx"
    q_path = tmp_path / "remutate_test.questions.txt"

    q_path.write_text(
        "Q1: What is the retention policy?\n"
        "  - Keywords: retention, 7 years\n"
        "O1: Audit all database backups.\n"
        "  - Keywords: backups, S3\n",
        encoding="utf-8",
    )

    doc = docx.Document()
    doc.add_paragraph("The retention policy mandates keeping audit records for 7 years.")
    doc.add_paragraph("All database backups are archived to immutable S3 buckets.")
    doc.save(doc_path)

    cfg = SnipperConfig()
    parser = DocumentParser(cfg)
    parsed = parser.parse(doc_path)

    findings_pass1 = FindingsData(
        findings=[
            Finding(
                question_numbers=[1],
                target_ids=["Q1"],
                snippet_text="The retention policy mandates keeping audit records for 7 years.",
                keywords=["retention", "7 years"],
            )
        ]
    )

    mutator = DocumentMutator(cfg)
    mutator.mutate(parsed, matches=[], findings_data=findings_pass1, output_path=doc_path)

    # First verification
    doc_v1 = docx.Document(doc_path)
    paras_v1 = [p.text for p in doc_v1.paragraphs]
    start_count_v1 = paras_v1.count("=== SNIPPER SUMMARY START ===")
    end_count_v1 = paras_v1.count("=== SNIPPER SUMMARY END ===")
    assert start_count_v1 == 1
    assert end_count_v1 == 1
    assert any("Q1: What is the retention policy?" in p for p in paras_v1)
    assert not any("O1: Audit all database backups." in p and "Snippet:" in p for p in paras_v1)

    # Second pass: re-parse and re-mutate with updated findings including O1
    parsed_v2 = parser.parse(doc_path)
    findings_pass2 = FindingsData(
        findings=[
            Finding(
                question_numbers=[1],
                target_ids=["Q1"],
                snippet_text="The retention policy mandates keeping audit records for 7 years.",
                keywords=["retention", "7 years"],
            ),
            Finding(
                question_numbers=[2],
                target_ids=["O1"],
                snippet_text="All database backups are archived to immutable S3 buckets.",
                keywords=["backups", "S3"],
            ),
        ]
    )

    mutator.mutate(parsed_v2, matches=[], findings_data=findings_pass2, output_path=doc_path)

    # Second verification: must NOT have duplicated summary block
    doc_v2 = docx.Document(doc_path)
    paras_v2 = [p.text for p in doc_v2.paragraphs]
    start_count_v2 = paras_v2.count("=== SNIPPER SUMMARY START ===")
    end_count_v2 = paras_v2.count("=== SNIPPER SUMMARY END ===")
    assert start_count_v2 == 1
    assert end_count_v2 == 1
    assert any("Q1: What is the retention policy?" in p for p in paras_v2)
    assert any("O1: Audit all database backups." in p for p in paras_v2)
    assert any('  * Snippet: "All database backups are archived to immutable S3 buckets."' in p for p in paras_v2)


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as td:
        tpath = Path(td)
        test_document_mutator_end_to_end(tpath)
        test_mutator_renders_keywords_and_concepts_in_summary(tpath)
        test_mutator_cross_paragraph_snippet(tpath)
        test_idempotent_remutation(tpath)
    print("Mutation tests passed!")
