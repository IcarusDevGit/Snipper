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

    # Check Summary block contains Q1 details (Keywords as bullets, no 'Snippet:' marker)
    assert any("Q1: What is quantum computing?" in p for p in all_paras)
    assert "Keywords:" in all_paras
    assert "  • quantum computing" in all_paras
    assert "  • qubits" in all_paras
    assert "Concepts:" in all_paras
    assert "  • superposition - Physical principle of existing in multiple states simultaneously (Source: https://en.wikipedia.org/wiki/Quantum_superposition)" in all_paras
    assert any('"Quantum computing utilizes qubits for calculations. Superposition allows multiple states."' in p for p in all_paras)
    assert not any("Snippet:" in p for p in all_paras)

    # Check Summary block contains Q2 details
    assert any("Q2: Who coined the term qubit?" in p for p in all_paras)
    assert "  • Schumacher" in all_paras
    assert "  • qubit" in all_paras

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
    assert not any("All database backups are archived to immutable S3 buckets." in p for p in paras_v1 if "S3" in p and p.startswith('"'))

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
    assert any('"All database backups are archived to immutable S3 buckets."' in p for p in paras_v2)
    assert not any("Snippet:" in p for p in paras_v2)


def test_document_mutator_stream_in_memory():
    import io

    # Create document in memory
    doc = docx.Document()
    doc.add_paragraph("In 1984, John Doe founded ACME Corp in Boston.")
    doc.add_paragraph("The firm grew rapidly over the subsequent decade.")
    in_stream = io.BytesIO()
    doc.save(in_stream)
    in_stream.seek(0)

    cfg = SnipperConfig(palette=["#FFFF7F", "#7FFFFF"])
    parser = DocumentParser(cfg)
    parsed = parser.parse(
        in_stream,
        questions_text="Q1: Who founded ACME Corp?\n  - Keywords: founded\n",
        virtual_path="virtual.docx",
    )

    findings = FindingsData(
        findings=[
            Finding(
                question_numbers=[1],
                target_ids=["Q1"],
                snippet_text="John Doe founded ACME Corp",
                keywords=["founded"],
            )
        ]
    )

    mutator = DocumentMutator(cfg)
    out_stream = io.BytesIO()
    result = mutator.mutate(parsed, matches=[], findings_data=findings, output_path=out_stream)

    assert result is out_stream
    out_stream.seek(0)

    # Verify mutated document from stream
    mutated_doc = docx.Document(out_stream)
    paras = [p.text for p in mutated_doc.paragraphs]
    assert "=== SNIPPER SUMMARY START ===" in paras
    assert any("Q1: Who founded ACME Corp?" in p for p in paras)


def test_hex_to_rgb_color():
    from mutation import hex_to_rgb_color

    yellow = hex_to_rgb_color("#FFFF00")
    assert yellow == {"red": 1.0, "green": 1.0, "blue": 0.0}

    green = hex_to_rgb_color("#00FF00")
    assert green == {"red": 0.0, "green": 1.0, "blue": 0.0}

    white = hex_to_rgb_color("#FFFFFF")
    assert white == {"red": 1.0, "green": 1.0, "blue": 1.0}


def test_detect_summary_block_range_gdoc():
    from mutation import detect_summary_block_range

    # 1. Document with summary block
    doc_with_summary = {
        "body": {
            "content": [
                {"endIndex": 1},
                {
                    "startIndex": 1,
                    "endIndex": 31,
                    "paragraph": {
                        "elements": [{"textRun": {"content": "=== SNIPPER SUMMARY START ===\n"}}]
                    },
                },
                {
                    "startIndex": 31,
                    "endIndex": 70,
                    "paragraph": {
                        "elements": [{"textRun": {"content": "Questions & Answers\n"}}]
                    },
                },
                {
                    "startIndex": 70,
                    "endIndex": 99,
                    "paragraph": {
                        "elements": [{"textRun": {"content": "=== SNIPPER SUMMARY END ===\n"}}]
                    },
                },
                {
                    "startIndex": 99,
                    "endIndex": 150,
                    "paragraph": {
                        "elements": [{"textRun": {"content": "Body text paragraph.\n"}}]
                    },
                },
            ]
        }
    }
    rng = detect_summary_block_range(doc_with_summary)
    assert rng == (1, 99)

    # 2. Document without summary block
    doc_clean = {
        "body": {
            "content": [
                {"endIndex": 1},
                {
                    "startIndex": 1,
                    "endIndex": 50,
                    "paragraph": {
                        "elements": [{"textRun": {"content": "Clean document text.\n"}}]
                    },
                },
            ]
        }
    }
    assert detect_summary_block_range(doc_clean) is None


