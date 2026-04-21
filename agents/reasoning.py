from huggingface_hub import InferenceClient

from config import HF_TOKEN, REASONING_MODEL_ID
from utils.prompts import REASONING_PROMPT
from utils.schemas import AgentState


def generate_report(state: AgentState) -> str:
    """Genera el informe nutricional usando el LLM razonador."""
    # Construir tabla de nutrición como texto
    rows = []
    for n in state.nutrition:
        rows.append(
            f"| {n.ingredient} | {n.grams:.0f}g | {n.calories:.0f} kcal | "
            f"{n.protein_g:.1f}g | {n.carbs_g:.1f}g | {n.fat_g:.1f}g |"
        )
    nutrition_table = (
        "| Ingrediente | Porción | Calorías | Proteína | Carbos | Grasa |\n"
        "|---|---|---|---|---|---|\n" + "\n".join(rows)
    )

    p = state.user_profile
    remaining_before = p.caloric_goal - p.daily_consumed_calories
    total_day_calories = p.daily_consumed_calories + state.total_calories
    remaining_after = p.caloric_goal - total_day_calories

    logged_meals_str = ", ".join(p.logged_meal_types) if p.logged_meal_types else "ninguna"
    remaining_meals_str = ", ".join(p.remaining_meal_types) if p.remaining_meal_types else "ninguna (última comida del día)"

    prompt = REASONING_PROMPT.format(
        age=p.age,
        sex=p.sex,
        weight_kg=p.weight_kg,
        height_cm=p.height_cm,
        activity_level=p.activity_level,
        caloric_goal=p.caloric_goal,
        objective=p.objective,
        allergies=", ".join(p.allergies) or "Ninguna",
        meal_type=p.meal_type,
        logged_meals=logged_meals_str,
        remaining_meals=remaining_meals_str,
        daily_consumed_calories=p.daily_consumed_calories,
        daily_consumed_protein=p.daily_consumed_protein,
        daily_consumed_carbs=p.daily_consumed_carbs,
        daily_consumed_fat=p.daily_consumed_fat,
        remaining_before=remaining_before,
        nutrition_table=nutrition_table,
        total_calories=state.total_calories,
        total_protein=state.total_protein,
        total_carbs=state.total_carbs,
        total_fat=state.total_fat,
        total_day_calories=total_day_calories,
        remaining_after=remaining_after,
    )

    client = InferenceClient(token=HF_TOKEN)
    response = client.chat_completion(
        model=REASONING_MODEL_ID,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2048,
    )
    return response.choices[0].message.content
