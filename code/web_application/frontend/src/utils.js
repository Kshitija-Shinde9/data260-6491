export function chipClass(recallType) {
  if (!recallType) return "";
  if (recallType.includes("Seal")) return "chip-seal";
  if (recallType.includes("Contamination")) return "chip-contam";
  if (recallType.includes("Allergen")) return "chip-allergen";
  if (recallType.includes("Spoiled")) return "chip-spoiled";
  return "";
}
