import io
from pathlib import Path
import sys
import docx

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from config import SnipperConfig
from document import DocumentParser, QuestionsParser, export_to_txt, format_as_txt


def test_questions_parser_mixed_targets(tmp_path: Path):
    q_file = tmp_path / "sample.questions.txt"
    q_file.write_text(
        "Q1: What are the encryption requirements?\n"
        "  - Keywords: AES, encryption, at-rest\n"
        "  - Concepts: Cryptographic Storage (web: true)\n"
        "O1: Audit all external network connections.\n"
        "  - Keywords: outbound, firewall, TLS\n"
        "  - Concepts: Network Egress\n"
        "Q2: How often are keys rotated?\n",
        encoding="utf-8",
    )

    qp = QuestionsParser(SnipperConfig(palette=["#111111", "#222222", "#333333"]))
    questions = qp.parse_file(q_file)

    assert len(questions) == 3

    assert questions[0].target_id == "Q1"
    assert questions[0].target_type == "Q"
    assert questions[0].text == "What are the encryption requirements?"
    assert questions[0].keywords == ["AES", "encryption", "at-rest"]
    assert len(questions[0].concepts) == 1
    assert questions[0].concepts[0].name == "Cryptographic Storage"
    assert questions[0].concepts[0].web_search is True
    assert questions[0].color == "#111111"

    assert questions[1].target_id == "O1"
    assert questions[1].target_type == "O"
    assert questions[1].text == "Audit all external network connections."
    assert questions[1].keywords == ["outbound", "firewall", "TLS"]
    assert questions[1].concepts[0].name == "Network Egress"
    assert questions[1].concepts[0].web_search is False
    assert questions[1].color == "#222222"

    assert questions[2].target_id == "Q2"
    assert questions[2].target_type == "Q"
    assert questions[2].text == "How often are keys rotated?"
    assert questions[2].color == "#333333"


def test_parse_decoupled_document(tmp_path: Path):
    doc_path = tmp_path / "report.docx"
    q_path = tmp_path / "report.questions.txt"

    q_path.write_text(
        "Q1: What is the failover strategy?\n"
        "  - Keywords: multi-region\n",
        encoding="utf-8",
    )

    doc = docx.Document()
    doc.add_paragraph("This is the first paragraph of clean document content.")
    doc.add_paragraph("The system implements active-passive multi-region failover.")
    doc.save(doc_path)

    parser = DocumentParser()
    parsed = parser.parse(doc_path)

    # All paragraphs in clean docx become body_paragraphs
    assert len(parsed.body_paragraphs) == 2
    assert "active-passive" in parsed.body_text
    assert len(parsed.questions) == 1
    assert parsed.questions[0].target_id == "Q1"
    assert parsed.questions_header_idx == -1

    # Export to txt generates report.txt with clean [P#]
    out_txt = export_to_txt(parsed)
    assert out_txt == tmp_path / "report.txt"
    assert out_txt.exists()
    content = out_txt.read_text(encoding="utf-8")
    assert "[P0] This is the first paragraph of clean document content." in content
    assert "[P1] The system implements active-passive multi-region failover." in content
    assert "=== QUESTIONS ===" not in content





def test_parse_standard_document(tmp_path: Path):
    doc_path = tmp_path / "test_doc.docx"
    doc = docx.Document()
    
    # Title
    doc.add_paragraph("Snipper Analysis Document")
    
    # Questions section
    doc.add_paragraph("Questions")
    doc.add_paragraph("1. Who founded ACME Corp?")
    doc.add_paragraph("2. When was the headquarters built?")
    
    # Body section
    doc.add_paragraph("Body")
    doc.add_paragraph("In 1984, John Doe founded ACME Corp.")
    doc.add_paragraph("The headquarters was completed in 1990 in Boston.")
    
    doc.save(doc_path)
    
    cfg = SnipperConfig(palette=["#111111", "#222222"])
    parser = DocumentParser(cfg)
    parsed = parser.parse(doc_path)
    
    assert len(parsed.questions) == 2
    assert parsed.questions[0].id == 1
    assert parsed.questions[0].text == "Who founded ACME Corp?"
    assert parsed.questions[0].color == "#111111"
    assert parsed.questions[1].id == 2
    assert parsed.questions[1].text == "When was the headquarters built?"
    assert parsed.questions[1].color == "#222222"
    
    assert len(parsed.body_paragraphs) == 2
    assert "John Doe" in parsed.body_text


