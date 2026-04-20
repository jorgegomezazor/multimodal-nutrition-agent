"""Módulo de visión: identifica ingredientes a partir de una imagen."""

import json
import time

import requests
from huggingface_hub import InferenceClient

from config import GOOGLE_API_KEY, GROQ_API_KEY, HF_TOKEN, VISION_MODEL_ID
from utils.prompts import VISION_PROMPT
from utils.schemas import Ingredient

_GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

# ---------------------------------------------------------------------------
# Tabla de porciones estándar (gramos por ración "normal").
# Fuente: USDA FoodData Central + guías nutricionales estándar.
# La clave más larga que coincida con el nombre del ingrediente gana.
# ---------------------------------------------------------------------------
_STANDARD_GRAMS: dict[str, float] = {
    # Spices, herbs, garnishes
    "black pepper":      3,  "cinnamon":       5,  "cumin":          5,
    "paprika":           5,  "seasoning":      5,  "spice":          5,
    "salt":              3,  "dill sprig":     5,  "basil leaves":  10,
    "parsley":          10,  "herb":          10,  "garnish":        8,
    "lemon wedge":      20,  "lime wedge":    20,
    # Oils, sauces, condiments
    "olive oil":        15,  "cooking oil":   15,  "oil":           15,
    "butter":           12,  "mayonnaise":    20,  "dressing":      25,
    "caramel sauce":    20,  "tomato sauce":  60,  "sauce":         40,
    "ketchup":          20,  "honey":         20,  "jam":           20,
    "peanut butter":    32,  "hummus":        50,  "cream":         30,
    "vegetable broth":  50,  "broth":         50,
    # Nuts, seeds, toppings
    "walnut":           25,  "almond":        25,  "cashew":        25,
    "nuts":             25,  "seeds":         15,
    "coconut flakes":   20,  "coconut":       25,
    # Dairy
    "greek yogurt":    150,  "yogurt":       150,
    "mozzarella":       50,  "manchego":      35,  "parmesan":      20,
    "cheese":           35,  "milk":         150,  "cream cheese":  30,
    # Eggs
    "scrambled eggs":  150,  "hard-boiled egg": 110, "omelette":   150,
    "fried egg":        55,  "egg":          110,
    # Bread and grains
    "pizza dough":     150,  "baguette":     100,
    "tortilla":         60,  "wrap":          80,
    "bread":            70,  "toast":         70,  "crouton":       20,
    "cooked oats":     180,  "oatmeal":      180,  "oats":          60,
    "granola":          40,  "cereal":        40,
    "cooked rice":     180,  "rice":         180,
    "penne pasta":     180,  "cooked pasta": 180,  "pasta":        180,
    "noodles":         180,  "couscous":     150,  "quinoa":       150,
    # Starchy vegetables
    "sweet potato":    150,  "potato":       150,  "fries":        100,
    "corn":             80,
    # Meat and fish (specific before generic)
    "grilled chicken": 130,  "chicken breast": 130, "chicken pieces": 130,
    "shredded chicken":100,  "chicken":      130,
    "ground beef":     120,  "beef":         120,
    "cured ham":        50,  "serrano":       50,  "ham":           50,
    "chorizo":          50,  "pork":         100,  "bacon":         40,
    "salmon fillet":   150,  "salmon":       150,
    "tuna":            100,  "shrimp":       100,  "fish":         150,
    # Legumes
    "cooked lentils":  180,  "lentils":      180,
    "cooked beans":    150,  "beans":        150,  "chickpeas":    150,
    "tofu":            120,
    # Vegetables
    "mixed salad greens": 70, "salad greens": 70, "lettuce":       70,
    "mixed greens":     70,  "spinach":       70,  "arugula":       60,
    "tomato":           80,  "cucumber":      80,
    "carrot":           75,  "broccoli":     100,
    "bell pepper":      80,  "red pepper":    80,  "green pepper":  80,
    "pepper":           80,
    "onion":            60,  "red onion":     60,
    "avocado":          80,  "mushroom":      80,  "zucchini":      80,
    # Fruits
    "banana":          120,  "mango":        100,
    "strawberry":       80,  "blueberry":     65,  "raspberry":     70,
    "apple":           150,  "orange":       150,  "grape":         80,
    "acai":            100,
    # Fallback
    "default":          80,
}

