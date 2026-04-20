"""Descarga y preprocesa datos de USDA FoodData Central."""

import os
import requests
import pandas as pd

from config import USDA_API_URL, USDA_API_KEY, USDA_CSV_PATH, DATA_DIR


FOOD_CATEGORIES = [
    "chicken", "rice", "bread", "pasta", "beef", "pork", "salmon", "egg",
    "tomato", "lettuce", "potato", "cheese", "milk", "yogurt", "apple",
    "banana", "olive oil", "butter", "sugar", "onion", "garlic", "pepper",
    "avocado", "beans", "lentils", "tofu", "shrimp", "tuna", "oats",
    "corn", "broccoli", "spinach", "carrot", "mushroom", "almond",
    "peanut butter", "honey", "chocolate", "flour", "cream",
]

# ---------------------------------------------------------------------------
# Alias: nombre que usa el modelo de visión → query USDA más precisa.
# La clave más larga que coincida como subcadena en el nombre del ingrediente gana.
# ---------------------------------------------------------------------------
_USDA_ALIASES: dict[str, str] = {
    # Huevos — todas las preparaciones tienen la misma composición base
    "egg omelette":          "egg whole",
    "scrambled eggs":        "egg whole",
    "scrambled egg":         "egg whole",
    "hard-boiled egg":       "egg whole",
    "boiled egg":            "egg whole",
    "fried egg":             "egg whole",
    "omelette":              "egg whole",
    "residual egg":          "egg whole",
    # Avena — USDA indexa la seca; "cooked water" da los valores reales (~71 kcal/100g)
    "cooked oatmeal":        "oatmeal cooked water",
    "cooked oats":           "oatmeal cooked water",
    "oatmeal":               "oatmeal cooked water",
    # Arroz
    "turmeric cooked rice":  "rice white long-grain cooked",
    "cooked yellow rice":    "rice white long-grain cooked",
    "cooked white rice":     "rice white long-grain cooked",
    "yellow rice":           "rice white long-grain cooked",
    "white rice":            "rice white long-grain cooked",
    # Pan y masas
    "baguette":              "bread french vienna",
    "whole wheat tortilla":  "tortillas flour whole wheat",
    "pizza dough":           "bread pizza crust",
    "whole wheat bread":     "bread whole wheat",
    # Carnes curadas
    "prosciutto":            "ham leg prosciutto",
    "cured ham":             "pork cured ham",
    "serrano":               "pork cured ham",
    "shredded chicken":      "chicken breast cooked",
    "ground meat":           "beef ground cooked",
    # Pescado
    "roasted salmon fillet": "salmon atlantic cooked",
    "baked salmon fillet":   "salmon atlantic cooked",
    "roasted salmon":        "salmon atlantic cooked",
    "baked salmon":          "salmon atlantic cooked",
    # Quesos
    "emmental cheese":       "cheese swiss",
    "emmental":              "cheese swiss",
    "swiss cheese":          "cheese swiss",
    "mozzarella cheese":     "cheese mozzarella whole milk",
    "manchego cheese":       "cheese manchego",
    # Lácteos
    "greek yogurt":          "yogurt greek plain whole milk",
    "caramel sauce":         "candies caramel",
    # Aceites, caldos, salsas
    "cooking oil":           "oil olive salad",
    "residual oil":          "oil olive salad",
    "soup broth":            "soup chicken broth",
    "vegetable broth":       "soup vegetable",
    "broth":                 "soup chicken broth",
    "tomato sauce":          "tomato sauce canned",
    "tomato pieces":         "tomatoes red ripe raw",
    "tomato slices":         "tomatoes red ripe raw",
    "diced tomato":          "tomatoes red ripe raw",
    # Verduras con modificadores de corte/cocción
    "mixed greens salad":    "lettuce green leaf raw",
    "mixed greens":          "lettuce green leaf raw",
    "diced cucumber":        "cucumber with peel raw",
    "diced carrots":         "carrots raw",
    "shredded carrot":       "carrots raw",
    "corn kernels":          "corn sweet yellow raw",
    "green beans":           "beans snap green raw",
    "red bell pepper":       "peppers sweet red raw",
    "bell pepper":           "peppers sweet raw",
    "mashed avocado":        "avocados raw",
    "avocado spread":        "avocados raw",
    "avocado chunks":        "avocados raw",
    "avocado":               "avocados raw",
    "roasted broccoli":      "broccoli cooked boiled",
    "steamed broccoli":      "broccoli cooked boiled",
    "roasted potatoes":      "potatoes flesh skin baked",
    "roasted potato":        "potatoes flesh skin baked",
    "diced potatoes":        "potatoes boiled",
    # Frutas con modificadores
    "acai bowl base":        "acai berry",
    "acai bowl":             "acai berry",
    "acai":                  "acai berry",
    "sliced banana":         "bananas raw",
    "banana slices":         "bananas raw",
    "diced mango":           "mangos raw",
    "mango chunks":          "mangos raw",
    "sliced strawberries":   "strawberries raw",
    "strawberry slices":     "strawberries raw",
    "fresh strawberries":    "strawberries raw",
    "blueberries":           "blueberries raw",
    "shredded coconut":      "coconut meat dried shredded",
    "coconut flakes":        "coconut meat dried shredded",
    # Legumbres
    "cooked green lentils":  "lentils mature seeds cooked boiled",
    "cooked lentils":        "lentils mature seeds cooked boiled",
    # Atún
    "tuna salad":            "tuna light canned water drained",
    "tuna chunks":           "tuna light canned water drained",
    # Especias y hierbas
    "fresh basil leaves":    "basil fresh",
    "basil leaves":          "basil fresh",
    "dill sprig":            "dill weed",
    "dill":                  "dill weed",
    "cinnamon spice":        "cinnamon ground",
    "cinnamon powder":       "cinnamon ground",
    "turmeric spice":        "spices turmeric ground",
    "turmeric":              "spices turmeric ground",
    "black pepper":          "spices pepper black",
}