def test_parse_resilient_delimiters(tmp_path: Path):
    doc_path = tmp_path / "resilient_doc.docx"
    doc = docx.Document()
    
    # Delimiters with colons and varied casing
    doc.add_paragraph("  **PERGUNTAS**:  ")
    doc.add_paragraph("- Onde fica a sede?")
    
    doc.add_paragraph("## CORPO ")
    doc.add_paragraph("A sede fica em Sao Paulo.")
    
    doc.save(doc_path)
    
    cfg = SnipperConfig(palette=["#FFFF00"])
    parser = DocumentParser(cfg)
    parsed = parser.parse(doc_path)
    
    assert len(parsed.questions) == 1
    assert parsed.questions[0].text == "Onde fica a sede?"
    assert "Sao Paulo" in parsed.body_text


def test_parse_sub_bullet_keywords_and_concepts(tmp_path: Path):
    doc_path = tmp_path / "subbullets_doc.docx"
    doc = docx.Document()
    
    doc.add_paragraph("Questions")
    doc.add_paragraph("1. What are the disaster recovery requirements?")
    doc.add_paragraph("   - Keywords: RPO, RTO; backup")
    doc.add_paragraph("   - Concepts: Immutable storage (web: true), Snapshot policy")
    doc.add_paragraph("2. Como é feita a auditoria de acesso?")
    doc.add_paragraph("   - Palavras-chave: auditoria")
    doc.add_paragraph("   - Conceitos: Controle de acesso (web)")
    doc.add_paragraph("3. What is the stock symbol?")
    
    doc.add_paragraph("Body")
    doc.add_paragraph("The company maintains RPO under 15 minutes.")
    
    doc.save(doc_path)
    
    parser = DocumentParser()
    parsed = parser.parse(doc_path)
    
    assert len(parsed.questions) == 3
    
    q1 = parsed.questions[0]
    assert q1.text == "What are the disaster recovery requirements?"
    assert q1.keywords == ["RPO", "RTO", "backup"]
    assert len(q1.concepts) == 2
    assert q1.concepts[0].name == "Immutable storage"
    assert q1.concepts[0].web_search is True
    assert q1.concepts[1].name == "Snapshot policy"
    assert q1.concepts[1].web_search is False
    
    q2 = parsed.questions[1]
    assert q2.text == "Como é feita a auditoria de acesso?"
    assert q2.keywords == ["auditoria"]
    assert len(q2.concepts) == 1
    assert q2.concepts[0].name == "Controle de acesso"
    assert q2.concepts[0].web_search is True
    
    q3 = parsed.questions[2]
    assert q3.text == "What is the stock symbol?"
    assert q3.keywords == []
    assert q3.concepts == []


def test_export_to_txt(tmp_path: Path):
    doc_path = tmp_path / "export_doc.docx"
    doc = docx.Document()
    doc.add_paragraph("Questions")
    doc.add_paragraph("1. What is the disaster recovery plan?")
    doc.add_paragraph("   - Keywords: RPO, RTO")
    doc.add_paragraph("   - Concepts: Immutable snapshot (web: true)")
    doc.add_paragraph("2. Who approves production deployments?")
    doc.add_paragraph("Body")
    doc.add_paragraph("Production releases require dual sign-off.")
    doc.add_paragraph("The target RPO is 15 minutes.")
    doc.save(doc_path)

    parser = DocumentParser()
    parsed = parser.parse(doc_path)

    # 1. Test format_as_txt and annotated_text property
    text_content = parsed.annotated_text
    assert "=== QUESTIONS ===" in text_content
    assert "1. What is the disaster recovery plan?" in text_content
    assert "   - Keywords: RPO, RTO" in text_content
    assert "   - Concepts: Immutable snapshot (web: true)" in text_content
    assert "2. Who approves production deployments?" in text_content
    assert "=== BODY ===" in text_content
    assert "[P0] Production releases require dual sign-off." in text_content
    assert "[P1] The target RPO is 15 minutes." in text_content

    # 2. Test export_to_txt with default filename
    exported_path = export_to_txt(parsed)
    assert exported_path == tmp_path / "export_doc.snipper.txt"
    assert exported_path.exists()
    assert exported_path.read_text(encoding="utf-8") == text_content

    # 3. Test export_txt with explicit output path
    custom_path = tmp_path / "custom_output.txt"
    res = parsed.export_txt(custom_path)
    assert res == custom_path
    assert custom_path.exists()
    assert custom_path.read_text(encoding="utf-8") == text_content


def test_verbatim_character_fidelity(tmp_path: Path):
    doc_path = tmp_path / "fidelity_doc.docx"
    doc = docx.Document()
    doc.add_paragraph("Questions")
    doc.add_paragraph("1. How are symbols handled?")
    doc.add_paragraph("Body")
    tricky_sentence = 'Text with *asterisks*, **bold markers**, #hashtags, [brackets], "smart quotes" and _underscores_.'
    doc.add_paragraph(tricky_sentence)
    doc.save(doc_path)

    parser = DocumentParser()
    parsed = parser.parse(doc_path)
    exported_path = export_to_txt(parsed)
    content = exported_path.read_text(encoding="utf-8")

    # Verify tricky characters are not converted, escaped, or stripped
    assert f"[P0] {tricky_sentence}" in content


