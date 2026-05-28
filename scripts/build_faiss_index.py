from pathlib import Path

import faiss
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer


INPUT_CSV = Path("data/processed/combined_final_validated.csv")
OUTPUT_DIR = Path("data/faiss_index")
INDEX_PATH = OUTPUT_DIR / "food.index"
META_PATH = OUTPUT_DIR / "food_meta.pkl"

EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def build_text_for_embedding(df: pd.DataFrame) -> pd.Series:
    return (
        df["item_name"].fillna("").astype(str)
        + " | category: "
        + df["cat_l1"].fillna("").astype(str)
        + " / "
        + df["cat_l2"].fillna("").astype(str)
    )


def main() -> None:
    if not INPUT_CSV.exists():
        raise FileNotFoundError(
            f"Input file not found: {INPUT_CSV}. "
            "Run the Prefect pipeline first."
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(INPUT_CSV)

    required_columns = [
        "item_name",
        "kcal_100g",
        "protein_100g",
        "carbs_100g",
        "fat_100g",
        "source",
        "cat_l1",
        "cat_l2",
    ]

    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    df = df.reset_index(drop=True).copy()

    if "doc_id" not in df.columns:
        df["doc_id"] = df["source"].astype(str) + "_" + df.index.astype(str)

    if "cat_l3" not in df.columns:
        df["cat_l3"] = ""

    df["text_for_embedding"] = build_text_for_embedding(df)

    keep_cols = [
        "doc_id",
        "source",
        "item_name",
        "kcal_100g",
        "protein_100g",
        "carbs_100g",
        "fat_100g",
        "cat_l1",
        "cat_l2",
        "cat_l3",
        "text_for_embedding",
    ]

    meta_df = df[keep_cols].copy()

    print(f"Loaded rows: {len(meta_df)}")
    print(f"Embedding model: {EMBEDDING_MODEL_NAME}")

    model = SentenceTransformer(EMBEDDING_MODEL_NAME)

    embeddings = model.encode(
        meta_df["text_for_embedding"].tolist(),
        batch_size=256,
        show_progress_bar=True,
        normalize_embeddings=True,
    )

    embeddings = np.asarray(embeddings, dtype="float32")

    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)

    faiss.write_index(index, str(INDEX_PATH))
    meta_df.to_pickle(META_PATH)

    print(f"Saved FAISS index to: {INDEX_PATH}")
    print(f"Saved metadata to: {META_PATH}")
    print(f"Index vectors: {index.ntotal}")
    print(f"Metadata rows: {len(meta_df)}")


if __name__ == "__main__":
    main()