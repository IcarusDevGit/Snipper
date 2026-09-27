#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "python-docx>=1.1.0",
#     "spacy>=3.7.0",
# ]
# ///
"""Command line interface for Snipper."""

import argparse
from pathlib import Path
import shutil
import sys
from typing import Optional

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from config import SnipperConfig, resolve_constraints_path
from document import DocumentParser
from findings import FindingsData
from highlighter import DocumentHighlighter
from mutation import DocumentMutator
from nlp import LexicalMatcher


def conserve_document_backup(file_path: Path) -> Path:
    """Conserves an intact copy of the input document prior to in-place mutation."""
    backup_path = file_path.with_name(f"{file_path.stem}.backup{file_path.suffix}")
    try:
        shutil.copy2(file_path, backup_path)
        print(f"[+] Conserved backup duplicate of input document at: {backup_path}")
    except Exception as e:
        print(f"[!] Warning: Could not create backup file: {e}", file=sys.stderr)
    return backup_path

def resolve_findings_path(
    findings_path: Optional[Path | str],
    document_path: Path,
) -> Optional[Path]:
    """Resolves findings JSON path from explicit argument or standard findings/ locations."""
    if findings_path:
        return Path(findings_path)

    doc_stem = document_path.stem
    script_dir = Path(__file__).resolve().parent
    skill_root = script_dir.parent
    clean_stem = doc_stem.lower().replace(" ", "_")

    candidates = [
        skill_root / "findings" / f"{doc_stem}.json",
        skill_root / "findings" / f"{clean_stem}.json",
        skill_root / "findings" / f"findings_{doc_stem}.json",
        skill_root / "findings" / f"findings_{clean_stem}.json",
        Path("findings") / f"{doc_stem}.json",
        Path("findings") / f"{clean_stem}.json",
        document_path.parent / "findings" / f"{doc_stem}.json",
        document_path.parent / "findings" / f"{clean_stem}.json",
    ]

    for c in candidates:
        if c.exists():
            return c

    return None


