from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--step",
        type=str,
        default="all",
        choices=["1", "2", "all"],
        help="Run step 1 (generate eval data) / step 2 (run RAGAS).",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    step1 = repo_root / "test" / "rag_eval" / "run_step1_generate_eval_data.py"
    step2 = repo_root / "test" / "rag_eval" / "run_step2_ragas_eval.py"

    if args.step in {"1", "all"}:
        subprocess.check_call([sys.executable, str(step1)])

    if args.step in {"2", "all"}:
        subprocess.check_call([sys.executable, str(step2)])


if __name__ == "__main__":
    main()

