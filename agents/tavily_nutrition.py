"""Modulo de nutricion via Tavily: busca datos reales para cada ingrediente."""

import re

from tavily import TavilyClient

from config import TAVILY_API_KEY
from utils.schemas import Ingredient, NutritionInfo

# Limites fisiologicos maximos por 100 g — filtra extracciones absurdas
_MAX = {"calories": 900, "protein_g": 95, "carbs_g": 100, "fat_g": 100, "fiber_g": 80}

# Patrones ordenados de mas a menos especifico
_PATTERNS = {
    "calories": [
        re.compile(r'(?:energy|calories?)[^\d]{0,10}?(\d+(?:\.\d+)?)\s*(?:kcal|cal)', re.I),
        re.compile(r'(\d+(?:\.\d+)?)\s*(?:kcal|calories?)\b', re.I),
    ],
    "protein_g": [
        re.compile(r'protein[^\d]{0,10}?(\d+(?:\.\d+)?)\s*g\b', re.I),
    ],
    "carbs_g": [
        re.compile(r'(?:total\s+)?carbohydrates?[^\d]{0,10}?(\d+(?:\.\d+)?)\s*g\b', re.I),
        re.compile(r'\bcarbs?[^\d]{0,10}?(\d+(?:\.\d+)?)\s*g\b', re.I),
    ],
    "fat_g": [
        re.compile(r'total\s+fat[^\d]{0,10}?(\d+(?:\.\d+)?)\s*g\b', re.I),
        re.compile(r'(?<!\w)fat[^\d]{0,10}?(\d+(?:\.\d+)?)\s*g\b', re.I),
    ],
    "fiber_g": [
        re.compile(r'(?:dietary\s+)?fiber[^\d]{0,10}?(\d+(?:\.\d+)?)\s*g\b', re.I),
    ],
}


def _find_per_100g_window(content: str) -> str:
    """Devuelve el fragmento del texto más cercano a una mención de 'per 100g'."""
    marker = re.search(r'per\s*100\s*(?:g|ml|gram)', content, re.I)
    if marker:
        start = max(0, marker.start() - 200)
        end   = min(len(content), marker.end() + 600)
        return content[start:end]
    return content   # si no hay marcador, usar todo


def _extract(content: str) -> dict:
    """Extrae valores nutricionales por 100 g con validacion de limites."""
    window = _find_per_100g_window(content)
    data = {}
    for key, patterns in _PATTERNS.items():
        for pat in patterns:
            match = pat.search(window)
            if match:
                try:
                    val = float(match.group(1))
                    if val <= _MAX[key]:          # descartar valores absurdos
                        data[key] = val
                        break
                except ValueError:
                    continue
    return data


def search_nutrition_tavily(ingredients: list[Ingredient]) -> list[NutritionInfo]:
    """Busca en Tavily la info nutricional de cada ingrediente y escala por porcion."""
    tavily = TavilyClient(api_key=TAVILY_API_KEY)
    results: list[NutritionInfo] = []

    for ing in ingredients:
        try:
            query = f"{ing.name} nutrition facts per 100g calories protein carbohydrates fat fiber"
            search = tavily.search(query, max_results=3, search_depth="basic")
            content = "\n\n".join(r.get("content", "") for r in search.get("results", []))

            data   = _extract(content)
            factor = ing.estimated_grams / 100.0

            results.append(NutritionInfo(
                ingredient=ing.name,
                grams=ing.estimated_grams,
                calories=data.get("calories",  0) * factor,
                protein_g=data.get("protein_g", 0) * factor,
                carbs_g=data.get("carbs_g",   0) * factor,
                fat_g=data.get("fat_g",     0) * factor,
                fiber_g=data.get("fiber_g",   0) * factor,
                source="Tavily",
            ))

        except Exception as exc:  # noqa: BLE001
            results.append(NutritionInfo(
                ingredient=ing.name,
                grams=ing.estimated_grams,
                source=f"Tavily (error: {exc})",
            ))

    return results