def test_gdoc_mutator_build_requests_atomic():
    import io
    from unittest.mock import MagicMock
    from mutation import GoogleDocsMutator

    cfg = SnipperConfig(palette=["#FFFF00"])
    parser = DocumentParser(cfg)
    stream = io.BytesIO(b"Data at rest must be encrypted using AES-256.\n")
    parsed = parser.parse(
        stream,
        questions_text="Q1: What is the encryption standard?\n  - Keywords: AES-256, encrypted\n",
        virtual_path="doc.gdoc",
    )

    findings = FindingsData(
        findings=[
            Finding(
                question_numbers=[1],
                target_ids=["Q1"],
                snippet_text="Data at rest must be encrypted using AES-256.",
                keywords=["AES-256", "encrypted"],
            )
        ]
    )

    doc_data = {
        "body": {
            "content": [
                {"endIndex": 1},
                {
                    "startIndex": 1,
                    "endIndex": 47,
                    "paragraph": {
                        "elements": [
                            {"textRun": {"content": "Data at rest must be encrypted using AES-256.\n"}}
                        ]
                    },
                },
            ]
        }
    }

    mutator = GoogleDocsMutator(cfg)
    requests = mutator.build_mutation_requests(doc_data, parsed, matches=[], findings_data=findings)

    # Must contain insertText at index 1
    insert_reqs = [r for r in requests if "insertText" in r]
    assert len(insert_reqs) == 1
    assert insert_reqs[0]["insertText"]["location"]["index"] == 1
    assert "=== SNIPPER SUMMARY START ===" in insert_reqs[0]["insertText"]["text"]
    assert "=== SNIPPER SUMMARY END ===" in insert_reqs[0]["insertText"]["text"]

    # Must contain updateTextStyle requests
    style_reqs = [r for r in requests if "updateTextStyle" in r]
    assert len(style_reqs) > 0

    # Verify background color highlight request with RGB floats
    bg_reqs = [
        r for r in style_reqs
        if "backgroundColor" in r["updateTextStyle"].get("fields", "")
    ]
    assert len(bg_reqs) > 0
    rgb = bg_reqs[0]["updateTextStyle"]["textStyle"]["backgroundColor"]["color"]["rgbColor"]
    assert rgb == {"red": 1.0, "green": 1.0, "blue": 0.0}

    # Verify bold styling requests
    bold_reqs = [
        r for r in style_reqs
        if "bold" in r["updateTextStyle"].get("fields", "")
    ]
    assert len(bold_reqs) > 0
    assert bold_reqs[0]["updateTextStyle"]["textStyle"]["bold"] is True


def test_gdoc_mutator_mutate_batch_update():
    import io
    from unittest.mock import MagicMock
    from mutation import GoogleDocsMutator

    cfg = SnipperConfig(palette=["#00FF00"])
    parser = DocumentParser(cfg)
    stream = io.BytesIO(b"Firewall rules prevent unauthorized egress.\n")
    parsed = parser.parse(
        stream,
        questions_text="O1: Audit network traffic.\n",
        virtual_path="doc.gdoc",
    )

    findings = FindingsData(
        findings=[
            Finding(
                question_numbers=[1],
                target_ids=["O1"],
                snippet_text="Firewall rules prevent unauthorized egress.",
            )
        ]
    )

    mock_service = MagicMock()
    mock_docs = MagicMock()
    mock_service.documents.return_value = mock_docs

    mock_docs.get.return_value.execute.return_value = {
        "body": {
            "content": [
                {"endIndex": 1},
                {
                    "startIndex": 1,
                    "endIndex": 44,
                    "paragraph": {
                        "elements": [
                            {"textRun": {"content": "Firewall rules prevent unauthorized egress.\n"}}
                        ]
                    },
                },
            ]
        }
    }
    mock_docs.batchUpdate.return_value.execute.return_value = {
        "documentId": "fake-doc-id",
        "replies": [],
    }

    mutator = GoogleDocsMutator(cfg, docs_service=mock_service)
    res = mutator.mutate("fake-doc-id", parsed, matches=[], findings_data=findings)

    assert res["documentId"] == "fake-doc-id"
    mock_docs.batchUpdate.assert_called_once()
    call_kwargs = mock_docs.batchUpdate.call_args[1]
    assert call_kwargs["documentId"] == "fake-doc-id"
    assert "requests" in call_kwargs["body"]
    assert len(call_kwargs["body"]["requests"]) > 0


