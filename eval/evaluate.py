import argparse
import base64
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.rag import retrieve_nutrition
from agents.usda_nutrition import search_nutrition_usda
from agents.vision import identify_ingredients
from utils.schemas import Ingredient

EVAL_DIR = Path(__file__).parent / "test_images"

_STOPWORDS = {
    "raw", "cooked", "boiled", "canned", "dried", "fresh", "whole", "large",
    "grade", "regular", "quick", "light", "lean", "drained", "salted",
    "unsalted", "enriched", "plain", "all", "dry", "heat", "mature", "seeds",
    "flesh", "skin", "baked", "grilled", "sliced", "sweet",
}


def _key_words(name: str) -> set[str]:
    """Palabras clave de un nombre de alimento (sin stopwords ni puntuacion)."""
    words = set(re.sub(r"[,./()]", " ", name.lower()).split())
    meaningful = words - _STOPWORDS
    return meaningful if meaningful else words


def _names_match(gt_name: str, pred_name: str) -> bool:
    """True si comparten alguna palabra clave (maneja banana/bananas, oat/oats)."""
    gt_words = _key_words(gt_name)
    pred_words = _key_words(pred_name)
    return any(g in p or p in g for g in gt_words for p in pred_words)


# ── Metricas ─────────────────────────────────────────────

def _gt_totals(ground_truth: list[dict]) -> dict:
    return {k: sum(g.get(k, 0) for g in ground_truth)
            for k in ("calories", "protein_g", "carbs_g", "fat_g")}


def evaluate_identification(predicted: list[Ingredient], ground_truth: list[dict]) -> dict:
    gt_names   = [item["name"].lower() for item in ground_truth]
    pred_names = [ing.name.lower() for ing in predicted]

    matched_gt   = {g for g in gt_names   if any(_names_match(g, p) for p in pred_names)}
    matched_pred = {p for p in pred_names if any(_names_match(g, p) for g in gt_names)}

    precision = len(matched_pred) / len(pred_names) if pred_names else 0
    recall    = len(matched_gt)   / len(gt_names)   if gt_names   else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    return {
        "precision":    round(precision, 3),
        "recall":       round(recall,    3),
        "f1":           round(f1,        3),
        "predicted":    sorted(pred_names),
        "ground_truth": sorted(gt_names),
    }


def evaluate_portion_mae(predicted: list[Ingredient], ground_truth: list[dict]) -> float:
    errors = []
    for ing in predicted:
        for gt in ground_truth:
            if _names_match(gt["name"].lower(), ing.name.lower()):
                errors.append(abs(ing.estimated_grams - gt["grams"]))
                break
    return round(sum(errors) / len(errors), 1) if errors else float("nan")


def evaluate_nutrition_mae(predicted_nutrition: list, gt_totals: dict) -> dict:
    pred = {
        "calories":  sum(n.calories  for n in predicted_nutrition),
        "protein_g": sum(n.protein_g for n in predicted_nutrition),
        "carbs_g":   sum(n.carbs_g   for n in predicted_nutrition),
        "fat_g":     sum(n.fat_g     for n in predicted_nutrition),
    }
    mae_abs = {k: round(abs(pred[k] - gt_totals[k]), 1) for k in gt_totals}
    mae_pct = {
        k: round(abs(pred[k] - gt_totals[k]) / gt_totals[k] * 100, 1)
        if gt_totals[k] else float("nan")
        for k in gt_totals
    }
    return {"predicted": {k: round(v, 1) for k, v in pred.items()},
            "mae_abs": mae_abs, "mae_pct": mae_pct}


# ── Runner ────────────────────────────────────────────────

