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
    # Any fence language: models have offered latex, tex, mathematica, math.
    (r"```[a-zA-Z]*", ""),
    # Page-OCR models like to wrap the answer in HTML, or hand back a whole
    # compilable document. Also catches stray chat special tokens (<|im_start|>).
    (r"<[^<>]*>", ""),
    (r"\\documentclass(\[[^\]]*\])?\{[^}]*\}", ""),
    (r"\\usepackage(\[[^\]]*\])?\{[^}]*\}", ""),
    (r"\\begin\{document\}|\\end\{document\}", ""),
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
    """`x^{2}` -> `x 2`, `{a}` -> `a`. Only safe for single-token groups.

    The replacement is space-padded on purpose: dropping the braces outright
    would turn `\\frac{d}{t}` into `\\fracdt`, which the tokenizer then reads as
    one long command. The tokenizer ignores whitespace, so the padding costs
    nothing.
    """
    prev = None
    while prev != s:
        prev = s
        s = _BRACE_RE.sub(r" \1 ", s)
    return s


# A group opening straight after one of these is decorative - there is no
# argument slot here for it to fill.
_GROUP_ANCHORS = set("=+-*/<>(),;&|[]!")

# Operator names take no argument, so `\log{x}` is just `\log x`.
_NO_ARG_COMMANDS = {
    "log",
    "ln",
    "lg",
    "exp",
    "sin",
    "cos",
    "tan",
    "cot",
    "sec",
    "csc",
    "sinh",
    "cosh",
    "tanh",
    "arcsin",
    "arccos",
    "arctan",
    "lim",
    "limsup",
    "liminf",
    "max",
    "min",
    "sup",
    "inf",
    "det",
    "dim",
    "ker",
    "deg",
    "arg",
    "gcd",
    "Pr",
    "sum",
    "prod",
    "int",
    "oint",
    "iint",
    "iiint",
}

_COMMAND_END_RE = re.compile(r"\\([a-zA-Z]+)$")


def _strip_decorative_groups(s: str) -> str:
    """Drop `{...}` groups that aren't filling an argument slot.

    Some models bracket every subexpression: `= {\\frac{1}{N}}` instead of
    `= \\frac{1}{N}`. It renders identically, and penalising it would score
    output style rather than transcription accuracy. A group is decorative
    when the token before it is an operator, a relation, an opening delimiter
    or the start of the string - never when it follows `^`, `_` or a command,
    where the braces carry meaning.
    """
    prev = None
    while prev != s:
        prev = s

        # Match every brace pair, and note what character introduced it.
        opens, pairs = [], []
        for i, ch in enumerate(s):
            if ch == "{":
                opens.append(i)
            elif ch == "}" and opens:
                pairs.append((opens.pop(), i))

        anchor_of = {}  # open index -> index of the preceding non-space char
        for start, _end in pairs:
            before = s[:start].rstrip()
            anchor_of[start] = len(before) - 1 if before else None

        # `^{...}` and `_{...}` take exactly one argument, so a group sitting
        # right after one of them is filling no slot.
        script_close = {
            end
            for start, end in pairs
            if anchor_of[start] is not None and s[anchor_of[start]] in "^_"
        }

        drop = set()
        for start, end in pairs:
            at = anchor_of[start]
            if at is None or s[at] in _GROUP_ANCHORS or at in script_close:
                drop |= {start, end}
                continue
            command = _COMMAND_END_RE.search(s[: at + 1])
            if command and command.group(1) in _NO_ARG_COMMANDS:
                drop |= {start, end}

        if drop:
            s = "".join(" " if i in drop else c for i, c in enumerate(s))
            s = re.sub(r"\s+", " ", s)
    return s


def normalize(latex: str) -> str:
    """Cosmetic cleanup. Whitespace is collapsed but not dropped, because
    `\\sin x` and `\\sinx` are not the same thing; the tokenizer handles the
    rest."""
    s = latex.strip()
    for pattern, repl in _SUBSTITUTIONS:
        s = re.sub(pattern, repl, s)
    s = re.sub(r"\s+", " ", s)
    # Decorative groups go first: unwrapping `^{\infty}` to `^ \infty` would
    # erase the evidence that the superscript's one argument slot is filled.
    s = _strip_decorative_groups(s)
    s = _strip_redundant_braces(s)
    s = _strip_decorative_groups(s)
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
