from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


_ACTIVITY_MULTIPLIERS = {
    "sedentario": 1.2,
    "ligero": 1.375,
    "moderado": 1.55,
    "activo": 1.725,
    "muy activo": 1.9,
}

_OBJECTIVE_ADJUSTMENTS = {
    "mantenimiento": 0,
    "volumen": +300,
    "definición": -400,
}


def compute_caloric_goal(
    age: int,
    weight_kg: float,
    height_cm: float,
    sex: str,
    activity_level: str,
    objective: str,
) -> int:
    """Calcula el objetivo calórico diario usando Mifflin-St Jeor + TDEE + objetivo."""
    if sex == "hombre":
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161
    tdee = bmr * _ACTIVITY_MULTIPLIERS.get(activity_level, 1.55)
    adjustment = _OBJECTIVE_ADJUSTMENTS.get(objective, 0)
    return round(tdee + adjustment)


MEAL_ORDER = ["desayuno", "almuerzo", "comida", "merienda", "cena"]


def remaining_meals(current_meal: str, logged_today: list[str]) -> list[str]:
    """Devuelve las comidas que quedan después de `current_meal`."""
    try:
        idx = MEAL_ORDER.index(current_meal)
    except ValueError:
        idx = len(MEAL_ORDER) - 1
    return [m for m in MEAL_ORDER[idx + 1:] if m not in logged_today]


class UserProfile(BaseModel):
    age: int = 25
    weight_kg: float = 70.0
    height_cm: float = 170.0
    sex: str = "hombre"  # hombre / mujer
    activity_level: str = "moderado"
    caloric_goal: int = 2000  # calculado automáticamente
    allergies: list[str] = Field(default_factory=list)
    objective: str = "mantenimiento"  # mantenimiento / volumen / definición
    # Comida actual y contexto del día
    meal_type: str = "comida"
    logged_meal_types: list[str] = Field(default_factory=list)  # ya registradas hoy
    remaining_meal_types: list[str] = Field(default_factory=list)  # quedan hoy
    # Acumulado del día (antes de esta comida)
    daily_consumed_calories: float = 0.0
    daily_consumed_protein: float = 0.0
    daily_consumed_carbs: float = 0.0
    daily_consumed_fat: float = 0.0


class Ingredient(BaseModel):
    name: str
    estimated_grams: float
    portion_size: str = "normal"  # small / normal / large / extra
    confidence: float = 1.0


class NutritionInfo(BaseModel):
    ingredient: str
    grams: float
    calories: float = 0.0
    protein_g: float = 0.0
    carbs_g: float = 0.0
    fat_g: float = 0.0
    fiber_g: float = 0.0
    source: str = "usda"


class AgentState(BaseModel):
    """Estado compartido del grafo LangGraph."""
    image_b64: str = ""
    user_profile: UserProfile = Field(default_factory=UserProfile)
    ingredients: list[Ingredient] = Field(default_factory=list)
    # Tavily (fuente principal)
    nutrition: list[NutritionInfo] = Field(default_factory=list)
    total_calories: float = 0.0
    total_protein: float = 0.0
    total_carbs: float = 0.0
    total_fat: float = 0.0
    # RAG (conservado para evaluación comparativa)
    rag_nutrition: list[NutritionInfo] = Field(default_factory=list)
    rag_total_calories: float = 0.0
    rag_total_protein: float = 0.0
    rag_total_carbs: float = 0.0
    rag_total_fat: float = 0.0
    report: str = ""
    error: Optional[str] = None
