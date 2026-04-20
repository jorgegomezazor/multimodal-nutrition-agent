"""NutriVision — Página principal: análisis de comida."""

import base64
from datetime import date

import plotly.graph_objects as go
import streamlit as st

from agents.graph import nutrivision_graph
from data.db import add_meal, get_today_meals, get_user, init_db, upsert_user
from utils.schemas import (
    MEAL_ORDER,
    NutritionInfo,
    UserProfile,
    compute_caloric_goal,
    remaining_meals,
)

# ── Inicialización ───────────────────────────────────────
init_db()
st.set_page_config(page_title="NutriVision", page_icon="🍽️", layout="wide")
st.title("🍽️ NutriVision")
st.caption("Agente multimodal de análisis nutricional por imagen")

# ── Defaults de perfil en session_state ─────────────────
_DEFAULT_PROFILE = {
    "age": 25, "sex": "hombre", "weight_kg": 70.0, "height_cm": 170.0,
    "activity_level": "moderado", "objective": "mantenimiento", "allergies": "",
}
if "profile" not in st.session_state:
    st.session_state.profile = _DEFAULT_PROFILE.copy()
if "user_email" not in st.session_state:
    st.session_state.user_email = ""
if "profile_saved" not in st.session_state:
    st.session_state.profile_saved = False
if "last_result" not in st.session_state:
    st.session_state.last_result = None

# ── Sidebar ──────────────────────────────────────────────
with st.sidebar:
    st.header("👤 Tu perfil")

    # — Login por email —
    email_input = st.text_input("Correo electrónico", value=st.session_state.user_email)
    col_load, col_save = st.columns(2)

    with col_load:
        if st.button("Cargar", use_container_width=True):
            if email_input:
                user = get_user(email_input)
                if user:
                    st.session_state.profile = {
                        "age": user["age"],
                        "sex": user["sex"],
                        "weight_kg": user["weight_kg"],
                        "height_cm": user["height_cm"],
                        "activity_level": user["activity_level"],
                        "objective": user["objective"],
                        "allergies": user["allergies"],
                    }
                    st.session_state.user_email = email_input
                    st.session_state.profile_saved = True
                    st.success("Perfil cargado")
                    st.rerun()
                else:
                    st.session_state.user_email = email_input
                    st.info("Email nuevo — rellena tu perfil y guárdalo")

    p = st.session_state.profile

    # — Campos de perfil —
    age = st.number_input("Edad", 10, 100, int(p["age"]))
    sex = st.selectbox(
        "Sexo", ["hombre", "mujer"],
        index=["hombre", "mujer"].index(p["sex"]),
    )
    weight = st.number_input("Peso (kg)", 30.0, 200.0, float(p["weight_kg"]), step=0.5)
    height = st.number_input("Altura (cm)", 100.0, 220.0, float(p["height_cm"]), step=0.5)
    activity_level = st.selectbox(
        "Nivel de actividad",
        ["sedentario", "ligero", "moderado", "activo", "muy activo"],
        index=["sedentario", "ligero", "moderado", "activo", "muy activo"].index(p["activity_level"]),
    )
    objective = st.selectbox(
        "Objetivo", ["mantenimiento", "volumen", "definición"],
        index=["mantenimiento", "volumen", "definición"].index(p["objective"]),
    )
    allergies_raw = st.text_input("Alergias (separadas por coma)", value=p["allergies"])
    allergies = [a.strip() for a in allergies_raw.split(",") if a.strip()]

    caloric_goal = compute_caloric_goal(age, weight, height, sex, activity_level, objective)
    st.info(f"🎯 Objetivo calórico: **{caloric_goal} kcal/día**")

    with col_save:
        if st.button("Guardar", use_container_width=True):
            if email_input:
                upsert_user(email_input, {
                    "age": age, "sex": sex, "weight_kg": weight,
                    "height_cm": height, "activity_level": activity_level,
                    "objective": objective, "allergies": allergies_raw,
                })
                st.session_state.profile = {
                    "age": age, "sex": sex, "weight_kg": weight,
                    "height_cm": height, "activity_level": activity_level,
                    "objective": objective, "allergies": allergies_raw,
                }
                st.session_state.user_email = email_input
                st.session_state.profile_saved = True
                st.success("Perfil guardado")
            else:
                st.warning("Introduce un correo para guardar")

    # — Registro del día —
    st.divider()
    st.header("📅 Registro de hoy")
    today = str(date.today())

    if st.session_state.user_email:
        today_meals = get_today_meals(st.session_state.user_email, today)
    else:
        today_meals = []

    day_calories = sum(m["calories"] for m in today_meals)
    day_protein  = sum(m["protein_g"] for m in today_meals)
    day_carbs    = sum(m["carbs_g"] for m in today_meals)
    day_fat      = sum(m["fat_g"] for m in today_meals)
    logged_types = [m["meal_type"] for m in today_meals]

    progress = min(day_calories / caloric_goal, 1.0) if caloric_goal > 0 else 0.0
    st.progress(progress, text=f"{day_calories:.0f} / {caloric_goal} kcal")

    c1, c2, c3 = st.columns(3)
    c1.metric("Proteína", f"{day_protein:.0f} g")
    c2.metric("Carbos", f"{day_carbs:.0f} g")
    c3.metric("Grasa", f"{day_fat:.0f} g")

    if today_meals:
        st.caption(f"Comidas: {', '.join(logged_types)}")

