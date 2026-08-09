"""Turn bench/results/*.json into a markdown comparison table.

uv run bench/report.py                  # everything, sorted by latency
uv run bench/report.py --sort score     # sorted by accuracy
uv run bench/report.py a b c            # just these runs, in this order
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from latexscore import score  # noqa: E402
from run import summarize  # noqa: E402

BENCH_DIR = Path(__file__).parent
RESULTS_DIR = BENCH_DIR / "results"

COLUMNS = [
    ("Config", lambda r: r["name"]),
    ("Model", lambda r: f"`{r['config']['model']}`"),
    ("RAM", lambda r: f"{r['loaded_mb'] / 1024:.1f} GB" if r.get("loaded_mb") else "-"),
    ("p50", lambda r: f"{r['latency_p50']:.2f}s"),
    ("mean", lambda r: f"{r['latency_mean']:.2f}s"),
    ("p95", lambda r: f"{r['latency_p95']:.2f}s"),
    ("Score", lambda r: f"{r['score_mean']:.3f}"),
    ("Exact", lambda r: f"{r['exact_rate']:.0%}"),
    ("simple", lambda r: f"{r['score_by_tier'].get('simple', 0):.2f}"),
    ("medium", lambda r: f"{r['score_by_tier'].get('medium', 0):.2f}"),
    ("hard", lambda r: f"{r['score_by_tier'].get('hard', 0):.2f}"),
]

SORT_KEYS = {
    "latency": lambda r: r["latency_p50"],
    "score": lambda r: -r["score_mean"],
    "name": lambda r: r["name"],
}


def render_table(results: list[dict]) -> str:
    rows = [[label for label, _ in COLUMNS]]
    rows += [[fn(r) for _, fn in COLUMNS] for r in results]
    widths = [max(len(row[i]) for row in rows) for i in range(len(COLUMNS))]
    out = ["| " + " | ".join(c.ljust(w) for c, w in zip(rows[0], widths)) + " |"]
    out.append("|" + "|".join("-" * (w + 2) for w in widths) + "|")
    for row in rows[1:]:
        out.append("| " + " | ".join(c.ljust(w) for c, w in zip(row, widths)) + " |")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("names", nargs="*", help="runs to include (default: all)")
    parser.add_argument("--sort", choices=SORT_KEYS, default="latency")
    parser.add_argument("--results", type=Path, default=RESULTS_DIR)
    parser.add_argument(
        "--rescore",
        action="store_true",
        help="recompute scores from the stored predictions and rewrite the "
        "result files - use after changing latexscore.py, instead of "
        "re-running every model",
    )
    args = parser.parse_args()

    if args.names:
        paths = [args.results / f"{n}.json" for n in args.names]
        missing = [p for p in paths if not p.exists()]
        if missing:
            print("missing results: " + ", ".join(p.stem for p in missing))
            return 1
    else:
        paths = sorted(args.results.glob("*.json"))

    if not paths:
        print(f"no results in {args.results}")
        return 1

    results = [json.loads(p.read_text()) for p in paths]

    if args.rescore:
        for path, result in zip(paths, results):
            for r in result["records"]:
                if "error" in r:
                    continue
                r["score"], r["exact"] = score(r["prediction"], r["reference"])
            result.update(summarize(result["records"]))
            path.write_text(json.dumps(result, indent=2) + "\n")
        print(f"rescored {len(results)} result file(s)\n")

    if not args.names:
        results.sort(key=SORT_KEYS[args.sort])

    host = results[0].get("host", {})
    print(
        f"Hardware: {host.get('cpu', 'unknown')}, {host.get('memory_gb', '?')} GB RAM"
    )
    print(f"Corpus:   {results[0]['n']} equations\n")
    print(render_table(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
