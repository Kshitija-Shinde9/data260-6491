# DOMAIN_SCHEMA.md

## Domain: Grocery Supply and Recall Notices
## DOMAIN_ID: 3
## SID4: 6491

This file defines the fields and category values used in the grocery recall report form built for Part 1 (HTML and JavaScript).

---

## Entity: Grocery supply and recall notices

### Fields

**1. Product Name** (Primary Field)
- Type: required text input
- Placeholder: "e.g. Trader Joe's Organic Frozen Blueberries, 16oz"
- Behavior: cursor auto-focuses here when the page loads
- Example value: `Trader Joe's Organic Frozen Blueberries, 16oz`

**2. Supplier / Brand** (Secondary Field)
- Type: required text input
- Placeholder: "who made or supplied it"
- Example value: `Trader Joe's (Stevens Creek location)`

**3. Submitter Email**
- Type: required email input
- Placeholder: "your email so we can follow up"
- Example value: `rohan1@gmail.com`

**4. Recall Reason / Description** (Content Field)
- Type: required textarea
- Placeholder: "what happened, when you noticed it, any batch/lot info"
- Validation rule: must be more than 25 characters (enforced in JavaScript)
- Example value:
  `"grabbed this from the TJ's on Stevens Creek, didn't notice till i got home that the bag had a small tear near the top seal, right where it's supposed to be sealed shut. bunch of the berries at the top were already a little frosted/clumped together like air got in. didn't want to risk it so i didn't open the rest, but the tear looked like it was there before i even picked it up off the shelf"`

**5. Recall Reason Type** (Category Dropdown - 4 options)
- Type: select dropdown, required
- Options:
  1. Packaging / Seal Failure
  2. Contamination
  3. Undeclared Allergen
  4. Spoiled or Quality Issue

**6. Terms Agreement**
- Type: checkbox, required
- Label text: "I agree to the terms and conditions."
- Validation rule: must be checked before submission (enforced in JavaScript)

**7. Submit Button**
- Text: "Report This Recall"

---

## Notes
- All fields marked "required" must have the HTML `required` attribute.
- Field 4 (description) and Field 6 (checkbox) are validated using an arrow-function JavaScript validator before allowing submission.
- This schema is the blueprint for the HTML form built in Part 1, Question I.4.