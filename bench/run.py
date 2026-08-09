"""Run the SnapTeX benchmark against one or more configurations.

    uv run bench/render.py                 # once, to build the corpus
    uv run bench/run.py --list             # what's configured
    uv run bench/run.py qwen3-vl-4b        # run one entry
    uv run bench/run.py --all              # run everything

Configurations live in bench/configs.toml. Add your own entry there and it
shows up here; nothing in this file needs to change.

Results are written to bench/results/<name>.json. Build the comparison table
with `uv run bench/report.py`.
"""

import argparse
import base64
import io
import json
import platform
import statistics
import subprocess
import sys
import time
import tomllib
from pathlib import Path

import httpx
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from latexscore import score  # noqa: E402

BENCH_DIR = Path(__file__).parent
CONFIG_FILE = BENCH_DIR / "configs.toml"
MANIFEST_FILE = BENCH_DIR / "corpus" / "manifest.json"
RESULTS_DIR = BENCH_DIR / "results"

DEFAULT_PROMPT = "Convert this equation to LaTeX. Output ONLY the raw LaTeX string."


def encode_image(path: Path, max_px: int | None, min_px: int | None) -> str:
    """PNG -> base64, with the longest side clamped into [min_px, max_px].

    Both directions matter. Downscaling cuts the visual token count on servers
    that do dynamic resolution; upscaling raises it, which is how you buy
    accuracy back on a small screenshot. Ollama ignores both - it resizes
    everything to a fixed grid - but mlx-vlm honours the real Qwen3-VL
    dynamic-resolution behaviour.
    """
    img = Image.open(path).convert("RGB")
    longest = max(img.size)
    scale = 1.0
    if max_px and longest > max_px:
        scale = max_px / longest
    elif min_px and longest < min_px:
        scale = min_px / longest
    if scale != 1.0:
        img = img.resize(
            (max(1, round(img.width * scale)), max(1, round(img.height * scale))),
            Image.LANCZOS,
        )
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def call_ollama(client, cfg, image_b64):
    """Ollama's native endpoint, which accepts the full `options` block."""
    body = {
        "model": cfg["model"],
        "messages": [{"role": "user", "content": cfg["prompt"], "images": [image_b64]}],
        "stream": False,
        "keep_alive": cfg.get("keep_alive", "10m"),
        "options": cfg.get("options", {}),
    }
    # Hybrid reasoning models (qwen3.5, ...) otherwise spend the whole token
    # budget thinking about a one-line transcription and return empty content.
    if "think" in cfg:
        body["think"] = cfg["think"]
    r = client.post(f"{cfg['base_url'].rstrip('/')}/api/chat", json=body)
    r.raise_for_status()
    data = r.json()
    return data["message"]["content"], {
        "prompt_tokens": data.get("prompt_eval_count"),
        "output_tokens": data.get("eval_count"),
        "load_ns": data.get("load_duration"),
        "prompt_eval_ns": data.get("prompt_eval_duration"),
        "eval_ns": data.get("eval_duration"),
    }


def call_openai(client, cfg, image_b64):
    """Anything speaking /v1/chat/completions (mlx-vlm, llama-server, vLLM...)."""
    body = {
        "model": cfg["model"],
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": cfg["prompt"]},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                    },
                ],
            }
        ],
        "stream": False,
        **cfg.get("options", {}),
    }
    r = client.post(f"{cfg['base_url'].rstrip('/')}/v1/chat/completions", json=body)
    r.raise_for_status()
    data = r.json()
    usage = data.get("usage") or {}
    return data["choices"][0]["message"]["content"], {
        "prompt_tokens": usage.get("prompt_tokens"),
        "output_tokens": usage.get("completion_tokens"),
    }


CALLERS = {"ollama": call_ollama, "openai": call_openai}


