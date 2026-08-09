# SnapTeX benchmark

A small, controlled harness for answering "which model and settings should
SnapTeX actually use?" It measures the two things that matter: how long a
conversion takes, and how much of the equation survives it.

## Running it

```bash
uv sync --group bench
uv run bench/render.py            # build the corpus, once
uv run bench/run.py --list        # what's configured
uv run bench/run.py qwen3vl-4b    # benchmark one config
uv run bench/run.py --all         # benchmark everything
uv run bench/report.py            # print the comparison table
```

`render.py` needs `latex` and `dvipng` on your PATH (MacTeX, TeX Live, MiKTeX).
The images it produces aren't checked in — they're derived from
`corpus/equations.txt` and regenerate in a few seconds.

## Adding your own model

Copy a block in [`configs.toml`](configs.toml):

```toml
[run.my-model]
model = "some-model:7b"
```

and run `uv run bench/run.py my-model`. Anything Ollama can serve works out of
the box. For a different server, set `engine = "openai"` and point `base_url`
at it — that path speaks plain `/v1/chat/completions`, so mlx-vlm, llama-server,
vLLM, SGLang and the hosted APIs all work.

Results land in `bench/results/<name>.json`, one file per config, including
every individual prediction so you can go read what the model actually got
wrong.

## The corpus

40 equations in [`corpus/equations.txt`](corpus/equations.txt), split into three
tiers:

- **simple** (10) — one-liners: `E = mc^2`, the quadratic formula, a limit
- **medium** (15) — integrals, sums, partial derivatives, script/blackboard
  letters, nested fractions
- **hard** (15) — matrices, `cases`, multi-line constructs, tensor indices,
  the Schrödinger and Einstein field equations

Each is rendered by real LaTeX through `dvipng`, cycling through five styles so
the benchmark isn't just one pristine render: a 200 DPI retina grab, a normal
140 DPI one, a small 100 DPI `\small` one, a large off-white one, and a
dark-mode one. That spread matters — the low-DPI and dark samples are where
the small models start falling over.

Because the images are generated *from* the LaTeX, the ground truth is exact by
construction. No hand-labelling, no scraped dataset of dubious quality.

## How accuracy is scored

LaTeX has no canonical form. `\frac{1}{2}`, `\dfrac{1}{2}` and `\frac 1 2` all
render identically, and `\left(` vs `(` is not a mistake. So
[`latexscore.py`](latexscore.py) normalises away the differences that don't
change what you see — math delimiters, markdown fences, `\left`/`\right`,
spacing macros, redundant braces around single tokens, `\mathrm` vs `\text` —
then compares what's left token by token:

```
score = 1 - (token edit distance / length of the longer sequence)
```

Differences that *do* change the rendered output are left alone and counted as
errors: `\cdot` vs `\times`, `\epsilon` vs `\varepsilon`, `pmatrix` vs
`bmatrix`.

Two numbers come out:

- **score** — the headline number, mean similarity in [0, 1]. Roughly "what
  fraction of the expression came back correct."
- **exact** — the share of outputs that matched perfectly after normalisation.
  Useful as a sanity check, but brittle; one stray brace on a long equation
  takes it to zero while `score` still reads 0.97.

This is not a research-grade metric and isn't trying to be. It's stable enough
to rank configurations, which is all it needs to do.

## Timing

Latency is measured client-side, end to end: the clock starts before the
request is built and stops when the response is parsed. That's what you
actually wait for after pressing the hotkey, including image encoding and HTTP
overhead.

Every config gets warmup calls first (2 by default) so the model is loaded and
the first-token penalty isn't counted, and `p50`/`p95` are reported alongside
the mean because the mean hides the tail — and the tail is what you notice.

Useful flags: `--repeats N` for more passes over the corpus (tighter numbers,
longer runs), `--limit N` and `--tier simple` for quick smoke tests.
