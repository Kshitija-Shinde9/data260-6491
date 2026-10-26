import csv
from pathlib import Path

OUT = Path("reports/hw07/part4/scenarios")
FIELDS = ["started_at", "duration_minutes", "ride_id"]


def write(name, count, duration, months):
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / name).open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for i in range(count):
            month = 1 + (i % months)
            week = 1 + (i % 4)
            year = 2026 + ((month - 1) // 12)
            month_in_year = 1 + ((month - 1) % 12)
            w.writerow(
                {
                    "started_at": f"{year:04d}-{month_in_year:02d}-{week:02d}T08:00:00",
                    "duration_minutes": duration(i),
                    "ride_id": i + 1,
                }
            )


write("membership_wins.csv", 600, lambda i: 30 + (i % 35), 4)
write("payg_wins.csv", 600, lambda i: 8 + (i % 8), 96)
print(f"Wrote {OUT / 'membership_wins.csv'} and {OUT / 'payg_wins.csv'}")
