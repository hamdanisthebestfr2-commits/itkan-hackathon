"""Accuracy test: python eval/run_eval.py

Put card photos in eval/cards/ (cardNN.jpg) with a matching cardNN.json holding the
true values, e.g. {"full_name": "Jhon Harzorwick", "bp_systolic": "120", "notes": null, ...}.
Only fields listed in the .json are scored.

Reports the numbers that matter for the pitch:
- field accuracy (AI value == truth)
- wrong values that were flagged for review (caught) vs. not flagged (slipped through)
"""
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import reader, validate  # noqa: E402

CARDS = Path(__file__).parent / "cards"


def norm(v) -> str:
    return reader._norm(None if v is None else str(v))


async def main():
    images = sorted(p for p in CARDS.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png"))
    total = correct = caught = slipped = 0
    times = []
    for img in images:
        truth_path = img.with_suffix(".json")
        if not truth_path.exists():
            print(f"skip {img.name}: no {truth_path.name}")
            continue
        truth = json.loads(truth_path.read_text())
        started = time.time()
        result = validate.review(await reader.read_card(reader.prepare_image(img.read_bytes())))
        times.append(time.time() - started)
        print(f"\n{img.name}  ({times[-1]:.1f}s)")
        for key, expected in truth.items():
            f = result["fields"][key]
            total += 1
            # compare against the normalized truth (e.g. "678 999 3218" -> "678-999-3218")
            expected_norm, _ = validate._normalize(validate.FIELD_BY_KEY[key], expected)
            if norm(f["value"]) == norm(expected_norm):
                correct += 1
                continue
            flagged = f["status"] in ("check", "missing")
            caught += flagged
            slipped += not flagged
            mark = "caught (flagged)" if flagged else "SLIPPED THROUGH"
            print(f"  {key:20} read {f['value']!r:22} truth {expected!r:22} {mark}")

    if not total:
        print("No scored cards found in eval/cards/")
        return
    wrong = total - correct
    print("\n================ RESULTS ================")
    print(f"Cards:              {len(times)}")
    print(f"Fields scored:      {total}")
    print(f"Field accuracy:     {100 * correct / total:.1f}%  ({correct}/{total})")
    if wrong:
        print(f"Errors caught:      {100 * caught / wrong:.0f}% of wrong values were flagged for review ({caught}/{wrong})")
    print(f"Slipped through:    {slipped}  (wrong AND not flagged)")
    print(f"Avg time per card:  {sum(times) / len(times):.1f}s")


asyncio.run(main())
