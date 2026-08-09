"""Render the ground-truth equations in corpus/equations.txt to PNGs.

Uses a real LaTeX install (latex + dvipng) so the images look like something you
would actually screenshot out of a paper, and so the ground truth is exact by
construction.

    uv run bench/render.py

Styles are cycled over the corpus so the benchmark covers a spread of
resolutions, sizes and colour schemes rather than one pristine render.
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path

BENCH_DIR = Path(__file__).parent
CORPUS_FILE = BENCH_DIR / "corpus" / "equations.txt"
IMAGE_DIR = BENCH_DIR / "corpus" / "images"
MANIFEST_FILE = BENCH_DIR / "corpus" / "manifest.json"


@dataclass(frozen=True)
class Style:
    name: str
    dpi: int
    size: str  # LaTeX size command
    fg: str  # dvipng colour spec
    bg: str


# The DPI values are chosen so the resulting pixel sizes match what you
# actually get from a screenshot tool. A 12pt display equation grabbed off a
# Retina screen at normal reading zoom lands around 60px of line height, which
# is 12/72 * 360 DPI; the rest are scaled around that.
#
# Roughly: a Retina PDF viewer, a normal 1x display, a zoomed-out page you
# cropped in a hurry, a large-print slide, and a dark-mode reader.
STYLES = [
    Style("retina", 600, r"\normalsize", "rgb 0 0 0", "rgb 1 1 1"),
    Style("normal", 360, r"\normalsize", "rgb 0 0 0", "rgb 1 1 1"),
    Style("small", 200, r"\small", "rgb 0 0 0", "rgb 1 1 1"),
    Style("large", 480, r"\large", "rgb 0.1 0.1 0.1", "rgb 0.97 0.97 0.95"),
    Style("dark", 380, r"\normalsize", "rgb 0.9 0.9 0.9", "rgb 0.12 0.12 0.14"),
]

# Not part of the corpus: used to warm the server up without poisoning the
# timed run through the prompt cache.
WARMUP_EQUATION = r"\int_a^b f(x)\,dx = F(b) - F(a)"

TEMPLATE = r"""\documentclass[12pt]{article}
\usepackage{amsmath,amssymb,amsfonts,bm}
\pagestyle{empty}
\begin{document}
%(size)s
\[
%(equation)s
\]
\end{document}
"""


@dataclass
class Sample:
    id: str
    tier: str
    style: str
    latex: str
    image: str


def parse_corpus(path: Path) -> list[tuple[str, str]]:
    """Return (tier, latex) pairs."""
    tier = "default"
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("@tier "):
            tier = line[len("@tier ") :].strip()
            continue
        out.append((tier, line))
    return out


def render(equation: str, style: Style, out_path: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "eq.tex").write_text(
            TEMPLATE % {"size": style.size, "equation": equation}
        )
        subprocess.run(
            ["latex", "-interaction=nonstopmode", "-halt-on-error", "eq.tex"],
            cwd=tmp,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "dvipng",
                "-T",
                "tight",
                "-D",
                str(style.dpi),
                "-fg",
                style.fg,
                "-bg",
                style.bg,
                "-q",
                "-z",
                "9",
                "--png",
                "-o",
                str(out_path),
                "eq.dvi",
            ],
            cwd=tmp,
            check=True,
            capture_output=True,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=CORPUS_FILE)
    parser.add_argument("--out", type=Path, default=IMAGE_DIR)
    args = parser.parse_args()

    for tool in ("latex", "dvipng"):
        if shutil.which(tool) is None:
            print(
                f"error: '{tool}' not found. Install a LaTeX distribution (MacTeX/TeX Live)."
            )
            return 1

    equations = parse_corpus(args.corpus)
    if not equations:
        print(f"error: no equations found in {args.corpus}")
        return 1

    if args.out.exists():
        shutil.rmtree(args.out)
    args.out.mkdir(parents=True)

    samples = []
    for i, (tier, latex) in enumerate(equations):
        style = STYLES[i % len(STYLES)]
        sample_id = f"{i:03d}_{tier}_{style.name}"
        image = args.out / f"{sample_id}.png"
        try:
            render(latex, style, image)
        except subprocess.CalledProcessError as e:
            print(f"failed to render {sample_id}: {latex}")
            print(e.stdout.decode(errors="replace")[-2000:])
            return 1
        samples.append(
            Sample(
                sample_id, tier, style.name, latex, str(image.relative_to(BENCH_DIR))
            )
        )
        print(f"  {sample_id}")

    warmup = args.out / "warmup.png"
    render(WARMUP_EQUATION, STYLES[1], warmup)
    print("  warmup")

    MANIFEST_FILE.write_text(
        json.dumps(
            {
                "styles": [asdict(s) for s in STYLES],
                "warmup": str(warmup.relative_to(BENCH_DIR)),
                "samples": [asdict(s) for s in samples],
            },
            indent=2,
        )
        + "\n"
    )
    print(f"\nrendered {len(samples)} equations -> {args.out}")
    print(f"manifest: {MANIFEST_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
