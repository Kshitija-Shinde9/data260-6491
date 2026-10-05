from __future__ import annotations

import logging
import sys
from typing import Any

import httpx

try:
    from mcp.server.fastmcp import FastMCP as _Server
except ModuleNotFoundError:
    from mcp.server.mcpserver import MCPServer as _Server

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [meals] %(message)s",
)
log = logging.getLogger("meals")

mcp = _Server("meals")
BASE = "https://www.themealdb.com/api/json/v1/1"


def _get_json(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{BASE}/{path.lstrip('/')}"
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as exc:
        log.error("HTTP error calling %s: %s", url, exc)
        raise RuntimeError(f"TheMealDB request failed: {exc}") from exc
    except ValueError as exc:
        log.error("JSON decode error from %s: %s", url, exc)
        raise RuntimeError(f"TheMealDB returned invalid JSON: {exc}") from exc


def _parse_ingredients(meal: dict[str, Any]) -> list[dict[str, str]]:
    ingredients: list[dict[str, str]] = []
    for i in range(1, 21):
        name = (meal.get(f"strIngredient{i}") or "").strip()
        measure = (meal.get(f"strMeasure{i}") or "").strip()
        if name:
            ingredients.append({"name": name, "measure": measure})
    return ingredients


def _meal_details_shape(meal: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": meal.get("idMeal"),
        "name": meal.get("strMeal"),
        "category": meal.get("strCategory"),
        "area": meal.get("strArea"),
        "instructions": meal.get("strInstructions"),
        "image": meal.get("strMealThumb"),
        "source": meal.get("strSource"),
        "youtube": meal.get("strYoutube"),
        "ingredients": _parse_ingredients(meal),
    }


def _no_matches() -> dict[str, Any]:
    return {"message": "no matches", "meals": []}


@mcp.tool()
def search_meals_by_name(query: str, limit: int = 5) -> list[dict[str, Any]] | dict[str, Any]:

    if limit < 1 or limit > 25:
        raise ValueError("limit must be between 1 and 25")
    log.info("search_meals_by_name query=%r limit=%s", query, limit)
    payload = _get_json("search.php", {"s": query})
    meals = payload.get("meals")
    if not meals:
        return _no_matches()
    results = []
    for meal in meals[:limit]:
        results.append(
            {
                "id": meal.get("idMeal"),
                "name": meal.get("strMeal"),
                "area": meal.get("strArea"),
                "category": meal.get("strCategory"),
                "thumb": meal.get("strMealThumb"),
            }
        )
    return results


@mcp.tool()
def meals_by_ingredient(ingredient: str, limit: int = 12) -> list[dict[str, Any]] | dict[str, Any]:

    if limit < 1:
        raise ValueError("limit must be at least 1")
    log.info("meals_by_ingredient ingredient=%r limit=%s", ingredient, limit)
    payload = _get_json("filter.php", {"i": ingredient})
    meals = payload.get("meals")
    if not meals:
        return _no_matches()
    results = []
    for meal in meals[:limit]:
        results.append(
            {
                "id": meal.get("idMeal"),
                "name": meal.get("strMeal"),
                "thumb": meal.get("strMealThumb"),
            }
        )
    return results


@mcp.tool()
def meal_details(id: str | int) -> dict[str, Any]:

    log.info("meal_details id=%r", id)
    payload = _get_json("lookup.php", {"i": str(id)})
    meals = payload.get("meals")
    if not meals:
        return _no_matches()
    return _meal_details_shape(meals[0])


@mcp.tool()
def random_meal() -> dict[str, Any]:

    log.info("random_meal")
    payload = _get_json("random.php")
    meals = payload.get("meals")
    if not meals:
        return _no_matches()
    return _meal_details_shape(meals[0])


if __name__ == "__main__":
    mcp.run()
