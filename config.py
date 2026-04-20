import os
from dotenv import load_dotenv

load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# ── Modelos ──────────────────────────────────────────────
VISION_MODEL_ID = "Qwen/Qwen2.5-VL-72B-Instruct"        # HF Inference API
REASONING_MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"  # LLM razonador gratuito
EMBEDDING_MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"

# ── Rutas ────────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CHROMA_DIR = os.path.join(DATA_DIR, "chroma_db")
USDA_CSV_PATH = os.path.join(DATA_DIR, "usda_foods.csv")

# ── USDA API  ─────────────────────────
USDA_API_URL = "https://api.nal.usda.gov/fdc/v1"
USDA_API_KEY = os.getenv("USDA_API_KEY", "")

# ── Tavily ────────────────────────────────────────────────
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# ── Groq ─────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