def run_pipeline(
    file_path: Path,
    lexical_only: bool = False,
    findings_path: Optional[Path] = None,
    config_path: Optional[Path] = None,
    output_path: Optional[Path] = None,
    dry_run: bool = False,
) -> int:
    """Executes the Snipper processing pipeline."""
    # 1. Load configuration
    cfg_file = resolve_constraints_path(config_path, file_path)
    config = SnipperConfig.from_file(cfg_file, file_path)
    if cfg_file:
        print(f"[+] Loaded configuration from: {cfg_file}")
        print(f"[+] Active palette ({config.palette_mode}, {config.palette_order}): {len(config.palette)} colors ({config.palette[0]} ... {config.palette[-1]})")
    else:
        print(f"[*] No CustomConstraints.md found; using {len(config.palette)}-color palette.")

    # 2. Ingest document
    print(f"[*] Ingesting document: {file_path}")
    parser = DocumentParser(config)
    try:
        parsed = parser.parse(file_path)
    except Exception as e:
        print(f"[!] Error parsing document: {e}", file=sys.stderr)
        return 1

    print(f"[+] Loaded {len(parsed.questions)} question(s) and {len(parsed.body_paragraphs)} body paragraph(s).")

    # 3. Deterministic NLP Lexical Matching (Phase 1 - Highlighter)
    matcher = LexicalMatcher(config)
    matcher.initialize_language(parsed.body_text)
    print(f"[+] Language resolved: {matcher.resolved_lang}")

    question_lemmas = matcher.extract_question_lemmas(parsed.questions)
    q_map = {q.id: q for q in parsed.questions}
    matches = matcher.scan_body(parsed.body_paragraphs, question_lemmas, q_map)
    print(f"[+] Found {len(matches)} lexical match token(s).")

    target = output_path or file_path

    # Preview-only mode: do not write or alter any files
    if dry_run:
        print("[*] DRY-RUN active: no files will be written or modified.")
        if target == file_path:
            print(f"[*] DRY-RUN: Backup would be created at {file_path.with_name(f'{file_path.stem}.backup{file_path.suffix}')}")
        if lexical_only:
            print(f"[*] DRY-RUN: Standalone Highlighter would highlight {len(matches)} match(es) in {target}.")
            return 0
        if findings_path:
            if not findings_path.exists():
                print(f"[!] Error: Findings file '{findings_path}' not found.", file=sys.stderr)
                return 1
            try:
                findings_data = FindingsData.from_file(findings_path)
            except Exception as e:
                print(f"[!] Error loading findings JSON: {e}", file=sys.stderr)
                return 1
            print(f"[+] DRY-RUN: Findings validated successfully ({len(findings_data.findings)} finding(s), {len(findings_data.unanswered_questions)} unanswered question(s)).")
            print(f"[*] DRY-RUN: DocumentMutator would apply findings and {len(matches)} match(es) to {target}.")
            return 0
        print(f"[*] DRY-RUN: Highlighter would highlight {len(matches)} match(es) in {target}.")
        return 0

    # Duplicate input document before in-place mutation to conserve backup
    if target == file_path:
        conserve_document_backup(file_path)

    # Standalone Lexical Matching (Highlighter): apply match highlights directly and exit
    if lexical_only:
        highlighter = DocumentHighlighter(config)
        highlighter.highlight_matches(parsed.body_paragraphs, matches)
        try:
            parsed.doc.save(str(target))
        except PermissionError:
            print(f"[!] Error: Permission denied when saving to '{target}'.", file=sys.stderr)
            print("[!] Please close the document in Microsoft Word (or other applications) and try again.", file=sys.stderr)
            return 2
        print(f"[OK] Document saved in-place to: {target}")
        print("[*] Standalone Highlighter matching completed. Exiting without agent invocation.")
        return 0

    # Phase 3 Document Mutation (if findings provided)
    if findings_path:
        if not findings_path.exists():
            print(f"[!] Error: Findings file '{findings_path}' not found.", file=sys.stderr)
            return 1

        print(f"[*] Loading findings from: {findings_path}")
        try:
            findings_data = FindingsData.from_file(findings_path)
        except Exception as e:
            print(f"[!] Error loading findings JSON: {e}", file=sys.stderr)
            return 1

        mutator = DocumentMutator(config)
        try:
            mutator.mutate(
                parsed=parsed,
                matches=matches,
                findings_data=findings_data,
                output_path=target,
            )
        except PermissionError:
            print(f"[!] Error: Permission denied when saving to '{target}'.", file=sys.stderr)
            print("[!] Please close the document in Microsoft Word (or other applications) and try again.", file=sys.stderr)
            return 2
        print(f"[OK] Document mutated in-place with findings and saved to: {target}")
        return 0

    # Otherwise: Phase 1 pass
    highlighter = DocumentHighlighter(config)
    highlighter.highlight_matches(parsed.body_paragraphs, matches)
    try:
        parsed.doc.save(str(target))
    except PermissionError:
        print(f"[!] Error: Permission denied when saving to '{target}'.", file=sys.stderr)
        print("[!] Please close the document in Microsoft Word (or other applications) and try again.", file=sys.stderr)
        return 2
    print(f"[OK] Document saved in-place to: {target}")
    print("[*] Phase 1 Highlighter complete. Provide --findings <path.json> to apply Phase 3 mutation.")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="snipper",
        description="Snipper - Verbatim Answer Snippet Discovery and Document Highlighter",
        epilog="""Exit codes:
  0  Success (including clean dry-run execution)
  1  General error (parse failure, invalid arguments, schema validation error)
  2  Permission error (file is locked, e.g. open in Microsoft Word)
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # 'highlight' subcommand (Primary Phase 1 Highlighter interface)
    highlight_parser = subparsers.add_parser("highlight", help="Execute standalone Phase 1 Highlighter (deterministic, zero-agent)")
    highlight_parser.add_argument("document", type=str, help="Path to input .docx document")
    highlight_parser.add_argument("--config", type=str, default=None, help="Path to CustomConstraints.md")
    highlight_parser.add_argument("--output", type=str, default=None, help="Optional output path (defaults to in-place overwrite)")
    highlight_parser.add_argument("--dry-run", action="store_true", help="Simulate execution without modifying files or saving")

    # 'match' subcommand (backward-compatible alias for highlight)
    match_parser = subparsers.add_parser("match", help="Execute standalone lexical match only (alias for highlight)")
    match_parser.add_argument("document", type=str, help="Path to input .docx document")
    match_parser.add_argument("--config", type=str, default=None, help="Path to CustomConstraints.md")
    match_parser.add_argument("--output", type=str, default=None, help="Optional output path (defaults to in-place overwrite)")
    match_parser.add_argument("--dry-run", action="store_true", help="Simulate execution without modifying files or saving")

    # 'run' subcommand
    run_parser = subparsers.add_parser("run", help="Run Snipper pipeline")
    run_parser.add_argument("document", type=str, help="Path to input .docx document")
    run_parser.add_argument("--lexical-only", action="store_true", help="Execute deterministic Phase 1 Highlighter matching only")
    run_parser.add_argument("--findings", type=str, default=None, help="Path to findings.json file to apply")
    run_parser.add_argument("--config", type=str, default=None, help="Path to CustomConstraints.md")
    run_parser.add_argument("--output", type=str, default=None, help="Optional output path (defaults to in-place overwrite)")
    run_parser.add_argument("--dry-run", action="store_true", help="Simulate execution without modifying files or saving")

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    doc_path = Path(args.document)
    if not doc_path.exists():
        print(f"[!] Error: File '{doc_path}' not found.", file=sys.stderr)
        return 1

    cfg_path = Path(args.config) if args.config else None
    out_path = Path(args.output) if args.output else None
    raw_findings = getattr(args, "findings", None)
    findings_path = resolve_findings_path(raw_findings, doc_path)
    if findings_path and not raw_findings:
        print(f"[+] Auto-detected findings file: {findings_path}")
    lex_only = (args.command in ("match", "highlight")) or getattr(args, "lexical_only", False)
    dry_run = getattr(args, "dry_run", False)

    return run_pipeline(
        file_path=doc_path,
        lexical_only=lex_only,
        findings_path=findings_path,
        config_path=cfg_path,
        output_path=out_path,
        dry_run=dry_run,
    )


if __name__ == "__main__":
    sys.exit(main())

