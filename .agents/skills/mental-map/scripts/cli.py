"""Command Line Interface for mental-map skill.

Transforms .map documents into Draw.io mental maps with directional curved arrows,
adaptive grid layouts, and harmonic color palettes.
"""

import argparse
import sys
from pathlib import Path
import webbrowser

# Add current directory to sys.path
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from parser import parse_document
from layout import build_layout
from emitter import emit_drawio_xml, save_diagram

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)


def main():
    parser = argparse.ArgumentParser(
        description="Generate modular Draw.io mental maps from .map documents (Google Docs or local files)."
    )
    parser.add_argument(
        "source",
        help="Path to .map / .md / .gdoc file, Google Docs URL, or Google Doc ID."
    )
    parser.add_argument(
        "-o", "--output",
        help="Optional custom output path or directory for the generated .drawio file.",
        default=None
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing .drawio file if present. If omitted, creates a versioned copy (v2, v3...)."
    )
    parser.add_argument(
        "--no-gdrive",
        action="store_true",
        help="Skip Google Drive cloud API upload and save only to local filesystem."
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open the generated diagram in your web browser (diagrams.net / Draw.io)."
    )

    args = parser.parse_args()

    print("\n========================================================")
    print("      Mental Map Generator (Draw.io Modular Maps)       ")
    print("========================================================\n")

    # 1. Parse Document
    print(f"[*] Ingesting document: {args.source}")
    try:
        model = parse_document(args.source)
    except Exception as e:
        print(f"[!] Error reading or parsing document: {e}")
        sys.exit(1)

    num_concepts = sum(len(s.concepts) for s in model.sections)
    num_bullets = sum(
        sum(len(c.bullets) for c in s.concepts) for s in model.sections
    )

    print(f"[+] Document Title: '{model.title}'")
    print(f"[+] Found {len(model.sections)} sections, {num_concepts} concepts, and {num_bullets} bullet cards.")

    # 2. Build Layout
    print("[*] Computing adaptive layout and arrow geometry...")
    layout = build_layout(model)
    print(f"[+] Layout canvas: {layout.canvas_width}x{layout.canvas_height}px, {len(layout.nodes)} cards, {len(layout.edges)} directional arrows.")

    # 3. Emit XML
    print("[*] Serializing and strictly validating Draw.io XML...")
    try:
        xml_content = emit_drawio_xml(layout)
        print("[+] XML strictly validated with xml.etree.ElementTree (0 errors).")
    except Exception as e:
        print(f"[!] XML Validation Error: {e}")
        sys.exit(1)

    # 4. Determine Output Path
    if args.output:
        out_p = Path(args.output)
        if out_p.is_dir() or (not out_p.suffix and not out_p.exists()):
            out_file = out_p / f"{model.title}.drawio"
        else:
            out_file = out_p
    else:
        # Check if source is a local path
        src_p = Path(args.source)
        if src_p.parent.exists() and str(src_p.parent) not in (".", ""):
            out_file = src_p.parent / f"{model.title}.drawio"
        elif src_p.exists() and src_p.is_file():
            out_file = src_p.parent / f"{model.title}.drawio"
        else:
            out_file = Path.cwd() / f"{model.title}.drawio"

    # 5. Save Diagram
    print(f"[*] Saving diagram to: {out_file}")
    res = save_diagram(
        xml_content=xml_content,
        output_path=out_file,
        overwrite=args.overwrite,
        sync_gdrive=not args.no_gdrive
    )

    print(f"[+] Saved locally: {res['local_path']}")
    if res["overwritten"]:
        print("    (Overwrote previous file in-place)")
    else:
        print("    (Preserved previous versions)")

    if res.get("gdrive_file_id"):
        print(f"[+] Google Drive Cloud File ID: {res['gdrive_file_id']}")
    if res.get("diagrams_net_url"):
        print(f"[+] Direct diagrams.net link: {res['diagrams_net_url']}")
    elif res.get("gdrive_sync_error"):
        print(f"[-] Google Drive sync note: {res['gdrive_sync_error']}")

    # 6. Launch browser if requested
    if args.open:
        target_url = res.get("diagrams_net_url") or f"file:///{Path(res['local_path']).resolve()}"
        print(f"[*] Opening in browser: {target_url}")
        webbrowser.open(target_url)

    print("\n[✓] Mental map generated successfully!\n")


if __name__ == "__main__":
    main()
