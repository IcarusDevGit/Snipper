import sys
from pathlib import Path
import docx

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from config import SnipperConfig
from document import DocumentParser, export_to_txt, format_as_txt


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


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        tpath = Path(td)
        test_parse_standard_document(tpath)
        test_parse_resilient_delimiters(tpath)
        test_parse_sub_bullet_keywords_and_concepts(tpath)
        test_export_to_txt(tpath)
        test_verbatim_character_fidelity(tpath)
    print("Document parser tests passed!")