# ── Área principal ───────────────────────────────────────
if not st.session_state.user_email:
    st.info("Introduce tu correo en el panel izquierdo para empezar. Si eres nuevo, rellena tu perfil y pulsa **Guardar**.")
    st.stop()

# Selector de tipo de comida
meal_type = st.selectbox(
    "¿Qué comida es esta?",
    MEAL_ORDER,
    index=MEAL_ORDER.index("comida"),
)

uploaded = st.file_uploader("📷 Sube una foto de tu plato", type=["jpg", "jpeg", "png"])

if uploaded:
    image_bytes = uploaded.read()
    image_b64 = base64.b64encode(image_bytes).decode()
    st.image(image_bytes, caption="Tu plato", use_container_width=True)

    if st.button("🔍 Analizar", type="primary"):
        remaining = remaining_meals(meal_type, logged_types)

        profile = UserProfile(
            age=age,
            sex=sex,
            weight_kg=weight,
            height_cm=height,
            activity_level=activity_level,
            caloric_goal=caloric_goal,
            objective=objective,
            allergies=allergies,
            meal_type=meal_type,
            logged_meal_types=logged_types,
            remaining_meal_types=remaining,
            daily_consumed_calories=day_calories,
            daily_consumed_protein=day_protein,
            daily_consumed_carbs=day_carbs,
            daily_consumed_fat=day_fat,
        )

        with st.spinner("Analizando imagen..."):
            result = nutrivision_graph.invoke({
                "image_b64": image_b64,
                "user_profile": profile.model_dump(),
            })

        if result.get("error"):
            st.error(result["error"])
        else:
            # Guardar en base de datos
            ingredients_list = [n["ingredient"] for n in result["nutrition"]]
            add_meal(
                email=st.session_state.user_email,
                date=today,
                meal_type=meal_type,
                calories=result["total_calories"],
                protein_g=result["total_protein"],
                carbs_g=result["total_carbs"],
                fat_g=result["total_fat"],
                ingredients=ingredients_list,
            )
            # Guardar resultado en session_state para mostrarlo tras cualquier rerun
            st.session_state.last_result = {
                "result": result,
                "meal_type": meal_type,
                "day_calories": day_calories,
                "caloric_goal": caloric_goal,
            }

# — Mostrar el último resultado (persiste entre reruns) —
if st.session_state.last_result:
    r = st.session_state.last_result
    result = r["result"]
    _meal_type = r["meal_type"]
    _new_total = r["day_calories"] + result["total_calories"]
    _left = r["caloric_goal"] - _new_total

    st.divider()
    st.subheader(f"🍽️ Resultado — {_meal_type.capitalize()}")

    # — Tabla de ingredientes —
    st.subheader("📊 Desglose nutricional")
    nutrition = [NutritionInfo(**n) for n in result["nutrition"]]
    table_data = [
        {
            "Ingrediente": n.ingredient,
            "Porción (g)": f"{n.grams:.0f}",
            "Calorías": f"{n.calories:.0f}",
            "Proteína (g)": f"{n.protein_g:.1f}",
            "Carbos (g)": f"{n.carbs_g:.1f}",
            "Grasa (g)": f"{n.fat_g:.1f}",
        }
        for n in nutrition
    ]
    st.table(table_data)

    # — Totales de esta comida —
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Calorías", f"{result['total_calories']:.0f} kcal")
    col2.metric("Proteína", f"{result['total_protein']:.1f} g")
    col3.metric("Carbos", f"{result['total_carbs']:.1f} g")
    col4.metric("Grasa", f"{result['total_fat']:.1f} g")

    # — Progreso del día —
    st.subheader("📅 Progreso del día")
    ca, cb, cc = st.columns(3)
    ca.metric("Total hoy", f"{_new_total:.0f} kcal")
    cb.metric("Objetivo", f"{r['caloric_goal']} kcal")
    cc.metric("Restante", f"{_left:.0f} kcal",
              delta_color="normal" if _left >= 0 else "inverse",
              delta=f"{_left:.0f}")

    # — Gráfico de macros —
    st.subheader("🥧 Macros de esta comida")
    fig = go.Figure(data=[go.Pie(
        labels=["Proteína", "Carbohidratos", "Grasa"],
        values=[result["total_protein"], result["total_carbs"], result["total_fat"]],
        marker_colors=["#636EFA", "#EF553B", "#00CC96"],
        hole=0.4,
    )])
    fig.update_layout(height=300, margin=dict(t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

    # — Informe del LLM —
    st.subheader("📝 Informe personalizado")
    st.markdown(result["report"])

    if st.button("🔄 Analizar otra comida"):
        st.session_state.last_result = None
        st.rerun()