def test_summary_block_visual_polish_docx_and_gdoc(tmp_path: Path):
    """Verifies clean summary output: bullet-point Keywords, no 'Snippet:' marker, and blank space between snippets."""
    import io
    from mutation import GoogleDocsMutator

    doc_path = tmp_path / "polish_test.docx"
    doc = docx.Document()
    doc.add_paragraph("First evidence sentence explains domain values.")
    doc.add_paragraph("Second evidence sentence explains codomain values.")
    doc.save(doc_path)

    cfg = SnipperConfig(palette=["#ea7286"])
    parser = DocumentParser(cfg)
    parsed = parser.parse(
        doc_path,
        questions_file=None,
    )
    parsed = parser.parse(
        io.BytesIO(doc_path.read_bytes()),
        questions_text="Q1: Explain domain and codomain.\n  - Keywords: domain, codomain, function\n",
        virtual_path="polish_test.docx",
    )

    findings = FindingsData(
        findings=[
            Finding(
                question_numbers=[1],
                target_ids=["Q1"],
                snippet_text="First evidence sentence explains domain values.",
                keywords=["domain", "codomain", "function"],
            ),
            Finding(
                question_numbers=[1],
                target_ids=["Q1"],
                snippet_text="Second evidence sentence explains codomain values.",
                keywords=["domain", "codomain", "function"],
            ),
        ]
    )

    # 1. Verify Word (.docx) summary block
    out_stream = io.BytesIO()
    mutator = DocumentMutator(cfg)
    mutator.mutate(parsed, matches=[], findings_data=findings, output_path=out_stream)
    out_stream.seek(0)
    mutated = docx.Document(out_stream)
    paras = [p.text for p in mutated.paragraphs]

    assert not any("Snippet:" in p for p in paras)
    assert "Keywords:" in paras
    assert "  • domain" in paras
    assert "  • codomain" in paras
    assert "  • function" in paras

    idx1 = next(i for i, p in enumerate(paras) if p.startswith('"First evidence sentence explains domain values."'))
    idx2 = next(i for i, p in enumerate(paras) if p.startswith('"Second evidence sentence explains codomain values."'))
    assert idx2 == idx1 + 2
    assert paras[idx1 + 1] == ""

    # 2. Verify Google Docs (.gdoc) summary block
    g_mutator = GoogleDocsMutator(cfg)
    summary_text, _ = g_mutator.build_summary_block_text(parsed, findings)
    assert "Snippet:" not in summary_text
    assert "Keywords:\n  • domain\n  • codomain\n  • function\n" in summary_text
    assert '"First evidence sentence explains domain values." Q¹\n\n"Second evidence sentence explains codomain values." Q¹\n' in summary_text


def test_q1_and_o1_do_not_cross_leak_in_summary(tmp_path: Path):
    """Ensures Q1 and O1 with identical numeric IDs stay isolated in summary blocks."""
    import io

    doc_path = tmp_path / "q1_o1_isolation.docx"
    doc = docx.Document()
    doc.add_paragraph("Data at rest uses AES-256.")
    doc.add_paragraph("Access requires MFA.")
    doc.save(doc_path)

    cfg = SnipperConfig(palette=["#ea7286", "#eab281"])
    parser = DocumentParser(cfg)
    parsed = parser.parse(
        io.BytesIO(doc_path.read_bytes()),
        questions_text="Q1: Encryption?\n  - Keywords: AES-256\nO1: Access control?\n  - Keywords: MFA\n",
        virtual_path="q1_o1_isolation.docx",
    )
    findings = FindingsData.from_dict({
        "findings": [
            {"target_ids": ["Q1"], "snippet_text": "Data at rest uses AES-256.", "keywords": ["AES-256"]},
            {"target_ids": ["O1"], "snippet_text": "Access requires MFA.", "keywords": ["MFA"]},
        ],
        "unanswered_targets": [],
    })

    out_stream = io.BytesIO()
    DocumentMutator(cfg).mutate(parsed, matches=[], findings_data=findings, output_path=out_stream)
    out_stream.seek(0)
    paras = [p.text for p in docx.Document(out_stream).paragraphs]

    q1_idx = next(i for i, p in enumerate(paras) if p.startswith("Q1:"))
    o1_idx = next(i for i, p in enumerate(paras) if p.startswith("O1:"))
    end_idx = paras.index("=== SNIPPER SUMMARY END ===")

    q1_section = paras[q1_idx:o1_idx]
    o1_section = paras[o1_idx:end_idx]

    assert any('"Data at rest uses AES-256."' in p for p in q1_section)
    assert not any("Access requires MFA." in p for p in q1_section)
    assert any('"Access requires MFA."' in p for p in o1_section)
    assert not any("Data at rest uses AES-256." in p for p in o1_section)


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as td:
        tpath = Path(td)
        test_document_mutator_end_to_end(tpath)
        test_mutator_renders_keywords_and_concepts_in_summary(tpath)
        test_mutator_cross_paragraph_snippet(tpath)
        test_idempotent_remutation(tpath)
        test_document_mutator_stream_in_memory()
    print("Mutation tests passed!")

