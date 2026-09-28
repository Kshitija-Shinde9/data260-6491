import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUMMARY_PATH = os.path.join(ROOT, "reports", "hw04", "raw", "n_plus_1_summary.json")
PAGE_SIZES = [10, 50, 200]


def main():
    with open(SUMMARY_PATH) as f:
        summary = json.load(f)

    by_key = {(r["page_size"], r["version"]): r for r in summary}

    for page_size in PAGE_SIZES:
        naive = by_key.get((page_size, "naive"))
        fixed = by_key.get((page_size, "fixed"))
        if not naive or not fixed:
            print(f"page_size={page_size}: missing naive or fixed data, skipping.")
            continue

        speedup = naive["p50_ms"] / fixed["p50_ms"]
        print(
            f"page_size={page_size}: "
            f"naive p50={naive['p50_ms']}ms, "
            f"fixed p50={fixed['p50_ms']}ms, "
            f"speedup={speedup:.1f}x"
        )


if __name__ == "__main__":
    main()
