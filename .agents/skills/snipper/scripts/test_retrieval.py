import sys
from pathlib import Path
import tempfile

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from retrieval import (
    CandidateSnippet,
    extract_paragraph_coordinates,
    format_lookup_results,
    format_snippet_card,
    lookup_snippets,
    score_candidate,
)


def setup_library_with_findings(root: Path):
    """Creates a library with sub-modules, companion text, and findings files."""
    mod = root / "Security"
    sub1 = mod / "IAM"
    sub1.mkdir(parents=True)

    (sub1 / "access.docx").write_text("doc dummy", encoding="utf-8")
    (sub1 / "access.txt").write_text(
        "[P0] Access control is enforced via pg_hba configuration.\n"
        "[P1] Database authentication requires TLS 1.3 certificates.\n",
        encoding="utf-8",
    )
    (sub1 / "access.findings.json").write_text(
        """{
            "findings": [
                {
                    "target_ids": ["Q1"],
                    "snippet_text": "Access control is enforced via pg_hba configuration.",
                    "keywords": ["access control", "pg_hba"]
                },
                {
                    "target_ids": ["O1"],
                    "snippet_text": "Database authentication requires TLS 1.3 certificates.",
                    "keywords": ["authentication", "TLS", "certificates"]
                }
            ],
            "unanswered_targets": []
        }""",
        encoding="utf-8",
    )

    sub2 = mod / "Audit"
    sub2.mkdir(parents=True)
    (sub2 / "audit.docx").write_text("doc dummy", encoding="utf-8")
    (sub2 / "audit.txt").write_text(
        "[P0] Audit logs must be forwarded to a centralized SIEM system.\n",
        encoding="utf-8",
    )
    (sub2 / "audit.findings.json").write_text(
        """{
            "findings": [
                {
                    "target_ids": ["O2"],
                    "snippet_text": "Audit logs must be forwarded to a centralized SIEM system.",
                    "keywords": ["audit", "SIEM"]
                }
            ],
            "unanswered_targets": []
        }""",
        encoding="utf-8",
    )


def test_extract_paragraph_coordinates():
    body = (
        "[P0] Introduction to cryptography.\n"
        "[P1] AES-256 is used for disk encryption.\n"
        "[P2] TLS is enforced for all in-transit traffic.\n"
    )
    assert extract_paragraph_coordinates(body, "AES-256 is used for disk encryption.") == "P1"
    assert extract_paragraph_coordinates(body, "TLS is enforced") == "P2"
    assert extract_paragraph_coordinates(body, "Not present in text") == ""


def test_score_candidate():
    c = CandidateSnippet(
        source_findings_path=Path("f.json"),
        source_doc_path=Path("doc.docx"),
        target_id="Q1",
        snippet_text="Encryption keys are rotated annually using HSM.",
        paragraph_coord="P2",
        keywords=["encryption", "HSM"],
    )
    # Keyword match + text match
    score = score_candidate(c, "encryption HSM")
    assert score > 10.0

    # Unrelated query
    zero_score = score_candidate(c, "payroll invoice")
    assert zero_score == 0.0


def test_lookup_with_limit_prioritization(tmp_path: Path):
    setup_library_with_findings(tmp_path)

    # Search for "TLS certificates" with limit 1
    results, scope_res = lookup_snippets(
        query="TLS certificates",
        target_path=tmp_path / "Security",
        scope="local",
        limit=1,
        library_root=tmp_path,
    )

    assert len(results) == 1
    assert results[0].target_id == "O1"
    assert "TLS 1.3" in results[0].snippet_text
    assert results[0].paragraph_coord == "P1"
    assert results[0].score > 0.0


def test_lookup_without_limit_evaluates_all(tmp_path: Path):
    setup_library_with_findings(tmp_path)

    # Search without limit returns all 3 candidates across Security module
    results, scope_res = lookup_snippets(
        query="anything",
        target_path=tmp_path / "Security",
        scope="local",
        limit=None,
        library_root=tmp_path,
    )

    assert len(results) == 3


def test_format_lookup_results():
    candidates = [
        CandidateSnippet(
            source_findings_path=Path("Security/access.findings.json"),
            source_doc_path=Path("Security/access.docx"),
            target_id="O1",
            snippet_text="Database authentication requires TLS 1.3 certificates.",
            paragraph_coord="P1",
            keywords=["authentication", "TLS"],
        )
    ]

    output = format_lookup_results(candidates, scope_type="hierarchical", limit=5)
    assert "[Found 1 relevant snippets (Scope: hierarchical, Limit: 5)]" in output
    assert "Security/access.docx :: P1" in output or "Security\\access.docx :: P1" in output
    assert "(Matched for O1)" in output
    assert '"Database authentication requires TLS 1.3 certificates."' in output
    assert "Keywords: authentication, TLS" in output


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as td:
        tpath = Path(td)
        test_extract_paragraph_coordinates()
        test_score_candidate()
        test_lookup_with_limit_prioritization(tpath)
        test_lookup_without_limit_evaluates_all(tpath)
        test_format_lookup_results()
    print("Retrieval tests passed!")
