import pandas as pd
import chromadb
from chromadb.config import Settings
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from config import USDA_CSV_PATH, CHROMA_DIR, EMBEDDING_MODEL_ID


def build_vector_store():
    """Lee el CSV de USDA y crea una colección ChromaDB con embeddings."""
    df = pd.read_csv(USDA_CSV_PATH)
    print(f"Cargados {len(df)} alimentos desde {USDA_CSV_PATH}")

    client = chromadb.PersistentClient(path=CHROMA_DIR, settings=Settings(anonymized_telemetry=False))

    # Borrar colección si ya existe
    try:
        client.delete_collection("usda_foods")
    except Exception:
        pass

    ef = SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL_ID)
    collection = client.create_collection(
        name="usda_foods",
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )

    # Insertar en lotes
    batch_size = 50
    for i in range(0, len(df), batch_size):
        batch = df.iloc[i : i + batch_size]
        collection.add(
            ids=[str(row.fdc_id) for _, row in batch.iterrows()],
            documents=[row.description for _, row in batch.iterrows()],
            metadatas=[
                {
                    "fdc_id": str(row.fdc_id),
                    "calories": float(row.calories),
                    "protein_g": float(row.protein_g),
                    "carbs_g": float(row.carbs_g),
                    "fat_g": float(row.fat_g),
                    "fiber_g": float(row.fiber_g),
                }
                for _, row in batch.iterrows()
            ],
        )

    print(f"Indice vectorial creado en {CHROMA_DIR} ({collection.count()} documentos)")


if __name__ == "__main__":
    build_vector_store()
