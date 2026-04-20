# NutriVision 🍽️

Agente multimodal de análisis nutricional por imagen. Fotografía un plato y obtén al instante calorías, macros e informe personalizado.

## Estructura del Proyecto

```
nutrivision/
├── app.py                   # Streamlit — punto de entrada principal
├── config.py                # Configuración global (modelos, rutas, API keys)
├── requirements.txt
├── .env.example
├── agents/
│   ├── graph.py             # LangGraph — orquestación del pipeline
│   ├── vision.py            # Nodo de visión: identifica ingredientes y porciones
│   ├── rag.py               # Nodo RAG: recuperación nutricional por embeddings
│   ├── usda_nutrition.py    # Nodo USDA: consulta FoodData Central API
│   └── reasoning.py        # Nodo razonador: genera el informe final
├── data/
│   ├── usda_loader.py       # Descarga y preprocesado USDA FoodData Central
│   ├── vector_store.py      # Construcción del índice ChromaDB
│   ├── db.py                # SQLite: usuarios y registro diario de comidas
│   ├── usda_foods.csv       # Cache local de alimentos USDA (generado)
│   ├── nutrivision.db       # Base de datos SQLite (generada)
│   └── chroma_db/           # Índice vectorial ChromaDB (generado)
├── pages/
│   └── 1_Dashboard.py       # Página de historial y progreso diario
├── utils/
│   ├── schemas.py           # Pydantic schemas (AgentState, Ingredient, etc.)
│   └── prompts.py           # Plantillas de prompts (visión y razonamiento)
└── eval/
    ├── evaluate.py          # Script de evaluación (F1, MAE, latencia)
    ├── test_images/         # 14 imágenes anotadas para evaluación
    └── results_final.json   # Resultados de la evaluación final
```

## Requisitos

- Python 3.10 o superior
- Conexión a internet (APIs externas de visión y USDA)

## Instalación

```bash
# 1. Crear y activar entorno virtual
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 2. Instalar dependencias
pip install -r requirements.txt

# Si tienes GPU NVIDIA, reemplaza torch por la versión CUDA (más rápido):
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

> Sin GPU, `torch` se instala en versión CPU automáticamente y el sistema funciona igual (sentence-transformers lo usa solo para los embeddings del RAG).

## Configuración

Copia el fichero de ejemplo y rellena tus claves:

```bash
cp .env.example .env
```

Edita `.env` con tus credenciales:

```env
HF_TOKEN=hf_...          # HuggingFace — modelo de visión principal (Qwen2.5-VL-72B)
GROQ_API_KEY=gsk_...     # Groq — fallback de visión (Llama-4-Scout-17B), gratuito
GOOGLE_API_KEY=...       # Google AI — fallback secundario (Gemini 2.0 Flash)
USDA_API_KEY=...         # USDA FoodData Central — gratuito en demo.nal.usda.gov/api-guide
TAVILY_API_KEY=tvly-...  # Tavily — no usado en producción, solo legacy
```

> El sistema funciona sin `GOOGLE_API_KEY` y sin `TAVILY_API_KEY`. Con solo `HF_TOKEN` + `GROQ_API_KEY` + `USDA_API_KEY` es suficiente.

## Preparar los datos (primera vez)

```bash
# Descarga ~300 alimentos de USDA y genera usda_foods.csv
python -m data.usda_loader

# Construye el índice vectorial ChromaDB a partir del CSV
python -m data.vector_store
```

Esto solo hay que hacerlo una vez. Los ficheros generados (`usda_foods.csv`, `chroma_db/`, `nutrivision.db`) se crean automáticamente en `data/`.

## Ejecutar la aplicación

```bash
streamlit run app.py
```

Se abre en `http://localhost:8501`. El flujo es:

1. **Perfil** — introduce edad, peso, altura, nivel de actividad y objetivo.
2. **Análisis** — sube una foto del plato y selecciona el tipo de comida.
3. **Informe** — el agente identifica ingredientes, consulta USDA y genera el informe nutricional.
4. **Dashboard** — historial de 30 días con progreso de macros y calorías.

## Ejecutar la evaluación

```bash
# Elimina resultados previos si los hay y lanza la evaluación completa
rm eval/results.json  # opcional, para forzar re-evaluación
python -m eval.evaluate
```

Evalúa las 14 imágenes de `eval/test_images/` y guarda métricas en `eval/results.json`. Al terminar imprime:

- **F1, Precisión, Recall** de identificación de ingredientes
- **MAE** de calorías, proteínas, carbohidratos y grasa (absoluto y porcentual)
- Comparativa RAG vs. USDA API
- Latencia media por imagen

## Cadena de fallback del módulo de visión

El sistema intenta los proveedores en este orden:

1. **Qwen2.5-VL-72B-Instruct** via HuggingFace Inference API (`HF_TOKEN`)
2. **Llama-4-Scout-17B** via Groq (`GROQ_API_KEY`) — gratuito, 14.400 req/día
3. **Gemini 2.0 Flash** via Google AI (`GOOGLE_API_KEY`) — con reintentos ante rate-limit

Si un proveedor falla o no está configurado, pasa automáticamente al siguiente.
