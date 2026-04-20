"""NutriVision — Dashboard: historial y gráficas del usuario."""

from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data.db import delete_meal, get_daily_summaries, get_today_meals, get_user, init_db
from utils.schemas import compute_caloric_goal

init_db()
st.set_page_config(page_title="NutriVision · Dashboard", page_icon="📊", layout="wide")
st.title("📊 Mi Dashboard")

# ── Autenticación via session_state compartido ───────────
email = st.session_state.get("user_email", "")
if not email:
    st.warning("Inicia sesión desde la página principal introduciendo tu correo.")
    st.stop()

user = get_user(email)
if not user:
    st.warning("Perfil no encontrado. Guárdalo desde la página principal.")
    st.stop()

# ── Cabecera de perfil ───────────────────────────────────
caloric_goal = compute_caloric_goal(
    user["age"], user["weight_kg"], user["height_cm"],
    user["sex"], user["activity_level"], user["objective"],
)

with st.expander("👤 Tu perfil", expanded=False):
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Edad", f"{user['age']} años")
    c2.metric("Peso", f"{user['weight_kg']} kg")
    c3.metric("Altura", f"{user['height_cm']} cm")
    c4.metric("Objetivo calórico", f"{caloric_goal} kcal/día")
    st.caption(f"Sexo: {user['sex']} · Actividad: {user['activity_level']} · Objetivo: {user['objective']}")
    if user["allergies"]:
        st.caption(f"Alergias: {user['allergies']}")

st.divider()

# ── Comidas de hoy ───────────────────────────────────────
today = str(date.today())
today_meals = get_today_meals(email, today)

st.subheader("🍽️ Comidas de hoy")
if today_meals:
    day_cal = sum(m["calories"] for m in today_meals)
    day_pro = sum(m["protein_g"] for m in today_meals)
    day_car = sum(m["carbs_g"] for m in today_meals)
    day_fat = sum(m["fat_g"] for m in today_meals)

    # Barra de progreso
    progress = min(day_cal / caloric_goal, 1.0) if caloric_goal > 0 else 0.0
    st.progress(progress, text=f"{day_cal:.0f} / {caloric_goal} kcal consumidas hoy")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Calorías", f"{day_cal:.0f} kcal")
    m2.metric("Proteína", f"{day_pro:.1f} g")
    m3.metric("Carbos", f"{day_car:.1f} g")
    m4.metric("Grasa", f"{day_fat:.1f} g")

    # Tabla detallada de hoy
    rows = []
    for meal in today_meals:
        rows.append({
            "ID": meal["id"],
            "Comida": meal["meal_type"].capitalize(),
            "Calorías": f"{meal['calories']:.0f}",
            "Proteína (g)": f"{meal['protein_g']:.1f}",
            "Carbos (g)": f"{meal['carbs_g']:.1f}",
            "Grasa (g)": f"{meal['fat_g']:.1f}",
            "Alimentos": meal["ingredients_json"],
        })

    df_today = pd.DataFrame(rows)
    st.dataframe(df_today.drop(columns=["ID"]), use_container_width=True, hide_index=True)

    # Eliminar registros individuales
    with st.expander("🗑️ Eliminar un registro de hoy"):
        meal_options = {f"{m['meal_type'].capitalize()} ({m['calories']:.0f} kcal)": m["id"]
                        for m in today_meals}
        to_delete = st.selectbox("Selecciona el registro a eliminar", list(meal_options.keys()))
        if st.button("Eliminar", type="secondary"):
            delete_meal(meal_options[to_delete])
            st.success("Registro eliminado")
            st.rerun()

    # Gráfico de macros de hoy
    st.subheader("🥧 Distribución de macros hoy")
    fig_today = go.Figure(data=[go.Pie(
        labels=["Proteína", "Carbohidratos", "Grasa"],
        values=[day_pro, day_car, day_fat],
        marker_colors=["#636EFA", "#EF553B", "#00CC96"],
        hole=0.45,
    )])
    fig_today.update_layout(height=320, margin=dict(t=10, b=10))
    st.plotly_chart(fig_today, use_container_width=True)
else:
    st.info("Aún no has registrado ninguna comida hoy. Sube una foto en la página principal.")

st.divider()

# ── Historial de los últimos 30 días ────────────────────
st.subheader("📈 Historial — últimos 30 días")
summaries = get_daily_summaries(email, limit=30)

if len(summaries) < 2:
    st.info("Necesitas al menos 2 días de datos para ver el historial.")
else:
    df = pd.DataFrame(summaries).sort_values("date")

    # — Gráfico de calorías diarias vs objetivo —
    fig_cal = go.Figure()
    fig_cal.add_trace(go.Bar(
        x=df["date"], y=df["calories"],
        name="Calorías consumidas",
        marker_color="#636EFA",
    ))
    fig_cal.add_hline(
        y=caloric_goal,
        line_dash="dash",
        line_color="#FF4B4B",
        annotation_text=f"Objetivo: {caloric_goal} kcal",
        annotation_position="top right",
    )
    fig_cal.update_layout(
        title="Calorías diarias vs objetivo",
        xaxis_title="Fecha",
        yaxis_title="kcal",
        height=380,
        margin=dict(t=40, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig_cal, use_container_width=True)

    # — Gráfico de macros apilados —
    fig_macros = go.Figure()
    fig_macros.add_trace(go.Bar(name="Proteína (g)",     x=df["date"], y=df["protein_g"], marker_color="#636EFA"))
    fig_macros.add_trace(go.Bar(name="Carbohidratos (g)", x=df["date"], y=df["carbs_g"],   marker_color="#EF553B"))
    fig_macros.add_trace(go.Bar(name="Grasa (g)",         x=df["date"], y=df["fat_g"],     marker_color="#00CC96"))
    fig_macros.update_layout(
        barmode="stack",
        title="Distribución de macros por día",
        xaxis_title="Fecha",
        yaxis_title="Gramos",
        height=380,
        margin=dict(t=40, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig_macros, use_container_width=True)

    # — Tabla resumen —
    st.subheader("📋 Tabla resumen")
    df_display = df.rename(columns={
        "date": "Fecha", "calories": "Calorías",
        "protein_g": "Proteína (g)", "carbs_g": "Carbos (g)",
        "fat_g": "Grasa (g)", "meal_count": "Comidas",
    })[["Fecha", "Calorías", "Proteína (g)", "Carbos (g)", "Grasa (g)", "Comidas"]].sort_values("Fecha", ascending=False)

    df_display["Calorías"] = df_display["Calorías"].map("{:.0f}".format)
    df_display["Proteína (g)"] = df_display["Proteína (g)"].map("{:.1f}".format)
    df_display["Carbos (g)"] = df_display["Carbos (g)"].map("{:.1f}".format)
    df_display["Grasa (g)"] = df_display["Grasa (g)"].map("{:.1f}".format)

    st.dataframe(df_display, use_container_width=True, hide_index=True)
