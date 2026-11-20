"""CLI entry point for Snipper: snip, hlt, lookup, dump, and legacy pipeline modes."""

import argparse
import io
import os
from pathlib import Path
import shutil
import sys
from typing import Any, Optional, Union

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
from storage import get_storage_provider, LocalStorageProvider, StorageProvider


def resolve_findings_path(
    findings_path: Optional[Union[Path, str]],
    document_path: Union[Path, str],
    storage_provider: Optional[Any] = None,
) -> Optional[Union[Path, str]]:
    """Resolves findings JSON path from explicit argument, sub-module convention, or findings/ directory."""
    if storage_provider is not None and getattr(storage_provider, "library_folder_id", None) is not None:
        if findings_path:
            return str(findings_path)
        doc_str = str(document_path).replace("\\", "/")
        if "/" in doc_str:
            parent_dir, filename = doc_str.rsplit("/", 1)
            stem = filename.rsplit(".", 1)[0]
            clean_stem = stem.lower().replace(" ", "_")
            candidates = [
                f"{parent_dir}/{stem}.findings.json",
                f"{parent_dir}/{clean_stem}.findings.json",
                f"{parent_dir}/{stem}.json",
                f"{parent_dir}/{clean_stem}.json",
                f"{parent_dir}/findings/{stem}.json",
            ]
        else:
            stem = doc_str.rsplit(".", 1)[0]
            clean_stem = stem.lower().replace(" ", "_")
            candidates = [
                f"{stem}.findings.json",
                f"{clean_stem}.findings.json",
                f"{stem}.json",
                f"{clean_stem}.json",
                f"findings/{stem}.json",
            ]
        for c in candidates:
            if storage_provider.exists(c):
                return c
        return None

    # Local filesystem resolution
    if findings_path:
        return Path(findings_path)

    doc_p = Path(document_path)
    doc_stem = doc_p.stem
    parent_dir = doc_p.parent
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
    questions_path: Optional[Union[Path, str]],
    document_path: Union[Path, str],
    storage_provider: Optional[Any] = None,
) -> Optional[Union[Path, str]]:
    """Resolves questions file path from explicit argument or sub-module convention (<name>.questions, <name>.questions.gdoc, <name>.questions.txt)."""
    if storage_provider is not None and getattr(storage_provider, "library_folder_id", None) is not None:
        if questions_path:
            return str(questions_path)
        doc_str = str(document_path).replace("\\", "/")
        if "/" in doc_str:
            parent_dir, filename = doc_str.rsplit("/", 1)
            stem = filename.rsplit(".", 1)[0]
            candidates = [
                f"{parent_dir}/{stem}.questions",
                f"{parent_dir}/{stem}.questions.gdoc",
                f"{parent_dir}/{stem}.questions.txt",
                f"{parent_dir}/questions",
                f"{parent_dir}/questions.gdoc",
                f"{parent_dir}/questions.txt",
            ]
        else:
            stem = doc_str.rsplit(".", 1)[0]
            candidates = [
                f"{stem}.questions",
                f"{stem}.questions.gdoc",
                f"{stem}.questions.txt",
                "questions",
                "questions.gdoc",
                "questions.txt",
            ]
        for c in candidates:
            if storage_provider.exists(c):
                return c
        return None

    # Local filesystem resolution
    if questions_path:
        return Path(questions_path)

    doc_p = Path(document_path)
    doc_stem = doc_p.stem
    parent_dir = doc_p.parent

    candidates = [
        parent_dir / f"{doc_stem}.questions",
        parent_dir / f"{doc_stem}.questions.gdoc",
        parent_dir / f"{doc_stem}.questions.txt",
        parent_dir / "questions",
        parent_dir / "questions.gdoc",
        parent_dir / "questions.txt",
    ]

    for c in candidates:
        if c.exists():
            return c

    return None


