VISION_PROMPT = """Analyze this food image. Identify every visible ingredient and classify its portion size.

For each ingredient, choose ONE portion_size label:
- "small"  — clearly less than a standard serving (garnish, drizzle, pinch)
- "normal" — a standard restaurant or home serving
- "large"  — noticeably more than standard (heaped plate, big fillet)
- "extra"  — very large, roughly double a standard serving

Standard portion references (what "normal" means for each category):
- Cooked rice, pasta or legumes: ~180 g
- Meat or fish fillet: ~130 g
- Whole egg: ~55 g (count visible eggs individually)
- Bread slice: ~35 g; roll or baguette portion: ~100 g; tortilla/wrap: ~60 g
- Oil, sauce or dressing: ~15 g (use "small" for drizzles, "normal" for visible pools)
- Cheese sliced: ~35 g; yogurt in bowl: ~150 g
- Fruit piece (banana, mango): ~110 g; berries (handful): ~65 g
- Granola or dry cereal: ~40 g
- Vegetables or salad greens per component: ~80 g
- Nuts or seeds: ~25 g; honey: ~15 g

Instructions:
1. List every distinct ingredient, including oils, sauces, spices, and garnishes.
2. Assign a portion_size label for each. Do NOT estimate grams — only use the four labels.
3. Respond ONLY with a valid JSON array. No extra text, no markdown code blocks.

Example output:
[
  {"name": "grilled chicken breast", "portion_size": "normal", "confidence": 0.9},
  {"name": "cooked white rice",      "portion_size": "large",  "confidence": 0.85},
  {"name": "roasted broccoli",       "portion_size": "normal", "confidence": 0.8},
  {"name": "olive oil",              "portion_size": "small",  "confidence": 0.7}
]

Be specific with food names (e.g. "whole wheat bread" not "bread", "Greek yogurt" not "yogurt")."""


REASONING_PROMPT = """You are a nutrition expert. Given the following data, produce a structured nutritional report in Spanish.

## User Profile
- Age: {age}, Sex: {sex}, Weight: {weight_kg} kg, Height: {height_cm} cm
- Activity level: {activity_level}
- Daily caloric goal (calculated): {caloric_goal} kcal
- Objective: {objective}
- Allergies: {allergies}

## Today's Meal Context
- Current meal: **{meal_type}**
- Meals already logged today: {logged_meals}
- Meals still remaining today: {remaining_meals}

## Daily Progress (before this meal)
- Calories already consumed today: {daily_consumed_calories:.0f} kcal
- Remaining budget before this meal: {remaining_before:.0f} kcal
- Protein consumed: {daily_consumed_protein:.1f} g
- Carbs consumed: {daily_consumed_carbs:.1f} g
- Fat consumed: {daily_consumed_fat:.1f} g

## This Meal — Identified Ingredients and Nutrition
{nutrition_table}

## This Meal — Totals
- Calories: {total_calories:.0f} kcal
- Protein: {total_protein:.1f} g
- Carbs: {total_carbs:.1f} g
- Fat: {total_fat:.1f} g

## After This Meal
- Total consumed today: {total_day_calories:.0f} / {caloric_goal} kcal
- Remaining budget: {remaining_after:.0f} kcal

## Instructions
1. Summarize the nutritional composition of this meal ({meal_type}).
2. Evaluate this meal in the context of the user's full day.
3. Flag any allergens found.
4. IMPORTANT: Provide 2-3 specific recommendations ONLY for the remaining meals of the day ({remaining_meals}). Do NOT recommend meals that have already passed. If there are no remaining meals, give general advice for tomorrow.
5. Format your response with clear sections using markdown headers.

Respond in Spanish."""
