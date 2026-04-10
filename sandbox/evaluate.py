#!/usr/bin/env python3
"""
Main evaluation entrypoint for the PDF parsing sandbox.

Usage examples:
    # Run full ablation (all parsers, all document types)
    python evaluate.py --all

    # Run specific parsers only
    python evaluate.py --parsers docling pymupdf paddleocr_en

    # Run on specific document type
    python evaluate.py --doc-type scanned_clean_300dpi

    # Quick smoke test (3 docs max per type)
    python evaluate.py --all --max-docs 3

    # List available parsers
    python evaluate.py --list-parsers

    # Single file evaluation (no ground truth required)
    python evaluate.py --file path/to/form.pdf --parser docling
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

# Ensure src/ is on the Python path when running from sandbox/
sys.path.insert(0, str(Path(__file__).parent))

from src.parsers import PARSER_REGISTRY
from src.ablation.runner import AblationRunner, AblationConfig

console = Console()


def list_parsers() -> None:
    """Print all available parsers with their properties."""
    from src.parsers import PARSER_REGISTRY
    console.print(Panel("[bold]Available Parsers[/bold]", style="blue"))
    for name, cls_or_factory in PARSER_REGISTRY.items():
        try:
            p = cls_or_factory() if callable(cls_or_factory) and not isinstance(cls_or_factory, type) else cls_or_factory()
            console.print(
                f"  [cyan]{name:30}[/cyan] "
                f"v{p.version:15} "
                f"license={p.license:20} "
                f"scanned={'✓' if p.supports_scanned else '✗':3} "
                f"tables={'✓' if p.supports_tables else '✗':3} "
                f"hw={'✓' if p.supports_handwriting else '✗'}"
            )
        except Exception as e:
            console.print(f"  [red]{name:30} ERROR: {e}[/red]")


def run_single(pdf_path: Path, parser_name: str, gt_path: Path | None) -> None:
    """Run a single parser on a single file and print results."""
    if parser_name not in PARSER_REGISTRY:
        console.print(f"[red]Unknown parser: {parser_name}[/red]")
        sys.exit(1)

    cls_or_factory = PARSER_REGISTRY[parser_name]
    parser = cls_or_factory() if callable(cls_or_factory) else cls_or_factory

    console.print(f"Parsing [cyan]{pdf_path.name}[/cyan] with [yellow]{parser_name}[/yellow]...")
    result = parser.extract(pdf_path)

    console.print(f"\n[bold]Result:[/bold]")
    console.print(f"  Success: {result.success}")
    console.print(f"  Wall time: {result.wall_time_seconds:.2f}s")
    console.print(f"  Text length: {len(result.full_text or '')} chars")
    console.print(f"  Fields extracted: {len(result.fields)}")
    console.print(f"  Tables extracted: {len(result.tables)}")

    if result.errors:
        console.print(f"\n[yellow]Errors/Warnings:[/yellow]")
        for err in result.errors:
            console.print(f"  - {err}")

    if result.fields:
        console.print(f"\n[bold]Sample fields (first 5):[/bold]")
        for f in result.fields[:5]:
            conf_str = f" (conf={f.confidence:.2f})" if f.confidence is not None else ""
            console.print(f"  [{f.field_type}] {f.name}: {f.value[:60]}{conf_str}")

    if gt_path and gt_path.exists():
        from src.metrics.compute import MetricsComputer
        import fitz
        doc = fitz.open(str(pdf_path))
        page_count = doc.page_count
        doc.close()
        metrics = MetricsComputer()
        eval_result = metrics.compute(result, gt_path, page_count)
        console.print(f"\n[bold]Metrics:[/bold]")
        console.print(f"  CER:               {eval_result.cer:.4f}")
        console.print(f"  WER:               {eval_result.wer:.4f}")
        console.print(f"  Field F1:          {eval_result.field_f1:.4f}")
        console.print(f"  Table Cell Acc:    {eval_result.table_cell_accuracy:.4f}")
        console.print(f"  Speed:             {eval_result.pages_per_second:.2f} pages/sec")


def main():
    parser = argparse.ArgumentParser(
        description="PDF Parsing Evaluation Sandbox",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--all", action="store_true", help="Run full ablation")
    parser.add_argument("--parsers", nargs="+", help="Specific parsers to run")
    parser.add_argument("--doc-type", help="Run on specific document type only")
    parser.add_argument("--max-docs", type=int, default=50, help="Max docs per type (default: 50)")
    parser.add_argument("--file", type=Path, help="Evaluate a single PDF file")
    parser.add_argument("--parser", help="Parser to use for --file mode")
    parser.add_argument("--gt", type=Path, help="Ground truth JSON for --file mode")
    parser.add_argument("--list-parsers", action="store_true")
    parser.add_argument("--data-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--results-dir", type=Path, default=Path("results"))

    args = parser.parse_args()

    if args.list_parsers:
        list_parsers()
        return

    if args.file:
        if not args.parser:
            console.print("[red]--parser required with --file[/red]")
            sys.exit(1)
        run_single(args.file, args.parser, args.gt)
        return

    if args.all or args.parsers:
        config = AblationConfig(
            data_dir=args.data_dir,
            results_dir=args.results_dir,
            parsers=args.parsers,
            doc_types=[args.doc_type] if args.doc_type else None,
            max_docs_per_type=args.max_docs,
        )
        runner = AblationRunner(config)
        runner.run()
        return

    parser.print_help()


if __name__ == "__main__":
    main()
