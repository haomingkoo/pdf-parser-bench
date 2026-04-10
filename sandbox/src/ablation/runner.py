"""
Ablation test runner — systematically evaluates all parser × preprocessing × document_type permutations.

Design:
- Reads test PDF corpus from data/raw/
- Reads ground truth annotations from data/ground_truth/
- Runs every registered parser on every document
- Computes all metrics via MetricsComputer
- Saves results to results/ablation_{timestamp}.jsonl
- Generates summary CSV and terminal report

Permutation space:
  parsers: N (all in PARSER_REGISTRY, or a subset)
  preprocessing: on / off
  document_types: digital / scanned_clean / scanned_degraded / handwritten / mixed
  → Each (parser, document) pair is one run

At 8 parsers × 5 doc types × N_docs_per_type = N total runs.
Runtime estimate: ~2–30 minutes depending on parser and doc count.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

from src.parsers import PARSER_REGISTRY, BaseParser
from src.metrics.compute import MetricsComputer, EvaluationResult

console = Console()


@dataclass
class AblationConfig:
    """Configuration for an ablation run."""
    data_dir: Path = Path("data/raw")
    gt_dir: Path = Path("data/ground_truth")
    results_dir: Path = Path("results")
    parsers: Optional[list[str]] = None      # None = all registered parsers
    doc_types: Optional[list[str]] = None    # None = all available document types
    max_docs_per_type: int = 50              # Cap for faster development runs


class AblationRunner:

    DOCUMENT_TYPES = [
        "digital_acroform",
        "digital_text_layer",
        "scanned_clean_300dpi",
        "scanned_degraded_sub300dpi",
        "handwritten_partial",
        "handwritten_majority",
        "mixed_print_handwrite",
        "fax_200dpi",
    ]

    def __init__(self, config: AblationConfig):
        self.config = config
        self.metrics = MetricsComputer()
        self.config.results_dir.mkdir(parents=True, exist_ok=True)

    def run(self) -> list[EvaluationResult]:
        """
        Run the full ablation. Returns all evaluation results.
        Also writes results to JSONL and summary CSV.
        """
        docs = self._discover_documents()
        parsers = self._instantiate_parsers()

        console.print(f"\n[bold blue]Ablation Run[/bold blue]")
        console.print(f"Documents: {len(docs)}")
        console.print(f"Parsers: {[p.name for p in parsers]}")
        console.print(f"Total runs: {len(docs) * len(parsers)}\n")

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        results_file = self.config.results_dir / f"ablation_{timestamp}.jsonl"
        all_results: list[EvaluationResult] = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            total = len(docs) * len(parsers)
            task = progress.add_task("Running ablation...", total=total)

            with open(results_file, "w") as out_f:
                for parser in parsers:
                    for doc_path, gt_path, doc_type in docs:
                        progress.update(
                            task,
                            description=f"{parser.name} × {doc_path.stem}",
                            advance=1,
                        )

                        parse_result = parser.extract(doc_path)

                        if gt_path and gt_path.exists():
                            import fitz
                            doc = fitz.open(str(doc_path))
                            page_count = doc.page_count
                            doc.close()
                            eval_result = self.metrics.compute(
                                parse_result, gt_path, page_count
                            )
                        else:
                            # No ground truth — record timing and errors only
                            eval_result = EvaluationResult(
                                parser_name=parse_result.parser_name,
                                document_id=doc_path.stem,
                                wall_time_seconds=parse_result.wall_time_seconds,
                                parse_errors=parse_result.errors,
                            )

                        eval_result.doc_type = doc_type
                        eval_result_dict = eval_result.to_dict()
                        all_results.append(eval_result)
                        out_f.write(json.dumps(eval_result_dict) + "\n")

        console.print(f"\n[green]Results saved to: {results_file}[/green]")
        self._print_summary(all_results)
        self._save_summary_csv(all_results, timestamp)
        return all_results

    def _discover_documents(self) -> list[tuple[Path, Optional[Path], str]]:
        """
        Discover test PDFs and their corresponding ground truth files.
        Returns list of (pdf_path, gt_path, doc_type) tuples.

        Expected directory structure:
          data/raw/digital_acroform/form1.pdf
          data/raw/scanned_clean_300dpi/form2.pdf
          ...
          data/ground_truth/form1.json
          data/ground_truth/form2.json
        """
        docs = []
        doc_types = self.config.doc_types or self.DOCUMENT_TYPES

        for doc_type in doc_types:
            type_dir = self.config.data_dir / doc_type
            if not type_dir.exists():
                console.print(f"[yellow]Warning: {type_dir} does not exist, skipping[/yellow]")
                continue

            pdfs = sorted(type_dir.glob("*.pdf"))
            if self.config.max_docs_per_type:
                pdfs = pdfs[: self.config.max_docs_per_type]

            for pdf_path in pdfs:
                gt_path = self.config.gt_dir / f"{pdf_path.stem}.json"
                docs.append((pdf_path, gt_path if gt_path.exists() else None, doc_type))

        return docs

    def _instantiate_parsers(self) -> list[BaseParser]:
        """Instantiate all parsers in the registry (or configured subset)."""
        names = self.config.parsers or list(PARSER_REGISTRY.keys())
        parsers = []
        for name in names:
            if name not in PARSER_REGISTRY:
                console.print(f"[red]Unknown parser: {name}[/red]")
                continue
            try:
                cls_or_factory = PARSER_REGISTRY[name]
                parser = cls_or_factory() if callable(cls_or_factory) else cls_or_factory
                parsers.append(parser)
            except Exception as e:
                console.print(f"[red]Failed to instantiate {name}: {e}[/red]")
        return parsers

    def _print_summary(self, results: list[EvaluationResult]) -> None:
        """Print a rich table summarizing results per parser."""
        table = Table(title="Ablation Summary — Mean Metrics Per Parser")
        table.add_column("Parser", style="cyan")
        table.add_column("CER ↓", justify="right")
        table.add_column("WER ↓", justify="right")
        table.add_column("FER ↑", justify="right")
        table.add_column("Field F1 ↑", justify="right")
        table.add_column("Table Acc ↑", justify="right")
        table.add_column("Speed (p/s) ↑", justify="right")
        table.add_column("N Docs", justify="right")

        import numpy as np
        from collections import defaultdict

        by_parser: dict[str, list[EvaluationResult]] = defaultdict(list)
        for r in results:
            by_parser[r.parser_name].append(r)

        for parser_name, parser_results in sorted(by_parser.items()):
            table.add_row(
                parser_name,
                f"{np.mean([r.cer for r in parser_results]):.3f}",
                f"{np.mean([r.wer for r in parser_results]):.3f}",
                f"{np.mean([r.fer for r in parser_results]):.3f}",
                f"{np.mean([r.field_f1 for r in parser_results]):.3f}",
                f"{np.mean([r.table_cell_accuracy for r in parser_results]):.3f}",
                f"{np.mean([r.pages_per_second for r in parser_results]):.2f}",
                str(len(parser_results)),
            )

        console.print(table)

    def _save_summary_csv(self, results: list[EvaluationResult], timestamp: str) -> None:
        """Save a flat CSV for analysis in notebooks/Excel."""
        import csv
        csv_path = self.config.results_dir / f"summary_{timestamp}.csv"
        if not results:
            return
        fieldnames = list(results[0].to_dict().keys())  # doc_type is now in to_dict()
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in results:
                writer.writerow(r.to_dict())
        console.print(f"[green]CSV saved to: {csv_path}[/green]")
