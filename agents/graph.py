from __future__ import annotations
from typing import TypedDict

from langgraph.graph import StateGraph, END

from utils.schemas import AgentState, Ingredient
from agents.vision import identify_ingredients
from agents.rag import retrieve_nutrition
from agents.usda_nutrition import search_nutrition_usda
from agents.reasoning import generate_report


class GraphState(TypedDict, total=False):
    image_b64: str
    user_profile: dict
    ingredients: list[dict]
    # Resultados RAG (conservados para evaluación)
    rag_nutrition: list[dict]
    rag_total_calories: float
    rag_total_protein: float
    rag_total_carbs: float
    rag_total_fat: float
    # Resultados Tavily (fuente principal para UI e informe)
    nutrition: list[dict]
    total_calories: float
    total_protein: float
    total_carbs: float
    total_fat: float
    report: str
    error: str | None


# ── Nodos ────────────────────────────────────────────────

def vision_node(state: GraphState) -> GraphState:
    try:
        ingredients = identify_ingredients(state["image_b64"])
        return {"ingredients": [ing.model_dump() for ing in ingredients]}
    except Exception as e:
        return {"error": f"Error en visión: {e}"}


def rag_node(state: GraphState) -> GraphState:
    """Nodo RAG — conservado para comparación en evaluación."""
    if state.get("error"):
        return {}
    ingredients = [Ingredient(**d) for d in state["ingredients"]]
    nutrition = retrieve_nutrition(ingredients)
    return {
        "rag_nutrition": [n.model_dump() for n in nutrition],
        "rag_total_calories": sum(n.calories for n in nutrition),
        "rag_total_protein": sum(n.protein_g for n in nutrition),
        "rag_total_carbs": sum(n.carbs_g for n in nutrition),
        "rag_total_fat": sum(n.fat_g for n in nutrition),
    }


def usda_node(state: GraphState) -> GraphState:
    """Nodo USDA API — datos nutricionales estructurados usados en UI e informe."""
    if state.get("error"):
        return {}
    ingredients = [Ingredient(**d) for d in state["ingredients"]]
    nutrition = search_nutrition_usda(ingredients)
    return {
        "nutrition": [n.model_dump() for n in nutrition],
        "total_calories": sum(n.calories for n in nutrition),
        "total_protein": sum(n.protein_g for n in nutrition),
        "total_carbs": sum(n.carbs_g for n in nutrition),
        "total_fat": sum(n.fat_g for n in nutrition),
    }


def reasoning_node(state: GraphState) -> GraphState:
    if state.get("error"):
        return {}
    agent_state = AgentState(**state)
    report = generate_report(agent_state)
    return {"report": report}


def should_continue(state: GraphState) -> str:
    return END if state.get("error") else "rag"


# ── Grafo ────────────────────────────────────────────────

def build_graph() -> StateGraph:
    graph = StateGraph(GraphState)

    graph.add_node("vision", vision_node)
    graph.add_node("rag", rag_node)
    graph.add_node("usda", usda_node)
    graph.add_node("reasoning", reasoning_node)

    graph.set_entry_point("vision")
    graph.add_conditional_edges("vision", should_continue, {"rag": "rag", END: END})
    graph.add_edge("rag", "usda")
    graph.add_edge("usda", "reasoning")
    graph.add_edge("reasoning", END)

    return graph.compile()


nutrivision_graph = build_graph()
