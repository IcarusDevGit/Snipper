"""CLI entry point for Snipper: snip, hlt, lookup, dump, and legacy pipeline modes."""

import argparse
from pathlib import Path
import shutil
import sys
from typing import Optional

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from config import SnipperConfig, resolve_constraints_path
from document import DocumentParser, QuestionsParser, export_to_txt
from findings import FindingsData
from highlighter import DocumentHighlighter
from mutation import DocumentMutator
from nlp import LexicalMatcher
from retrieval import format_lookup_results, lookup_snippets


def resolve_findings_path(
    findings_path: Optional[Path | str],
    document_path: Path,
) -> Optional[Path]:
    """Resolves findings JSON path from explicit argument, sub-module convention, or findings/ directory."""
    if findings_path:
        return Path(findings_path)

    doc_stem = document_path.stem
    parent_dir = document_path.parent
    clean_stem = doc_stem.lower().replace(" ", "_")

    candidates = [
        parent_dir / f"{doc_stem}.findings.json",
        parent_dir / f"{clean_stem}.findings.json",
        parent_dir / f"{doc_stem}.json",
        parent_dir / f"{clean_stem}.json",
        parent_dir / "findings" / f"{doc_stem}.json",
        Path("findings") / f"{doc_stem}.json",
        Path("findings") / f"{clean_stem}.json",
    ]

    for c in candidates:
        if c.exists():
            return c

    return None


def resolve_questions_path(
    questions_path: Optional[Path | str],
    document_path: Path,
) -> Optional[Path]:
    """Resolves questions file path from explicit argument or sub-module convention (<name>.questions.txt)."""
    if questions_path:
        return Path(questions_path)

    doc_stem = document_path.stem
    parent_dir = document_path.parent

    candidates = [
        parent_dir / f"{doc_stem}.questions.txt",
        parent_dir / "questions.txt",
    ]

    for c in candidates:
        if c.exists():
            return c

    return None


