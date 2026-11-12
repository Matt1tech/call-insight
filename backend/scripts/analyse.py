"""Run all transcripts through the analysis graph and write the results to JSON.

Usage: uv run python scripts/analyse.py [--mode auto|live|replay] [--out PATH]
The default output is data/analysis/analysis.generated.json; the reviewed
data/analysis/analysis.json is never overwritten by this script.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai.workflow import DATA_DIR, load_reviewed, load_transcripts, run_analysis  # noqa: E402

DEFAULT_OUT = DATA_DIR / "analysis" / "analysis.generated.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["auto", "live", "replay"], default="auto")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    results, failed = [], 0
    for conversation_id in load_transcripts():
        run = run_analysis(conversation_id, mode=args.mode)
        status = "ok" if run.analysis and not run.blocking_errors else "ERRORS"
        print(f"{conversation_id}: mode={run.mode} {status}")
        for error in run.errors:
            print(f"  - {error}")
        if run.analysis is None:
            failed += 1
        else:
            results.append(run.analysis.model_dump())

    if args.out.resolve() == (DATA_DIR / "analysis" / "analysis.json").resolve():
        print("Refusing to overwrite the reviewed analysis.json; choose another --out.")
        return 2
    args.out.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(results)} analyses to {args.out}")

    if run.mode == "replay" and not failed:
        same = results == list(load_reviewed().values())
        print("Replay matches reviewed analysis:", "yes" if same else "NO")
        return 0 if same else 1
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
