from data.usda_loader import fetch_usda_foods
from utils.schemas import Ingredient, NutritionInfo


def search_nutrition_usda(ingredients: list[Ingredient]) -> list[NutritionInfo]:
    """Para cada ingrediente busca en USDA y escala los nutrientes por porcion."""
    results: list[NutritionInfo] = []

    for ing in ingredients:
        try:
            foods = fetch_usda_foods(ing.name, page_size=1)
            if not foods:
                results.append(NutritionInfo(
                    ingredient=ing.name,
                    grams=ing.estimated_grams,
                    source="USDA (sin resultado)",
                ))
                continue

            top = foods[0]
            factor = ing.estimated_grams / 100.0
            results.append(NutritionInfo(
                ingredient=ing.name,
                grams=ing.estimated_grams,
                calories=top["calories"]  * factor,
                protein_g=top["protein_g"] * factor,
                carbs_g=top["carbs_g"]   * factor,
                fat_g=top["fat_g"]     * factor,
                fiber_g=top["fiber_g"]   * factor,
                source=f"USDA:{top['fdc_id']}",
            ))

        except Exception as exc:  # noqa: BLE001
            results.append(NutritionInfo(
                ingredient=ing.name,
                grams=ing.estimated_grams,
                source=f"USDA (error: {exc})",
            ))

    return results