def run_pipeline(
    file_path: Path,
    lexical_only: bool = False,
    findings_path: Optional[Path] = None,
    questions_path: Optional[Path] = None,
    config_path: Optional[Path] = None,
    output_path: Optional[Path] = None,
    dry_run: bool = False,
) -> int:
    """Executes the Snipper processing pipeline."""
    cfg_file = resolve_constraints_path(config_path, file_path)
    config = SnipperConfig.from_file(cfg_file, file_path)
    if cfg_file:
        print(f"[+] Loaded configuration from: {cfg_file}")
    else:
        print(f"[*] No CustomConstraints.md found; using {len(config.palette)}-color palette.")

    print(f"[*] Ingesting document: {file_path}")
    parser = DocumentParser(config)
    try:
        parsed = parser.parse(file_path, questions_file=questions_path)
    except Exception as e:
        print(f"[!] Error parsing document: {e}", file=sys.stderr)
        return 1

    print(f"[+] Loaded {len(parsed.questions)} target(s) and {len(parsed.body_paragraphs)} body paragraph(s).")

    # Auto-synchronize lightweight text companion (<name>.txt)
    if not dry_run:
        try:
            txt_path = export_to_txt(parsed)
            print(f"[+] Synchronized text copy to: {txt_path}")
        except Exception as e:
            print(f"[*] Warning: Could not export text copy: {e}", file=sys.stderr)

    matcher = LexicalMatcher(config)
    matcher.initialize_language(parsed.body_text)
    print(f"[+] Language resolved: {matcher.resolved_lang}")

    question_lemmas = matcher.extract_question_lemmas(parsed.questions)
    q_map = {q.id: q for q in parsed.questions}
    matches = matcher.scan_body(parsed.body_paragraphs, question_lemmas, q_map)
    print(f"[+] Found {len(matches)} lexical match token(s).")

    target = output_path or file_path

    if dry_run:
        print("[*] DRY-RUN active: no files will be written or modified.")
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
            print(f"[+] DRY-RUN: Findings validated successfully ({len(findings_data.findings)} finding(s)).")
            print(f"[*] DRY-RUN: DocumentMutator would apply findings to {target}.")
            return 0
        print(f"[*] DRY-RUN: Highlighter would highlight {len(matches)} match(es) in {target}.")
        return 0

    if lexical_only:
        highlighter = DocumentHighlighter(config)
        highlighter.highlight_matches(parsed.body_paragraphs, matches)
        try:
            parsed.doc.save(str(target))
        except PermissionError:
            print(f"[!] Error: Permission denied when saving to '{target}'.", file=sys.stderr)
            print("[!] Please close the document in Microsoft Word and try again.", file=sys.stderr)
            return 2
        print(f"[OK] Document saved in-place to: {target}")
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

        mutator = DocumentMutator(config)
        try:
            mutator.mutate(parsed, matches, findings_data, output_path=target)
        except PermissionError:
            print(f"[!] Error: Permission denied when saving to '{target}'.", file=sys.stderr)
            print("[!] Please close the document in Microsoft Word and try again.", file=sys.stderr)
            return 2

        print(f"[OK] Full pipeline complete. Mutated document saved in-place to: {target}")
        return 0

    highlighter = DocumentHighlighter(config)
    highlighter.highlight_matches(parsed.body_paragraphs, matches)
    try:
        parsed.doc.save(str(target))
    except PermissionError:
        print(f"[!] Error: Permission denied when saving to '{target}'.", file=sys.stderr)
        print("[!] Please close the document in Microsoft Word and try again.", file=sys.stderr)
        return 2
    print(f"[OK] Document saved in-place to: {target}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="snipper",
        description="Snipper v0.4 - Semantic Answer Discovery and Document Highlighter",
        epilog="""Exit codes:
  0  Success
  1  General error
  2  Permission error (file is locked)
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # /snipper:snip
    snip_parser = subparsers.add_parser("snip", help="Ingest document and sync text copy for snipping")
    snip_parser.add_argument("document", nargs="?", default=None, help="Path to input .docx or .txt document")
    snip_parser.add_argument("--dir", type=str, default=None, help="Path to input .docx or .txt document")
    snip_parser.add_argument("--q", type=str, default=None, help="Path to questions file (defaults to <name>.questions.txt)")
    snip_parser.add_argument("--output", type=str, default=None, help="Optional output path")

    # /snipper:hlt / highlight
    hlt_parser = subparsers.add_parser("hlt", help="Mutate .docx document with findings and highlights")
    hlt_parser.add_argument("document", nargs="?", default=None, help="Path to input .docx document")
    hlt_parser.add_argument("--docs", type=str, default=None, help="Path to input .docx document")
    hlt_parser.add_argument("--f", "--findings", dest="findings", type=str, default=None, help="Path to findings file (defaults to <name>.findings.json)")
    hlt_parser.add_argument("--config", type=str, default=None, help="Path to CustomConstraints.md")
    hlt_parser.add_argument("--output", type=str, default=None, help="Optional output path")
    hlt_parser.add_argument("--dry-run", action="store_true", help="Simulate execution without modifying files")

    # highlight (alias)
    highlight_parser = subparsers.add_parser("highlight", help="Execute standalone Phase 1 Highlighter")
    highlight_parser.add_argument("document", type=str, help="Path to input .docx document")
    highlight_parser.add_argument("--config", type=str, default=None, help="Path to CustomConstraints.md")
    highlight_parser.add_argument("--output", type=str, default=None, help="Optional output path")
    highlight_parser.add_argument("--dry-run", action="store_true", help="Simulate execution without modifying files")

    # match (alias)
    match_parser = subparsers.add_parser("match", help="Execute standalone lexical match only")
    match_parser.add_argument("document", type=str, help="Path to input .docx document")
    match_parser.add_argument("--config", type=str, default=None, help="Path to CustomConstraints.md")
    match_parser.add_argument("--output", type=str, default=None, help="Optional output path")
    match_parser.add_argument("--dry-run", action="store_true", help="Simulate execution without modifying files")

    # /snipper:lookup
    lookup_parser = subparsers.add_parser("lookup", help="Search snippets across existing findings files within scope")
    lookup_parser.add_argument("--q", type=str, default=None, help="Question query string")
    lookup_parser.add_argument("--o", type=str, default=None, help="Objective query string")
    lookup_parser.add_argument("--dir", type=str, default=None, help="Target file or directory path")
    lookup_parser.add_argument("--scope", type=str, default=None, choices=["local", "hierarchical", "global"], help="Scope mode")
    lookup_parser.add_argument("--limit", type=int, default=None, help="Maximum number of snippets to return")

    # run (legacy full pipeline)
    run_parser = subparsers.add_parser("run", help="Run full Snipper pipeline")
    run_parser.add_argument("document", type=str, help="Path to input .docx document")
    run_parser.add_argument("--lexical-only", action="store_true", help="Execute deterministic lexical matching only")
    run_parser.add_argument("--findings", type=str, default=None, help="Path to findings file")
    run_parser.add_argument("--q", type=str, default=None, help="Path to questions file")
    run_parser.add_argument("--config", type=str, default=None, help="Path to CustomConstraints.md")
    run_parser.add_argument("--output", type=str, default=None, help="Optional output path")
    run_parser.add_argument("--dry-run", action="store_true", help="Simulate execution without modifying files")

    # dump
    dump_parser = subparsers.add_parser("dump", help="Export plain-text copy of document with paragraph coordinates")
    dump_parser.add_argument("document", type=str, help="Path to input .docx document")
    dump_parser.add_argument("--output", type=str, default=None, help="Optional output path")

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    # Handle 'lookup' subcommand
    if args.command == "lookup":
        query = args.q or args.o
        if not query:
            print("[!] Error: Either --q or --o query string must be provided.", file=sys.stderr)
            return 1
        candidates, scope_res = lookup_snippets(
            query=query,
            target_path=args.dir,
            scope=args.scope,
            limit=args.limit,
        )
        print(format_lookup_results(candidates, scope_res.scope_type, limit=args.limit))
        return 0

    # Resolve document path across different subcommands
    raw_doc = getattr(args, "document", None) or getattr(args, "docs", None) or getattr(args, "dir", None)
    if not raw_doc:
        print("[!] Error: Document path is required.", file=sys.stderr)
        return 1

    doc_path = Path(raw_doc)
    if not doc_path.exists():
        print(f"[!] Error: File '{doc_path}' not found.", file=sys.stderr)
        return 1

    out_path = Path(args.output) if getattr(args, "output", None) else None

    # Handle 'dump' subcommand
    if args.command == "dump":
        doc_parser = DocumentParser()
        try:
            parsed = doc_parser.parse(doc_path)
            out_file = export_to_txt(parsed, output_path=out_path)
            print(f"[OK] Exported plain text copy to: {out_file}")
            return 0
        except Exception as e:
            print(f"[!] Error exporting text copy: {e}", file=sys.stderr)
            return 1

    # Handle 'snip' subcommand
    if args.command == "snip":
        q_path = resolve_questions_path(getattr(args, "q", None), doc_path)
        doc_parser = DocumentParser()
        try:
            parsed = doc_parser.parse(doc_path, questions_file=q_path)
            txt_file = export_to_txt(parsed, output_path=out_path)
            print(f"[OK] Ingestion complete. Companion text synchronized to: {txt_file}")
            if q_path and q_path.exists():
                print(f"[+] Loaded {len(parsed.questions)} target(s) from questions file: {q_path}")
            return 0
        except Exception as e:
            print(f"[!] Error during snipping ingestion: {e}", file=sys.stderr)
            return 1

    # Handle 'hlt' subcommand
    if args.command == "hlt":
        findings_arg = getattr(args, "findings", None)
        findings_path = resolve_findings_path(findings_arg, doc_path)
        if not findings_path or not findings_path.exists():
            print(f"[!] Error: Findings file not found for '{doc_path}'.", file=sys.stderr)
            return 1

        cfg_path = Path(args.config) if getattr(args, "config", None) else None
        return run_pipeline(
            file_path=doc_path,
            lexical_only=False,
            findings_path=findings_path,
            config_path=cfg_path,
            output_path=out_path,
            dry_run=getattr(args, "dry_run", False),
        )

    # Legacy 'highlight', 'match', 'run'
    cfg_path = Path(args.config) if getattr(args, "config", None) else None
    raw_findings = getattr(args, "findings", None)
    findings_path = resolve_findings_path(raw_findings, doc_path)
    if findings_path and not raw_findings:
        print(f"[+] Auto-detected findings file: {findings_path}")

    q_path = resolve_questions_path(getattr(args, "q", None), doc_path)
    lex_only = (args.command in ("match", "highlight")) or getattr(args, "lexical_only", False)
    dry_run = getattr(args, "dry_run", False)

    return run_pipeline(
        file_path=doc_path,
        lexical_only=lex_only,
        findings_path=findings_path,
        questions_path=q_path,
        config_path=cfg_path,
        output_path=out_path,
        dry_run=dry_run,
    )


if __name__ == "__main__":
    sys.exit(main())