_PORTION_MULT: dict[str, float] = {
    "small":   0.6,  "pequeña": 0.6,  "pequeño": 0.6,
    "normal":  1.0,  "medium":  1.0,
    "large":   1.5,  "grande":  1.5,
    "extra":   2.0,
}


def _keyword_grams(name: str) -> float:
    """Gramos estándar del ingrediente usando la clave más larga que coincida."""
    name_lower = name.lower()
    for keyword in sorted(_STANDARD_GRAMS, key=len, reverse=True):
        if keyword == "default":
            continue
        if keyword in name_lower:
            return _STANDARD_GRAMS[keyword]
    return _STANDARD_GRAMS["default"]


def _parse_ingredients(raw: str) -> list[Ingredient]:
    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end == -1:
        raise ValueError(f"No se encontró JSON válido: {raw[:200]}")
    data = json.loads(raw[start: end + 1])
    ingredients = []
    for item in data:
        portion_size = str(item.get("portion_size", "normal")).lower().strip()
        mult = _PORTION_MULT.get(portion_size, 1.0)
        estimated_grams = round(_keyword_grams(item["name"]) * mult, 1)
        ingredients.append(Ingredient(
            name=item["name"],
            portion_size=portion_size,
            estimated_grams=estimated_grams,
            confidence=item.get("confidence", 1.0),
        ))
    return ingredients


def identify_ingredients_hf(image_b64: str) -> list[Ingredient]:
    client = InferenceClient(token=HF_TOKEN)
    response = client.chat_completion(
        model=VISION_MODEL_ID,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                {"type": "text", "text": VISION_PROMPT},
            ],
        }],
        max_tokens=1024,
    )
    return _parse_ingredients(response.choices[0].message.content)


def identify_ingredients_groq(image_b64: str) -> list[Ingredient]:
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        json={
            "model": _GROQ_MODEL,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                    {"type": "text", "text": VISION_PROMPT},
                ],
            }],
            "max_tokens": 1024,
        },
        timeout=60,
    )
    response.raise_for_status()
    return _parse_ingredients(response.json()["choices"][0]["message"]["content"])


def identify_ingredients_gemini(image_b64: str) -> list[Ingredient]:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={GOOGLE_API_KEY}"
    )
    payload = {"contents": [{"parts": [
        {"inline_data": {"mime_type": "image/jpeg", "data": image_b64}},
        {"text": VISION_PROMPT},
    ]}]}

    wait = 15
    for _ in range(4):
        resp = requests.post(url, json=payload, timeout=60)
        if resp.status_code == 429:
            print(f"[Vision] Gemini rate-limit, esperando {wait}s...")
            time.sleep(wait)
            wait *= 2
            continue
        resp.raise_for_status()
        raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        return _parse_ingredients(raw)
    raise RuntimeError("Gemini rate-limit: reintentos agotados")


def identify_ingredients(image_b64: str) -> list[Ingredient]:
    """Cadena de fallback: HF → Groq → Gemini."""
    try:
        return identify_ingredients_hf(image_b64)
    except Exception as e:
        print(f"[Vision] HF falló ({e}), intentando Groq...")

    if GROQ_API_KEY:
        try:
            return identify_ingredients_groq(image_b64)
        except Exception as e:
            print(f"[Vision] Groq falló ({e}), intentando Gemini...")

    if GOOGLE_API_KEY:
        return identify_ingredients_gemini(image_b64)

    raise RuntimeError("Todos los proveedores de visión fallaron")