def test_parse_from_in_memory_stream():
    import io
    doc = docx.Document()
    doc.add_paragraph("Paragraph zero text.")
    doc.add_paragraph("Paragraph one text.")
    stream = io.BytesIO()
    doc.save(stream)
    stream.seek(0)

    parser = DocumentParser()
    parsed = parser.parse(
        stream,
        questions_text="Q1: What is in paragraph zero?\n  - Keywords: zero\n",
        virtual_path="virtual_doc.docx",
    )

    assert len(parsed.body_paragraphs) == 2
    assert parsed.body_paragraphs[0][1].text == "Paragraph zero text."
    assert len(parsed.questions) == 1
    assert parsed.questions[0].target_id == "Q1"
    assert parsed.questions[0].text == "What is in paragraph zero?"
    assert parsed.file_path == Path("virtual_doc.docx")


def test_export_txt_with_storage_provider():
    import io
    from storage import LocalStorageProvider

    doc = docx.Document()
    doc.add_paragraph("Body line.")
    stream = io.BytesIO()
    doc.save(stream)
    stream.seek(0)

    parser = DocumentParser()
    parsed = parser.parse(stream, virtual_path="module/entry.docx")

    mock_storage = LocalStorageProvider()
    mock_storage.write_text = lambda target_dir, filename, text: f"uploaded://{target_dir}/{filename}"

    result = parsed.export_txt(storage_provider=mock_storage)
    assert result == "uploaded://module/entry.txt"


def test_parse_plain_text_stream_gdoc():
    """Verifies that an in-memory plain text stream (from Drive files().export) is parsed cleanly."""
    raw_text = "First paragraph from Google Doc.\nSecond paragraph discussing encryption and access controls.\n"
    stream = io.BytesIO(raw_text.encode("utf-8"))

    parser = DocumentParser()
    parsed = parser.parse(
        stream,
        questions_text="Q1: What controls access?\n  - Keywords: access, encryption\n",
        virtual_path="Module1/Lesson.gdoc",
    )

    assert len(parsed.body_paragraphs) == 2
    assert parsed.body_paragraphs[0][1].text == "First paragraph from Google Doc."
    assert parsed.body_paragraphs[1][1].text == "Second paragraph discussing encryption and access controls."
    assert len(parsed.questions) == 1
    assert parsed.questions[0].target_id == "Q1"
    assert parsed.questions[0].keywords == ["access", "encryption"]
    assert "encryption" in parsed.body_text


def test_parse_decoupled_questions_gdoc_extension(tmp_path: Path):
    """Verifies discovery of <stem>.questions and <stem>.questions.gdoc companion files."""
    doc_path = tmp_path / "notes.docx"
    doc = docx.Document()
    doc.add_paragraph("Content line.")
    doc.save(doc_path)

    q_gdoc = tmp_path / "notes.questions"
    q_gdoc.write_text("Q1: Question from .questions file?\n", encoding="utf-8")

    parser = DocumentParser()
    parsed = parser.parse(doc_path)
    assert len(parsed.questions) == 1
    assert parsed.questions[0].text == "Question from .questions file?"


def test_export_txt_bypasses_write_when_gdoc():
    """Verifies that export_to_txt does NOT write any files when storage_backend == 'gdoc'."""
    from storage import LocalStorageProvider

    doc = docx.Document()
    doc.add_paragraph("Body paragraph.")
    stream = io.BytesIO()
    doc.save(stream)
    stream.seek(0)

    parser = DocumentParser()
    parsed = parser.parse(stream, virtual_path="module/entry.gdoc")

    storage = LocalStorageProvider()
    storage.backend = "gdoc"
    storage.storage_backend = "gdoc"
    write_called = False

    def fake_write(target_dir, filename, text):
        nonlocal write_called
        write_called = True
        return f"{target_dir}/{filename}"

    storage.write_text = fake_write

    cfg = SnipperConfig(storage_backend="gdoc")
    res = parsed.export_txt(storage_provider=storage, config=cfg)

    assert write_called is False
    assert res == "entry.txt"


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        tpath = Path(td)
        test_parse_standard_document(tpath)
        test_parse_resilient_delimiters(tpath)
        test_parse_sub_bullet_keywords_and_concepts(tpath)
        test_export_to_txt(tpath)
        test_verbatim_character_fidelity(tpath)
        test_parse_from_in_memory_stream()
        test_export_txt_with_storage_provider()
    print("Document parser tests passed!")