def reset_model(cfg) -> None:
    """Unload the model so its cached image embeddings go with it.

    Ollama keeps the vision encoder's output per image for as long as the
    model stays resident: re-sending the same screenshot costs 0.005s of
    prefill instead of 0.44s. That is lovely in a chat loop and completely
    unrepresentative here - every SnapTeX conversion is a screenshot the
    server has never seen. Without this, whichever config happens to run
    second over the same corpus looks three times faster than the one before
    it.
    """
    if cfg.get("engine") == "ollama":
        subprocess.run(["ollama", "stop", cfg["model"]], capture_output=True)


def resident_size_mb(cfg) -> float | None:
    """How much memory the model is actually holding, per `ollama ps`."""
    if cfg.get("engine") != "ollama":
        return None
    try:
        out = subprocess.run(
            ["ollama", "ps"], capture_output=True, text=True, check=True
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    for line in out.splitlines()[1:]:
        parts = line.split()
        if parts and parts[0] == cfg["model"]:
            # columns: NAME ID SIZE UNIT PROCESSOR ...
            try:
                value, unit = float(parts[2]), parts[3].upper()
            except (IndexError, ValueError):
                return None
            return value * 1024 if unit.startswith("GB") else value
    return None


def run_config(
    name: str,
    cfg: dict,
    samples: list[dict],
    warmup_image: str,
    warmup: int,
    repeats: int,
) -> dict:
    caller = CALLERS[cfg.get("engine", "ollama")]
    timeout = cfg.get("timeout", 300)
    max_px, min_px = cfg.get("max_px"), cfg.get("min_px")

    encoded = {
        s["id"]: encode_image(BENCH_DIR / s["image"], max_px, min_px) for s in samples
    }
    # Deliberately an image that is not in the corpus, so the server's prompt
    # cache can't hand the first timed samples a free prefill.
    encoded_warmup = encode_image(BENCH_DIR / warmup_image, max_px, min_px)

    with httpx.Client(timeout=timeout) as client:
        loaded_mb = None
        records = []
        for rep in range(repeats):
            # Each pass starts cold, otherwise pass 2 would be scoring the
            # image cache rather than the model.
            if cfg.get("reset", True):
                reset_model(cfg)
            print(f"[{name}] warming up ({warmup} calls)...", flush=True)
            for _ in range(warmup):
                caller(client, cfg, encoded_warmup)

            # Measured after warmup, so the model is loaded and the vision
            # tower has actually been touched.
            loaded_mb = loaded_mb or resident_size_mb(cfg)

            for s in samples:
                t0 = time.perf_counter()
                try:
                    text, meta = caller(client, cfg, encoded[s["id"]])
                except Exception as e:  # a failed call is a zero, not a crash
                    print(f"  {s['id']}: ERROR {type(e).__name__}: {e}", flush=True)
                    records.append(
                        {
                            "id": s["id"],
                            "tier": s["tier"],
                            "style": s["style"],
                            "repeat": rep,
                            "latency_s": time.perf_counter() - t0,
                            "score": 0.0,
                            "exact": False,
                            "prediction": "",
                            "error": f"{type(e).__name__}: {e}",
                        }
                    )
                    continue
                latency = time.perf_counter() - t0
                sim, exact = score(text, s["latex"])
                records.append(
                    {
                        "id": s["id"],
                        "tier": s["tier"],
                        "style": s["style"],
                        "repeat": rep,
                        "latency_s": latency,
                        "score": sim,
                        "exact": exact,
                        "prediction": text.strip(),
                        "reference": s["latex"],
                        **meta,
                    }
                )
                print(f"  {s['id']:<24} {latency:5.2f}s  {sim:.3f}", flush=True)

    return {
        "name": name,
        "config": cfg,
        "loaded_mb": loaded_mb,
        "records": records,
        **summarize(records),
    }


def summarize(records: list[dict]) -> dict:
    lat = sorted(r["latency_s"] for r in records)
    scores = [r["score"] for r in records]
    tiers = {}
    for r in records:
        tiers.setdefault(r["tier"], []).append(r["score"])
    out_tokens = [r["output_tokens"] for r in records if r.get("output_tokens")]
    return {
        "n": len(records),
        "latency_mean": statistics.fmean(lat),
        "latency_p50": statistics.median(lat),
        "latency_p95": lat[min(len(lat) - 1, round(0.95 * len(lat)))],
        "score_mean": statistics.fmean(scores),
        "exact_rate": sum(r["exact"] for r in records) / len(records),
        "error_rate": sum("error" in r for r in records) / len(records),
        "score_by_tier": {t: statistics.fmean(v) for t, v in sorted(tiers.items())},
        "output_tokens_mean": statistics.fmean(out_tokens) if out_tokens else None,
    }


def host_info() -> dict:
    def sysctl(key):
        try:
            return subprocess.run(
                ["sysctl", "-n", key], capture_output=True, text=True, check=True
            ).stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

    info = {"platform": platform.platform(), "python": platform.python_version()}
    if platform.system() == "Darwin":
        info["cpu"] = sysctl("machdep.cpu.brand_string")
        mem = sysctl("hw.memsize")
        info["memory_gb"] = round(int(mem) / 1024**3) if mem else None
    return info


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("names", nargs="*", help="config entries to run")
    parser.add_argument("--all", action="store_true", help="run every entry")
    parser.add_argument("--list", action="store_true", help="list entries and exit")
    parser.add_argument("--config", type=Path, default=CONFIG_FILE)
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument("--repeats", type=int, default=1, help="passes over the corpus")
    parser.add_argument(
        "--limit", type=int, help="only the first N samples (for smoke tests)"
    )
    parser.add_argument("--tier", help="restrict to one difficulty tier")
    args = parser.parse_args()

    raw = tomllib.loads(args.config.read_text())
    defaults = raw.get("defaults", {})
    prompts = raw.get("prompts", {})
    engine_defaults = {e: defaults.get(e, {}) for e in CALLERS}
    shared = {k: v for k, v in defaults.items() if k not in CALLERS}

    entries = {}
    for name, cfg in raw.get("run", {}).items():
        engine = cfg.get("engine", shared.get("engine", "ollama"))
        if engine not in CALLERS:
            parser.error(f"{name}: unknown engine '{engine}'")
        base = engine_defaults[engine]
        merged = {**shared, **base, **cfg, "engine": engine}
        merged["options"] = {**base.get("options", {}), **cfg.get("options", {})}
        prompt_id = merged.get("prompt_id")
        if prompt_id and prompt_id not in prompts:
            parser.error(f"{name}: unknown prompt_id '{prompt_id}'")
        merged["prompt"] = prompts.get(prompt_id, DEFAULT_PROMPT).strip()
        entries[name] = merged

    if args.list:
        width = max(len(n) for n in entries)
        for name, cfg in entries.items():
            print(f"{name:<{width}}  {cfg.get('engine', 'ollama'):<7} {cfg['model']}")
        return 0

    selected = list(entries) if args.all else args.names
    if not selected:
        parser.error("give one or more config names, or --all (see --list)")
    unknown = [n for n in selected if n not in entries]
    if unknown:
        parser.error(f"unknown config(s): {', '.join(unknown)}")

    if not MANIFEST_FILE.exists():
        print("error: corpus not rendered yet. Run: uv run bench/render.py")
        return 1
    manifest = json.loads(MANIFEST_FILE.read_text())
    samples = manifest["samples"]
    if args.tier:
        samples = [s for s in samples if s["tier"] == args.tier]
    if args.limit:
        samples = samples[: args.limit]

    RESULTS_DIR.mkdir(exist_ok=True)
    host = host_info()

    for name in selected:
        result = run_config(
            name,
            entries[name],
            samples,
            manifest["warmup"],
            args.warmup,
            args.repeats,
        )
        result["host"] = host
        result["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        (RESULTS_DIR / f"{name}.json").write_text(json.dumps(result, indent=2) + "\n")
        print(
            f"[{name}] p50 {result['latency_p50']:.2f}s  mean {result['latency_mean']:.2f}s  "
            f"score {result['score_mean']:.3f}  exact {result['exact_rate']:.0%}\n",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
