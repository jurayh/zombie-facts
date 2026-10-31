#!/usr/bin/env python3
"""Run the Zombie Facts offline spike and write results/zombie_rates.{json,md}."""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from zombie_facts.harness import render_markdown, run

if __name__ == "__main__":
    res = run()
    out = pathlib.Path(__file__).parent / "results"
    out.mkdir(exist_ok=True)
    (out / "zombie_rates.json").write_text(json.dumps(res, indent=2, sort_keys=True) + "\n")
    (out / "zombie_rates.md").write_text(render_markdown(res))
    print(render_markdown(res))
