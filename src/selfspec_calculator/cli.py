from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import HardwareConfig, ModelConfig
from .estimator import estimate_sweep
from .io import load_speculation_stats


def _existing_path(value: str) -> Path:
    path = Path(value)
    if not path.exists():
        raise argparse.ArgumentTypeError(f"File not found: {value}")
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ppa-calculator", add_help=True)
    parser.add_argument("--model", required=True, type=_existing_path, help="Path to model.yaml")
    parser.add_argument("--hardware", required=True, type=_existing_path, help="Path to hardware.yaml")
    parser.add_argument("--stats", required=True, type=_existing_path, help="Path to stats (json|yaml)")
    parser.add_argument(
        "--prompt-lengths",
        nargs="+",
        required=True,
        type=int,
        help="One or more prompt lengths (e.g., 64 128 256)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write report JSON to this path (default: stdout)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        model = ModelConfig.from_yaml(args.model)
        hardware = HardwareConfig.from_yaml(args.hardware)
        stats = load_speculation_stats(args.stats)
        report = estimate_sweep(
            model=model,
            hardware=hardware,
            stats=stats,
            prompt_lengths=args.prompt_lengths,
            paths={
                "model": str(args.model),
                "hardware": str(args.hardware),
                "stats": str(args.stats),
            },
        )
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 2

    payload = report.model_dump(mode="json")
    text = json.dumps(payload, indent=2, sort_keys=True)
    if args.output is None:
        print(text)
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text + "\n", encoding="utf-8")
    return 0