def _apply_storage_config(
    config: SnipperConfig,
    target_path: Optional[Union[Path, str]],
    storage_override: Optional[str] = None,
) -> None:
    """Applies CLI storage backend overrides and SNIPPER_LIBRARY_FOLDER_ID env fallback."""
    if storage_override:
        config.storage_backend = storage_override
    elif target_path and not str(target_path).startswith("http"):
        if Path(str(target_path)).suffix.lower() == ".gdoc":
            config.storage_backend = "gdoc"

    if not config.library_folder_id:
        env_folder_id = os.environ.get("SNIPPER_LIBRARY_FOLDER_ID", "").strip()
        if env_folder_id:
            config.library_folder_id = env_folder_id


def run_pipeline(
    file_path: Union[Path, str],
    lexical_only: bool = False,
    findings_path: Optional[Union[Path, str]] = None,
    questions_path: Optional[Union[Path, str]] = None,
    config_path: Optional[Path] = None,
    output_path: Optional[Union[Path, str]] = None,
    dry_run: bool = False,
    storage_provider: Optional[Any] = None,
    storage_backend: Optional[str] = None,
) -> int:
    """Executes the Snipper processing pipeline."""
    cfg_file = resolve_constraints_path(config_path, file_path if not str(file_path).startswith("http") else None)
    config = SnipperConfig.from_file(cfg_file, file_path if not str(file_path).startswith("http") else None)
    _apply_storage_config(config, file_path, storage_backend)

    if cfg_file:
        print(f"[+] Loaded configuration from: {cfg_file}")
    else:
        print(f"[*] No CustomConstraints.md found; using {len(config.palette)}-color palette.")

    if storage_provider is None:
        try:
            storage = get_storage_provider(config)
        except Exception as e:
            print(f"[!] {e}", file=sys.stderr)
            return 1
    else:
        storage = storage_provider

    is_gdrive = getattr(storage, "library_folder_id", None) is not None
    is_gdoc = (
        (config.storage_backend == "gdoc")
        or (getattr(storage, "backend", None) == "gdoc")
        or (getattr(storage, "storage_backend", None) == "gdoc")
    )

    print(f"[*] Ingesting document: {file_path}")
    parser = DocumentParser(config)
    try:
        if is_gdrive:
            doc_stream = storage.read_stream(file_path)
            q_text = storage.read_text(questions_path) if questions_path else None
            parsed = parser.parse(doc_stream, questions_text=q_text, virtual_path=file_path)
        else:
            parsed = parser.parse(Path(file_path), questions_file=Path(questions_path) if questions_path else None)
    except Exception as e:
        print(f"[!] Error parsing document: {e}", file=sys.stderr)
        return 1

    print(f"[+] Loaded {len(parsed.questions)} target(s) and {len(parsed.body_paragraphs)} body paragraph(s).")

    # Auto-synchronize lightweight text companion (<name>.txt)
    if not dry_run:
        try:
            if is_gdrive:
                txt_path = export_to_txt(parsed, output_path=output_path, storage_provider=storage, config=config)
            else:
                txt_path = export_to_txt(parsed, output_path=output_path, config=config)
            if is_gdoc or is_gdrive:
                print(f"[+] In-memory companion text ready: {txt_path}")
            else:
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
            if is_gdrive:
                if not storage.exists(findings_path):
                    print(f"[!] Error: Findings file '{findings_path}' not found.", file=sys.stderr)
                    return 1
                try:
                    findings_data = FindingsData.from_json(storage.read_text(findings_path))
                except Exception as e:
                    print(f"[!] Error loading findings JSON: {e}", file=sys.stderr)
                    return 1
            else:
                f_p = Path(findings_path)
                if not f_p.exists():
                    print(f"[!] Error: Findings file '{findings_path}' not found.", file=sys.stderr)
                    return 1
                try:
                    findings_data = FindingsData.from_file(f_p)
                except Exception as e:
                    print(f"[!] Error loading findings JSON: {e}", file=sys.stderr)
                    return 1
            print(f"[+] DRY-RUN: Findings validated successfully ({len(findings_data.findings)} finding(s)).")
            print(f"[*] DRY-RUN: DocumentMutator would apply findings to {target}.")
            return 0
        print(f"[*] DRY-RUN: Highlighter would highlight {len(matches)} match(es) in {target}.")
        return 0

    if lexical_only:
        if is_gdoc:
            from mutation import GoogleDocsMutator
            mutator = GoogleDocsMutator(config, docs_service=getattr(storage, "docs_service", None))
            empty_findings = FindingsData(findings=[])
            try:
                mutator.mutate(
                    target,
                    parsed,
                    matches,
                    empty_findings,
                    storage_provider=storage,
                )
            except Exception as e:
                print(f"[!] Error saving Google Doc: {e}", file=sys.stderr)
                return 1
            print(f"[OK] Google Doc saved in-place to: {target}")
            return 0

        highlighter = DocumentHighlighter(config)
        highlighter.highlight_matches(parsed.body_paragraphs, matches)
        try:
            if is_gdrive:
                out_stream = io.BytesIO()
                parsed.doc.save(out_stream)
                out_stream.seek(0)
                storage.update_stream(
                    target,
                    out_stream,
                    mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            else:
                parsed.doc.save(str(target))
        except PermissionError:
            print(f"[!] Error: Permission denied when saving to '{target}'.", file=sys.stderr)
            print("[!] Please close the document in Microsoft Word and try again.", file=sys.stderr)
            return 2
        except Exception as e:
            print(f"[!] Error saving document: {e}", file=sys.stderr)
            return 1
        print(f"[OK] Document saved in-place to: {target}")
        return 0

    if findings_path:
        if is_gdrive:
            if not storage.exists(findings_path):
                print(f"[!] Error: Findings file '{findings_path}' not found.", file=sys.stderr)
                return 1
            try:
                findings_data = FindingsData.from_json(storage.read_text(findings_path))
            except Exception as e:
                print(f"[!] Error loading findings JSON: {e}", file=sys.stderr)
                return 1
        else:
            f_p = Path(findings_path)
            if not f_p.exists():
                print(f"[!] Error: Findings file '{findings_path}' not found.", file=sys.stderr)
                return 1
            try:
                findings_data = FindingsData.from_file(f_p)
            except Exception as e:
                print(f"[!] Error loading findings JSON: {e}", file=sys.stderr)
                return 1

        if is_gdoc:
            from mutation import GoogleDocsMutator
            mutator = GoogleDocsMutator(config, docs_service=getattr(storage, "docs_service", None))
            try:
                mutator.mutate(
                    target,
                    parsed,
                    matches,
                    findings_data,
                    storage_provider=storage,
                )
            except Exception as e:
                print(f"[!] Error saving Google Doc: {e}", file=sys.stderr)
                return 1
            print(f"[OK] Full pipeline complete. Mutated Google Doc saved in-place to: {target}")
            return 0

        mutator = DocumentMutator(config)
        try:
            if is_gdrive:
                out_stream = io.BytesIO()
                mutator.mutate(parsed, matches, findings_data, output_path=out_stream)
                storage.update_stream(
                    target,
                    out_stream,
                    mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            else:
                mutator.mutate(parsed, matches, findings_data, output_path=Path(target))
        except PermissionError:
            print(f"[!] Error: Permission denied when saving to '{target}'.", file=sys.stderr)
            print("[!] Please close the document in Microsoft Word and try again.", file=sys.stderr)
            return 2
        except Exception as e:
            print(f"[!] Error saving document: {e}", file=sys.stderr)
            return 1

        print(f"[OK] Full pipeline complete. Mutated document saved in-place to: {target}")
        return 0

    if is_gdoc:
        from mutation import GoogleDocsMutator
        mutator = GoogleDocsMutator(config, docs_service=getattr(storage, "docs_service", None))
        empty_findings = FindingsData(findings=[])
        try:
            mutator.mutate(
                target,
                parsed,
                matches,
                empty_findings,
                storage_provider=storage,
            )
        except Exception as e:
            print(f"[!] Error saving Google Doc: {e}", file=sys.stderr)
            return 1
        print(f"[OK] Google Doc saved in-place to: {target}")
        return 0

    highlighter = DocumentHighlighter(config)
    highlighter.highlight_matches(parsed.body_paragraphs, matches)
    try:
        if is_gdrive:
            out_stream = io.BytesIO()
            parsed.doc.save(out_stream)
            out_stream.seek(0)
            storage.update_stream(
                target,
                out_stream,
                mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        else:
            parsed.doc.save(str(target))
    except PermissionError:
        print(f"[!] Error: Permission denied when saving to '{target}'.", file=sys.stderr)
        print("[!] Please close the document in Microsoft Word and try again.", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"[!] Error saving document: {e}", file=sys.stderr)
        return 1

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
    snip_parser.add_argument("--output", "--out", dest="output", type=str, default=None, help="Optional output path")
    snip_parser.add_argument("--config", type=str, default=None, help="Path to CustomConstraints.md")
    snip_parser.add_argument("--storage", choices=["local", "gdrive", "gdoc"], default=None, help="Storage backend (local, gdrive, gdoc)")

    # /snipper:hlt / highlight
    hlt_parser = subparsers.add_parser("hlt", help="Mutate .docx document with findings and highlights")
    hlt_parser.add_argument("document", nargs="?", default=None, help="Path to input .docx document")
    hlt_parser.add_argument("--docs", type=str, default=None, help="Path to input .docx document")
    hlt_parser.add_argument("--f", "--findings", dest="findings", type=str, default=None, help="Path to findings file (defaults to <name>.findings.json)")
    hlt_parser.add_argument("--q", type=str, default=None, help="Path to questions file (defaults to auto-detect)")
    hlt_parser.add_argument("--config", type=str, default=None, help="Path to CustomConstraints.md")
    hlt_parser.add_argument("--output", "--out", dest="output", type=str, default=None, help="Optional output path")
    hlt_parser.add_argument("--dry-run", action="store_true", help="Simulate execution without modifying files")
    hlt_parser.add_argument("--storage", choices=["local", "gdrive", "gdoc"], default=None, help="Storage backend (local, gdrive, gdoc)")

    # highlight (alias)
    highlight_parser = subparsers.add_parser("highlight", help="Execute standalone Phase 1 Highlighter")
    highlight_parser.add_argument("document", type=str, help="Path to input .docx document")
    highlight_parser.add_argument("--config", type=str, default=None, help="Path to CustomConstraints.md")
    highlight_parser.add_argument("--output", "--out", dest="output", type=str, default=None, help="Optional output path")
    highlight_parser.add_argument("--dry-run", action="store_true", help="Simulate execution without modifying files")
    highlight_parser.add_argument("--storage", choices=["local", "gdrive", "gdoc"], default=None, help="Storage backend (local, gdrive, gdoc)")

    # match (alias)
    match_parser = subparsers.add_parser("match", help="Execute standalone lexical match only")
    match_parser.add_argument("document", type=str, help="Path to input .docx document")
    match_parser.add_argument("--config", type=str, default=None, help="Path to CustomConstraints.md")
    match_parser.add_argument("--output", "--out", dest="output", type=str, default=None, help="Optional output path")
    match_parser.add_argument("--dry-run", action="store_true", help="Simulate execution without modifying files")
    match_parser.add_argument("--storage", choices=["local", "gdrive", "gdoc"], default=None, help="Storage backend (local, gdrive, gdoc)")

    # /snipper:lookup
    lookup_parser = subparsers.add_parser("lookup", help="Search snippets across existing findings files within scope")
    lookup_parser.add_argument("query", nargs="?", default=None, help="Search query string")
    lookup_parser.add_argument("--q", type=str, default=None, help="Question query string")
    lookup_parser.add_argument("--o", type=str, default=None, help="Objective query string")
    lookup_parser.add_argument("--dir", type=str, default=None, help="Target file or directory path")
    lookup_parser.add_argument("--scope", type=str, default=None, choices=["local", "hierarchical", "global"], help="Scope mode")
    lookup_parser.add_argument("--limit", type=int, default=None, help="Maximum number of snippets to return")
    lookup_parser.add_argument("--config", type=str, default=None, help="Path to CustomConstraints.md")
    lookup_parser.add_argument("--storage", choices=["local", "gdrive", "gdoc"], default=None, help="Storage backend (local, gdrive, gdoc)")

    # run (legacy full pipeline)
    run_parser = subparsers.add_parser("run", help="Run full Snipper pipeline")
    run_parser.add_argument("document", type=str, help="Path to input .docx document")
    run_parser.add_argument("--lexical-only", action="store_true", help="Execute deterministic lexical matching only")
    run_parser.add_argument("--findings", type=str, default=None, help="Path to findings file")
    run_parser.add_argument("--q", type=str, default=None, help="Path to questions file")
    run_parser.add_argument("--config", type=str, default=None, help="Path to CustomConstraints.md")
    run_parser.add_argument("--output", "--out", dest="output", type=str, default=None, help="Optional output path")
    run_parser.add_argument("--dry-run", action="store_true", help="Simulate execution without modifying files")
    run_parser.add_argument("--storage", choices=["local", "gdrive", "gdoc"], default=None, help="Storage backend (local, gdrive, gdoc)")

    # dump
    dump_parser = subparsers.add_parser("dump", help="Export plain-text copy of document with paragraph coordinates")
    dump_parser.add_argument("document", type=str, help="Path to input .docx document")
    dump_parser.add_argument("--output", "--out", dest="output", type=str, default=None, help="Optional output path")
    dump_parser.add_argument("--config", type=str, default=None, help="Path to CustomConstraints.md")
    dump_parser.add_argument("--storage", choices=["local", "gdrive", "gdoc"], default=None, help="Storage backend (local, gdrive, gdoc)")

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    cfg_arg = getattr(args, "config", None)
    raw_doc = getattr(args, "document", None) or getattr(args, "docs", None) or getattr(args, "dir", None)
    cfg_file = resolve_constraints_path(cfg_arg, raw_doc if raw_doc else None)
    config = SnipperConfig.from_file(cfg_file, raw_doc if raw_doc else None)

    storage_override = getattr(args, "storage", None)
    _apply_storage_config(config, raw_doc, storage_override)

    try:
        storage = get_storage_provider(config)
    except Exception as e:
        print(f"[!] {e}", file=sys.stderr)
        return 1

    is_gdrive = getattr(storage, "library_folder_id", None) is not None
    is_gdoc = (
        (config.storage_backend == "gdoc")
        or (getattr(storage, "backend", None) == "gdoc")
        or (getattr(storage, "storage_backend", None) == "gdoc")
    )

    # Handle 'lookup' subcommand
    if args.command == "lookup":
        query = args.query or args.q or args.o
        if not query:
            print("[!] Error: Query string (positional, --q, or --o) must be provided.", file=sys.stderr)
            return 1
        lib_root = config.library_folder_id if is_gdrive else None
        candidates, scope_res = lookup_snippets(
            query=query,
            target_path=args.dir,
            scope=args.scope,
            limit=args.limit,
            storage_provider=storage,
            library_root=lib_root,
        )
        print(format_lookup_results(candidates, scope_res.scope_type, limit=args.limit))
        return 0

    # Resolve document path across different subcommands
    if not raw_doc:
        print("[!] Error: Document path is required.", file=sys.stderr)
        return 1

    if is_gdrive:
        if not storage.exists(raw_doc):
            print(f"[!] Error: File '{raw_doc}' not found on Google Drive.", file=sys.stderr)
            return 1
        doc_path = raw_doc
    else:
        doc_path = Path(raw_doc)
        if not doc_path.exists():
            print(f"[!] Error: File '{doc_path}' not found.", file=sys.stderr)
            return 1

    out_path = Path(args.output) if (getattr(args, "output", None) and not is_gdrive) else getattr(args, "output", None)

    # Handle 'dump' subcommand
    if args.command == "dump":
        doc_parser = DocumentParser(config)
        try:
            if is_gdrive:
                doc_stream = storage.read_stream(raw_doc)
                parsed = doc_parser.parse(doc_stream, virtual_path=raw_doc)
                out_file = export_to_txt(parsed, output_path=out_path, storage_provider=storage, config=config)
            else:
                parsed = doc_parser.parse(doc_path)
                out_file = export_to_txt(parsed, output_path=out_path, config=config)
            print(f"[OK] Exported plain text copy to: {out_file}")
            return 0
        except Exception as e:
            print(f"[!] Error exporting text copy: {e}", file=sys.stderr)
            return 1

    # Handle 'snip' subcommand
    if args.command == "snip":
        q_path = resolve_questions_path(getattr(args, "q", None), doc_path, storage_provider=storage if is_gdrive else None)
        doc_parser = DocumentParser(config)
        try:
            if is_gdrive:
                doc_stream = storage.read_stream(raw_doc)
                q_text = storage.read_text(q_path) if q_path else None
                parsed = doc_parser.parse(doc_stream, questions_text=q_text, virtual_path=raw_doc)
                txt_file = export_to_txt(parsed, output_path=out_path, storage_provider=storage, config=config)
                if is_gdoc:
                    print(f"[OK] Ingestion complete. In-memory companion text ready: {txt_file}")
                else:
                    print(f"[OK] Ingestion complete. Companion text synchronized to: {txt_file}")
                if q_path and q_text:
                    print(f"[+] Loaded {len(parsed.questions)} target(s) from questions file: {q_path}")
                return 0
            else:
                parsed = doc_parser.parse(doc_path, questions_file=Path(q_path) if q_path else None)
                txt_file = export_to_txt(parsed, output_path=out_path, config=config)
                print(f"[OK] Ingestion complete. Companion text synchronized to: {txt_file}")
                if q_path and Path(q_path).exists():
                    print(f"[+] Loaded {len(parsed.questions)} target(s) from questions file: {q_path}")
                return 0
        except Exception as e:
            print(f"[!] Error during snipping ingestion: {e}", file=sys.stderr)
            return 1

    # Handle 'hlt' subcommand
    if args.command == "hlt":
        findings_arg = getattr(args, "findings", None)
        findings_path = resolve_findings_path(findings_arg, doc_path, storage_provider=storage if is_gdrive else None)
        if not findings_path:
            print(f"[!] Error: Findings file not found for '{doc_path}'.", file=sys.stderr)
            return 1
        if not is_gdrive and not Path(findings_path).exists():
            print(f"[!] Error: Findings file '{findings_path}' not found.", file=sys.stderr)
            return 1

        q_path = resolve_questions_path(getattr(args, "q", None), doc_path, storage_provider=storage if is_gdrive else None)
        cfg_path = Path(args.config) if getattr(args, "config", None) else None
        return run_pipeline(
            file_path=doc_path,
            lexical_only=False,
            findings_path=findings_path,
            questions_path=q_path,
            config_path=cfg_path,
            output_path=out_path,
            dry_run=getattr(args, "dry_run", False),
            storage_provider=storage,
        )

    # Legacy 'highlight', 'match', 'run'
    cfg_path = Path(args.config) if getattr(args, "config", None) else None
    raw_findings = getattr(args, "findings", None)
    findings_path = resolve_findings_path(raw_findings, doc_path, storage_provider=storage if is_gdrive else None)
    if findings_path and not raw_findings:
        print(f"[+] Auto-detected findings file: {findings_path}")

    q_path = resolve_questions_path(getattr(args, "q", None), doc_path, storage_provider=storage if is_gdrive else None)
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
        storage_provider=storage,
    )


if __name__ == "__main__":
    sys.exit(main())
