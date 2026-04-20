"""Módulo RAG: recupera información nutricional de la base vectorial USDA."""

import chromadb
from chromadb.config import Settings

from config import CHROMA_DIR
from utils.schemas import Ingredient, NutritionInfo


def _get_collection() -> chromadb.Collection:
    client = chromadb.PersistentClient(path=CHROMA_DIR, settings=Settings(anonymized_telemetry=False))
    return client.get_collection("usda_foods")


def retrieve_nutrition(ingredients: list[Ingredient]) -> list[NutritionInfo]:
    """Busca cada ingrediente en la base vectorial y devuelve sus datos nutricionales."""
    collection = _get_collection()
    results: list[NutritionInfo] = []

    for ing in ingredients:
        query_result = collection.query(
            query_texts=[ing.name],
            n_results=1,
        )

        if not query_result["documents"] or not query_result["documents"][0]:
            # Si no se encuentra, devolver vacío con el nombre
            results.append(NutritionInfo(ingredient=ing.name, grams=ing.estimated_grams))
            continue

        meta = query_result["metadatas"][0][0]

        # Los valores en USDA son por 100 g → escalar a la porción estimada
        factor = ing.estimated_grams / 100.0
        results.append(
            NutritionInfo(
                ingredient=ing.name,
                grams=ing.estimated_grams,
                calories=meta.get("calories", 0) * factor,
                protein_g=meta.get("protein_g", 0) * factor,
                carbs_g=meta.get("carbs_g", 0) * factor,
                fat_g=meta.get("fat_g", 0) * factor,
                fiber_g=meta.get("fiber_g", 0) * factor,
                source=f"USDA: {meta.get('fdc_id', 'N/A')}",
            )
        )

    return results