def run_evaluation(images_dir: Path, save_path: Path | None = None):
    json_files = sorted(images_dir.glob("*.json"))
    if not json_files:
        print(f"No se encontraron .json en {images_dir}")
        return

    # Cargar resultados previos si existen (modo resume)
    all_results = []
    done_images = set()
    if save_path and save_path.exists():
        with open(save_path, encoding="utf-8") as f:
            all_results = json.load(f)
        done_images = {r["image"] for r in all_results}
        print(f"Reanudando: {len(done_images)} imagen(es) ya completada(s): {sorted(done_images)}")

    for json_file in json_files:
        with open(json_file, encoding="utf-8") as f:
            gt = json.load(f)

        img_path = images_dir / gt["image_file"]
        if gt["image_file"] in done_images:
            print(f"[SKIP] Ya evaluada: {gt['image_file']}")
            continue
        if not img_path.exists():
            print(f"[SKIP] Imagen no encontrada: {img_path}")
            continue

        print(f"\n{'-'*60}")
        print(f"  Imagen: {gt['image_file']}")
        print(f"{'-'*60}")

        image_b64 = base64.b64encode(img_path.read_bytes()).decode()
        gt_totals = _gt_totals(gt["ingredients"])

        # -- Vision --
        t0 = time.time()
        try:
            predicted_ings = identify_ingredients(image_b64)
            t_vision = round(time.time() - t0, 2)
        except Exception as e:
            print(f"  [ERROR Vision] {e}")
            continue

        id_metrics   = evaluate_identification(predicted_ings, gt["ingredients"])
        portion_mae  = evaluate_portion_mae(predicted_ings, gt["ingredients"])

        print(f"\n  [Vision]  {t_vision:.1f}s")
        print(f"    Predicho:     {', '.join(id_metrics['predicted'])}")
        print(f"    Ground truth: {', '.join(id_metrics['ground_truth'])}")
        print(f"    P={id_metrics['precision']:.2f}  R={id_metrics['recall']:.2f}  F1={id_metrics['f1']:.2f}")
        print(f"    MAE porciones: {portion_mae} g")

        # -- RAG --
        t1 = time.time()
        try:
            rag_nutrition = retrieve_nutrition(predicted_ings)
        except Exception as e:
            print(f"  [ERROR RAG] {e}")
            rag_nutrition = []
        t_rag = round(time.time() - t1, 2)

        rag_mae = evaluate_nutrition_mae(rag_nutrition, gt_totals)
        print(f"\n  [RAG]  {t_rag:.1f}s")
        print(f"    Predicho:  cal={rag_mae['predicted']['calories']:.0f}  "
              f"prot={rag_mae['predicted']['protein_g']:.1f}  "
              f"carbs={rag_mae['predicted']['carbs_g']:.1f}  "
              f"fat={rag_mae['predicted']['fat_g']:.1f}")
        print(f"    MAE abs:   cal={rag_mae['mae_abs']['calories']:.0f}  "
              f"prot={rag_mae['mae_abs']['protein_g']:.1f}  "
              f"carbs={rag_mae['mae_abs']['carbs_g']:.1f}  "
              f"fat={rag_mae['mae_abs']['fat_g']:.1f}")
        print(f"    MAE %:     cal={rag_mae['mae_pct']['calories']:.1f}%  "
              f"prot={rag_mae['mae_pct']['protein_g']:.1f}%  "
              f"carbs={rag_mae['mae_pct']['carbs_g']:.1f}%  "
              f"fat={rag_mae['mae_pct']['fat_g']:.1f}%")

        # -- USDA API --
        t2 = time.time()
        try:
            usda_nutrition = search_nutrition_usda(predicted_ings)
        except Exception as e:
            print(f"  [ERROR USDA] {e}")
            usda_nutrition = []
        t_usda = round(time.time() - t2, 2)

        usda_mae = evaluate_nutrition_mae(usda_nutrition, gt_totals)
        print(f"\n  [USDA API]  {t_usda:.1f}s")
        print(f"    Predicho:  cal={usda_mae['predicted']['calories']:.0f}  "
              f"prot={usda_mae['predicted']['protein_g']:.1f}  "
              f"carbs={usda_mae['predicted']['carbs_g']:.1f}  "
              f"fat={usda_mae['predicted']['fat_g']:.1f}")
        print(f"    MAE abs:   cal={usda_mae['mae_abs']['calories']:.0f}  "
              f"prot={usda_mae['mae_abs']['protein_g']:.1f}  "
              f"carbs={usda_mae['mae_abs']['carbs_g']:.1f}  "
              f"fat={usda_mae['mae_abs']['fat_g']:.1f}")
        print(f"    MAE %:     cal={usda_mae['mae_pct']['calories']:.1f}%  "
              f"prot={usda_mae['mae_pct']['protein_g']:.1f}%  "
              f"carbs={usda_mae['mae_pct']['carbs_g']:.1f}%  "
              f"fat={usda_mae['mae_pct']['fat_g']:.1f}%")

        print(f"\n  [Ground truth]  "
              f"cal={gt_totals['calories']:.0f}  "
              f"prot={gt_totals['protein_g']:.1f}  "
              f"carbs={gt_totals['carbs_g']:.1f}  "
              f"fat={gt_totals['fat_g']:.1f}")

        all_results.append({
            "image": gt["image_file"],
            "latency_s": {
                "vision": t_vision, "rag": t_rag, "usda": t_usda,
                "total_rag":  round(t_vision + t_rag,  2),
                "total_usda": round(t_vision + t_usda, 2),
            },
            "identification": id_metrics,
            "portion_mae_g":  portion_mae,
            "rag":            rag_mae,
            "usda":           usda_mae,
            "ground_truth":   gt_totals,
        })

    if not all_results:
        return

    # -- Resumen --
    n = len(all_results)

    def avg_mae(src, field):
        return sum(r[src]["mae_abs"][field] for r in all_results) / n

    def avg_pct(src, field):
        vals = [r[src]["mae_pct"][field] for r in all_results
                if isinstance(r[src]["mae_pct"][field], float)]
        return sum(vals) / len(vals) if vals else float("nan")

    print(f"\n{'='*60}")
    print(f"  RESUMEN -- {n} imagen(es)")
    print(f"{'='*60}")
    print(f"\n  Identificacion de ingredientes:")
    print(f"    F1 medio:            {sum(r['identification']['f1'] for r in all_results)/n:.3f}")
    print(f"    Precision media:     {sum(r['identification']['precision'] for r in all_results)/n:.3f}")
    print(f"    Recall medio:        {sum(r['identification']['recall'] for r in all_results)/n:.3f}")
    portion_maes = [r["portion_mae_g"] for r in all_results if r["portion_mae_g"] == r["portion_mae_g"]]
    if portion_maes:
        print(f"    MAE porciones:       {sum(portion_maes)/len(portion_maes):.1f} g")

    print(f"\n  Nutricion -- MAE calorias:")
    print(f"    RAG:  {avg_mae('rag','calories'):.0f} kcal  ({avg_pct('rag','calories'):.1f}%)")
    print(f"    USDA: {avg_mae('usda','calories'):.0f} kcal  ({avg_pct('usda','calories'):.1f}%)")
    print(f"\n  Nutricion -- MAE proteina:")
    print(f"    RAG:  {avg_mae('rag','protein_g'):.1f} g  ({avg_pct('rag','protein_g'):.1f}%)")
    print(f"    USDA: {avg_mae('usda','protein_g'):.1f} g  ({avg_pct('usda','protein_g'):.1f}%)")
    print(f"\n  Nutricion -- MAE carbohidratos:")
    print(f"    RAG:  {avg_mae('rag','carbs_g'):.1f} g  ({avg_pct('rag','carbs_g'):.1f}%)")
    print(f"    USDA: {avg_mae('usda','carbs_g'):.1f} g  ({avg_pct('usda','carbs_g'):.1f}%)")
    print(f"\n  Nutricion -- MAE grasa:")
    print(f"    RAG:  {avg_mae('rag','fat_g'):.1f} g  ({avg_pct('rag','fat_g'):.1f}%)")
    print(f"    USDA: {avg_mae('usda','fat_g'):.1f} g  ({avg_pct('usda','fat_g'):.1f}%)")

    t_rag_avg  = sum(r["latency_s"]["total_rag"]  for r in all_results) / n
    t_usda_avg = sum(r["latency_s"]["total_usda"] for r in all_results) / n
    print(f"\n  Latencia media:")
    print(f"    RAG:  {t_rag_avg:.1f}s")
    print(f"    USDA: {t_usda_avg:.1f}s")

    if save_path:
        save_path.write_text(
            json.dumps(all_results, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"\n  Resultados guardados en: {save_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", type=Path, default=EVAL_DIR)
    parser.add_argument("--save",   type=Path, default=None)
    args = parser.parse_args()
    run_evaluation(args.images, args.save)
