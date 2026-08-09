"""Scoring LaTeX OCR output against a ground-truth string.

There is no single right answer in LaTeX: `\\frac{1}{2}`, `\\dfrac{1}{2}` and
`\\frac 1 2` all render identically, and a model that writes `\\left(` where the
reference writes `(` has not made a mistake. So we normalise away the
differences that don't change what you see on screen, then compare the
remainder token by token.

Two numbers come out of it:

  exact    - 1.0 if the normalised strings match character for character
  score    - 1 - (token edit distance / length), i.e. how much of the
             expression survived, in [0, 1]

`score` is the one to look at. `exact` is a useful sanity check but it's
brittle: one stray brace drops it to zero, which tells you nothing about
whether the output was usable.

Deliberately *not* normalised: things that change the rendered output, like
\\cdot vs \\times, \\epsilon vs \\varepsilon, or pmatrix vs bmatrix. Those are
real errors even if they're small ones.
"""

import re

# (pattern, replacement) applied in order. All of these are cosmetic: the
# rendered result is identical before and after.
_SUBSTITUTIONS = [
    # Markdown fences and math delimiters the model may wrap the answer in.
    (r"```(?:latex|tex)?", ""),
    (r"\\begin\{(?:equation|displaymath|math|align)\*?\}", ""),
    (r"\\end\{(?:equation|displaymath|math|align)\*?\}", ""),
    (r"\\\[|\\\]|\\\(|\\\)", ""),
    (r"\$+", ""),
    # Sizing and spacing that carries no meaning.
    (
        r"\\left\b|\\right\b|\\big[lrm]?\b|\\Big[lrm]?\b|\\bigg[lrm]?\b|\\Bigg[lrm]?\b",
        "",
    ),
    (r"\\displaystyle\b|\\textstyle\b|\\limits\b|\\nolimits\b", ""),
    (r"\\[,;:!]|\\quad\b|\\qquad\b|\\ (?=\S)", " "),
    (r"~", " "),
    # Equivalent spellings.
    (r"\\dfrac\b|\\tfrac\b", r"\\frac"),
    (r"\\mathrm\b|\\textrm\b|\\textnormal\b", r"\\text"),
    (r"\\bm\b|\\boldsymbol\b|\\mathbf\b", r"\\mathbf"),
    (r"\\ge\b", r"\\geq"),
    (r"\\le\b", r"\\leq"),
    (r"\\ne\b", r"\\neq"),
    (r"\\to\b", r"\\rightarrow"),
    (r"\\vert\b", "|"),
    (r"\\Vert\b", r"\\|"),
    (r"\\ast\b", "*"),
    (r"\\lbrace\b", r"\\{"),
    (r"\\rbrace\b", r"\\}"),
]

_TOKEN_RE = re.compile(r"\\[a-zA-Z]+|\\.|[^\s]")


_BRACE_RE = re.compile(r"\{\s*(\\[a-zA-Z]+|[^{}\\\s])\s*\}")


def _strip_redundant_braces(s: str) -> str:
    """`x^{2}` -> `x^2`, `{a}` -> `a`. Only safe for single-token groups."""
    prev = None
    while prev != s:
        prev = s
        s = _BRACE_RE.sub(r"\1", s)
    return s


def normalize(latex: str) -> str:
    """Cosmetic cleanup. Whitespace is collapsed but not dropped, because
    `\\sin x` and `\\sinx` are not the same thing; the tokenizer handles the
    rest."""
    s = latex.strip()
    for pattern, repl in _SUBSTITUTIONS:
        s = re.sub(pattern, repl, s)
    s = re.sub(r"\s+", " ", s)
    s = _strip_redundant_braces(s)
    return s.strip()


def tokenize(latex: str) -> list[str]:
    return _TOKEN_RE.findall(latex)


def edit_distance(a: list[str], b: list[str]) -> int:
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def score(prediction: str, reference: str) -> tuple[float, bool]:
    """Return (similarity in [0, 1], exact match)."""
    pred_t = tokenize(normalize(prediction))
    ref_t = tokenize(normalize(reference))
    if pred_t == ref_t:
        return 1.0, True
    if not ref_t:
        return 0.0, False
    dist = edit_distance(pred_t, ref_t)
    return max(0.0, 1.0 - dist / max(len(pred_t), len(ref_t))), False
