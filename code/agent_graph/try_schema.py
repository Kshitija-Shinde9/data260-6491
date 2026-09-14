# A small script to check my rulebook catches the mistakes it should.

from schema import validate_planner_output

examples = [
    ("GOOD - 3 tags, right lengths, short summary", {
        "tags": ["torn packaging seal", "frozen berry recall", "frost damage"],
        "summary": "Blueberries recalled because the bag seal was torn and frost got in.",
    }),
    ("BAD - only 2 tags", {
        "tags": ["torn packaging seal", "frost damage"],
        "summary": "Blueberries recalled because the seal was torn.",
    }),
    ("BAD - 4 tags", {
        "tags": ["one tag", "two tag", "three tag", "four tag"],
        "summary": "Blueberries recalled because the seal was torn.",
    }),
    ("BAD - a tag that is too short", {
        "tags": ["ok", "frozen berry recall", "frost damage"],
        "summary": "Blueberries recalled because the seal was torn.",
    }),
    ("BAD - a tag that is too long", {
        "tags": ["this tag is far too long to be allowed by my rules", "frozen berry recall", "frost damage"],
        "summary": "Blueberries recalled because the seal was torn.",
    }),
    ("BAD - summary longer than 25 words", {
        "tags": ["torn packaging seal", "frozen berry recall", "frost damage"],
        "summary": ("The Trader Joe's organic frozen blueberries in the sixteen ounce bag have "
                    "been recalled because the seal at the top of the packaging was found to "
                    "be torn which let air inside and caused frost to build up on the fruit"),
    }),
]

print("Checking my rulebook against good and bad examples")
print("=" * 60)

for name, data in examples:
    ok, problem = validate_planner_output(data)
    print(f"\n{name}")
    if ok:
        print("   PASSED the rules")
    else:
        print(f"   REJECTED: {problem}")