# Palabras de método de cocción o formato que se eliminan cuando no hay alias,
# para acercar el query a la terminología USDA.
_MODIFIER_WORDS = {
    "diced", "sliced", "chopped", "shredded", "roasted", "baked",
    "steamed", "grilled", "sauteed", "residual", "pieces",
    "chunks", "strips", "sprig", "base", "kernels", "fillet",
    "fresh", "mixed",
}

# Límites fisiológicos por 100 g
_MAX_KCAL_PER_100G = 900
_MAX_MACRO_PER_100G = 100


def _normalize_query(query: str) -> str:
    """Alias más largo primero; si no hay alias, elimina modificadores de cocción."""
    q = query.lower().strip()
    for alias in sorted(_USDA_ALIASES, key=len, reverse=True):
        if alias in q:
            return _USDA_ALIASES[alias]
    words = q.split()
    core = [w for w in words if w not in _MODIFIER_WORDS]
    return " ".join(core) if core else query


def _extract_kcal(food: dict) -> float:
    """Extrae calorías en kcal/100 g. Prefiere la entrada con unidad KCAL."""
    kcal_val = None
    kj_val = None
    for n in food.get("foodNutrients", []):
        name = n.get("nutrientName", "")
        unit = n.get("unitName", "").upper()
        val = n.get("value", 0) or 0
        if "Energy" in name or "energy" in name:
            if unit == "KCAL":
                kcal_val = val
            elif unit == "KJ" and kcal_val is None:
                kj_val = val
    if kcal_val is not None:
        return kcal_val
    if kj_val is not None:
        return round(kj_val / 4.184, 1)
    return 0.0


def _is_plausible(entry: dict) -> bool:
    """True si los valores nutricionales son fisiológicamente posibles."""
    if entry["calories"] > _MAX_KCAL_PER_100G:
        return False
    if any(entry[k] > _MAX_MACRO_PER_100G for k in ("protein_g", "carbs_g", "fat_g")):
        return False
    return True


def fetch_usda_foods(query: str, page_size: int = 5) -> list[dict]:
    """Busca alimentos en la API USDA FoodData Central."""
    url = f"{USDA_API_URL}/foods/search"
    normalized = _normalize_query(query)
    params = {
        "api_key": USDA_API_KEY,
        "query": normalized,
        "pageSize": page_size,
        "dataType": ["Foundation", "SR Legacy"],
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    foods = resp.json().get("foods", [])

    results = []
    for food in foods:
        nutrients = {n["nutrientName"]: n["value"] for n in food.get("foodNutrients", [])}
        entry = {
            "fdc_id":      food.get("fdcId", ""),
            "description": food.get("description", ""),
            "calories":    _extract_kcal(food),
            "protein_g":   nutrients.get("Protein", 0) or 0,
            "carbs_g":     nutrients.get("Carbohydrate, by difference", 0) or 0,
            "fat_g":       nutrients.get("Total lipid (fat)", 0) or 0,
            "fiber_g":     nutrients.get("Fiber, total dietary", 0) or 0,
        }
        if _is_plausible(entry):
            results.append(entry)
    return results


def build_usda_csv():
    """Descarga datos de USDA para las categorías definidas y guarda CSV."""
    os.makedirs(DATA_DIR, exist_ok=True)
    all_foods = []

    for category in FOOD_CATEGORIES:
        print(f"  Descargando: {category}...")
        try:
            foods = fetch_usda_foods(category)
            all_foods.extend(foods)
        except Exception as e:
            print(f"  Error con '{category}': {e}")

    df = pd.DataFrame(all_foods).drop_duplicates(subset=["fdc_id"])
    df.to_csv(USDA_CSV_PATH, index=False)
    print(f"Guardados {len(df)} alimentos en {USDA_CSV_PATH}")
    return df


if __name__ == "__main__":
    build_usda_csv()
