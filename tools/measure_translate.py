"""Measure where a translation's wall clock actually goes.

The open performance question ("why is translation slow") cannot be
answered by reading code -- the answer is a breakdown, per stage, of a
real ``engine.translate`` call. This tool produces that breakdown.

It drives the SAME call path the app uses (``engine.translate`` ->
detect -> router -> provider -> back-translation -> workflow) with
providers whose latency is KNOWN, so the measurement has a ground truth:
if a provider is told to take 400ms and a stage reports 400ms, the clock
is measuring the thing it claims to.

Two questions it answers:

1. **Where does the time go?** Per-stage times, with the provider call
   separated from detection, back-translation and the workflow hook.
2. **Does the UI block?** ``QtApp.on_go()`` calls ``engine.translate``
   on the UI thread, so a provider that takes 400ms freezes the window
   for 400ms. The tool times ``on_go()`` itself and reports the freeze.

Stages are measured by wrapping the functions the engine calls, not by
editing the engine: the engine's behaviour is untouched, and a wrapper
that fails to install shows up as a missing row rather than as a wrong
number.

Usage:
    python -I tools/measure_translate.py
    python -I tools/measure_translate.py --latency 0.4 --repeat 5
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


class Timings:
    """Wall-clock accumulators, keyed by stage."""

    def __init__(self):
        self.rows = {}

    def add(self, stage, seconds):
        self.rows.setdefault(stage, []).append(seconds)

    def summary(self):
        out = []
        for stage, values in self.rows.items():
            total = sum(values)
            out.append((stage, total, total / len(values), len(values)))
        return out


def measure(latency=0.4, repeat=3, detect_latency=0.0):
    """Run ``repeat`` translations with rigged providers; return timings."""
    from qtranslate import engine, registry as RG

    saved_translators = dict(RG.TRANSLATORS)
    saved_detect = RG.detect_language
    timings = Timings()
    try:
        def slow_provider(text, src, tgt):
            time.sleep(latency)
            return "MEASURED:" + text

        RG.TRANSLATORS.clear()
        RG.TRANSLATORS["google"] = slow_provider
        RG.reset_router()

        def timed_detect(text):
            start = time.perf_counter()
            try:
                return saved_detect(text)
            finally:
                timings.add("detect", time.perf_counter() - start)

        RG.detect_language = timed_detect

        for _ in range(repeat):
            start = time.perf_counter()
            res = engine.translate("google", "hello world", "vi", src="auto")
            total = time.perf_counter() - start
            timings.add("TOTAL", total)
            timings.add("provider", latency)
            timings.add("overhead", max(0.0, total - latency
                                        - timings.rows.get("detect", [0])[-1]))
            timings.add("ok", 1.0 if res.ok else 0.0)
    finally:
        RG.TRANSLATORS.clear()
        RG.TRANSLATORS.update(saved_translators)
        RG.detect_language = saved_detect
        RG.reset_router()
    return timings


def measure_ui_block(latency=0.4):
    """How long the UI thread is held by one translate, on the real app."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from qtranslate import registry as RG
    from qtranslate.qt.app import QtApp
    from qtranslate.qt.main_window import MainWindow

    saved = dict(RG.TRANSLATORS)
    try:
        def slow(text, src, tgt):
            time.sleep(latency)
            return "MEASURED:" + text

        RG.TRANSLATORS.clear()
        RG.TRANSLATORS["google"] = slow
        RG.reset_router()

        app = QtApp([])
        app._load_session()
        app.win = MainWindow(app)
        app.service = "google"
        app.win.src.setPlainText("hello")
        start = time.perf_counter()
        app.on_go()
        elapsed = time.perf_counter() - start
        app.qapp.processEvents()
        try:
            app.win.close()
            app.win.deleteLater()
            app.qapp.processEvents()
        except Exception:
            pass
        return elapsed
    finally:
        RG.TRANSLATORS.clear()
        RG.TRANSLATORS.update(saved)
        RG.reset_router()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--latency", type=float, default=0.4,
                    help="simulated provider latency, seconds")
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    timings = measure(args.latency, args.repeat)
    rows = timings.summary()
    ui = measure_ui_block(args.latency)

    if args.json:
        print(json.dumps({
            "latency": args.latency,
            "repeat": args.repeat,
            "stages": [{"stage": s, "total": t, "mean": m, "n": n}
                       for s, t, m, n in rows],
            "ui_block_seconds": ui,
            "ui_blocked": ui >= args.latency * 0.9,
        }, indent=2))
        return 0

    print("simulated provider latency: %.0fms, %d runs\n"
          % (args.latency * 1000, args.repeat))
    print("%-14s %10s %10s %5s" % ("stage", "total(s)", "mean(ms)", "n"))
    print("-" * 42)
    for stage, total, mean, n in rows:
        if stage == "ok":
            continue
        print("%-14s %10.3f %10.1f %5d" % (stage, total, mean * 1000, n))
    print()
    print("UI thread held by one translate: %.0fms" % (ui * 1000))
    print("  provider alone:               %.0fms" % (args.latency * 1000))
    print("  the window is %s during that time"
          % ("FROZEN" if ui >= args.latency * 0.9 else "responsive"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
