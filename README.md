# SayFit — Food Tracking Data Pipeline

This repository contains the food macro database pipeline powering **SayFit**. It combines USDA and Open Food Facts data, cleans and standardises food names, deduplicates USDA entries, applies ontology labels, and produces search-ready CSV outputs.

---

## What’s in this repo

The current workflow documented in the notebooks focuses on two key processing stages:

1. **OFF Ontology Data Cleaning** — clean `off_data_ontology.csv` without deduplication
2. **USDA Deduplication Pipeline** — deduplicate USDA food names using blocking + fuzzy matching + clustering

There are also supporting notebooks and scripts for data acquisition, ontology mapping, and DuckDB database generation.

---

## Key files

| File | Purpose |
|---|---|
| `OFF Ontology Data Cleaning.ipynb` | Cleans the ontology-labeled OFF dataset without fuzzy deduplication |
| `USDA Deduplication Pipeline.ipynb` | Documents and runs USDA name deduplication |
| `data_acq.ipynb` | Earlier data acquisition and preprocessing work |
| `build_usda_duckdb.py` | Rebuilds `usda.duckdb` from raw USDA CSV files |
| `requirements.txt` | Python dependencies for notebooks and scripts |
| `off.duckdb` | Local DuckDB database for OFF data |
| `usda_data_clean2.csv` | Cleaned USDA source used before deduplication |
| `off_data_clean2.csv` | Cleaned OFF source used in earlier stages |
| `usda_final.csv` | Final USDA dataset with ontology labels |

---

## OFF ontology cleaning pipeline

Documented in `OFF Ontology Data Cleaning.ipynb`.

### Goal

Clean `off_data_ontology.csv` while **keeping duplicates for now**.

### Input

| Attribute | Value |
|---|---|
| File | `off_data_ontology.csv` |
| Rows (raw) | 40,996 |
| Columns | `item_name`, `cat`, `kcal_100g`, `fat_100g`, `carbs_100g`, `protein_100g`, `source`, `cat_l1`, `cat_l2`, `cat_l3` |

### Cleaning steps

1. Load with `pandas.read_csv()`
2. Ensure `item_name` is a string and strip whitespace
3. Lowercase and replace hyphens with spaces
4. Remove rows where `item_name` has more than 5 words
5. Remove rows containing measurement keywords
6. Remove rows containing digits
7. Normalise Unicode and special characters

### Documented row drops

| Step | Dropped |
|---|---:|
| More than 5 words | 6,984 |
| Measurement keywords | 4,289 |
| Digits in name | 1,573 |
| Empty after normalisation | 130 |

### Output

| Attribute | Value |
|---|---|
| File | `off_data_ontology_clean.csv` |
| Rows (cleaned) | 28,020 |
| Unique `item_name` | 21,008 |

> This step intentionally does **not** perform fuzzy matching or deduplication.

---

## USDA deduplication pipeline

Documented in `USDA Deduplication Pipeline.ipynb`.

### Goal

Collapse near-duplicate USDA food names into one canonical representation.

### Core idea

The USDA pipeline first creates a normalised field called `item_norm`, then applies a staged deduplication strategy:

1. Exact matching on `item_norm`
2. Blocking to reduce pairwise comparisons
3. Fuzzy matching inside blocks using `rapidfuzz`
4. BFS clustering over similar pairs
5. Canonical-name selection per cluster
6. Final deduplication on `item_canonical`

### `item_norm` transformation

`item_name` is transformed as follows:

```text
unicode → ASCII → lowercase → remove special chars → tokenise → deduplicate tokens → sort tokens alphabetically → rejoin
```

Example:

```text
"Chicken, Breast" → "breast chicken"
```

### Blocking strategy

To avoid $O(n^2)$ comparisons across the entire USDA dataset, names are grouped by:

```python
block_key = (first_4_chars_of_first_token, token_count, first_char_of_first_token)
```

Only names in the same block are compared.

### Fuzzy matching

- Library: `rapidfuzz`
- Function: `fuzz.token_set_ratio`
- Threshold: `95`

Pairs scoring at least 95 are added as edges in a graph.

### Clustering

Connected components in the similarity graph are found using **Breadth-First Search (BFS)**. Each connected component is treated as one deduplication cluster.

### Canonical selection

Within each cluster, the canonical name is selected by:

1. Highest frequency in the original dataset
2. Shortest name
3. Alphabetical order

### Finalisation

- Map all names to `item_canonical`
- Remove duplicates on `item_canonical`
- Remove repeated tokens inside names
- Replace `item_name` with the canonical value
- Drop helper columns `item_norm` and `item_canonical`
- Save to `usda_data_dedup_final.csv`

---
# Prefect Data Engineering Pipeline

## Overview

This project includes a Prefect-based data engineering pipeline for processing, validating, transforming, and indexing the food reference dataset.

The pipeline transforms the existing `combined_final.csv` dataset into a validated and structured DuckDB-based data layer, followed by dbt transformations and FAISS index generation for semantic food retrieval.

---

## Pipeline Architecture

```text
RAW CSV
↓
Prefect orchestration
↓
Cleaning + validation
↓
DuckDB storage
↓
dbt transformations
↓
Validated CSV export
↓
SentenceTransformer embeddings
↓
FAISS index generation
```

---

## Pipeline Steps

The workflow currently performs the following steps:

1. Input file validation
2. CSV loading
3. Basic cleaning
   - duplicate removal
   - removal of fully empty rows
4. Data validation
   - required column checks
   - missing item name checks
   - numeric value validation
   - realistic nutrition range validation
5. Export to DuckDB
6. dbt transformation layers
   - staging
   - intermediate
   - marts
7. Export of validated CSV
8. SentenceTransformer embedding generation
9. FAISS index generation

---

## Validation Rules

The current validation layer checks:

- `item_name` must not be empty
- nutrition columns must contain numeric values
- `kcal_100g` must be between 0 and 1000
- `fat_100g` must be between 0 and 100
- `carbs_100g` must be between 0 and 100
- `protein_100g` must be between 0 and 100

Invalid rows are exported separately for data quality monitoring.

---

## dbt Transformation Layers

The dbt project currently uses a layered transformation structure:

```text
staging
→ intermediate
→ marts
```

Current models:

- `stg_food_items`
- `int_food_items_cleaned`
- `mart_food_items_final`

---

## FAISS Index Output

The pipeline generates the following retrieval artifacts for `sayfit-alpha`:

```text
data/faiss_index/food.index
data/faiss_index/food_meta.pkl
```

The FAISS index is built using:

```text
sentence-transformers/all-MiniLM-L6-v2
```

The metadata file maintains row-order alignment with the FAISS vectors.

---

## Technologies Used

- Prefect
- DuckDB
- dbt
- pandas
- FAISS
- sentence-transformers
- Python 3.11.3

---

## Running the Pipeline

Run the Prefect pipeline from the repository root:

```bash
python flows/build_food_reference_data.py
```

Run the FAISS index build step:

```bash
python scripts/build_faiss_index.py
```

Run dbt transformations:

```bash
cd dbt_sayfit/sayfit_food_data
dbt run
```

---

## Output

The pipeline generates:

### Validated CSV export

```text
data/processed/combined_final_validated.csv
```

### Rejected rows export

```text
data/processed/rejected_food_rows.csv
```

### DuckDB database

```text
data/sayfit_food_pipeline.duckdb
```

### FAISS retrieval artifacts

```text
data/faiss_index/food.index
data/faiss_index/food_meta.pkl
```

---

## Purpose

The goal of this pipeline is to make the food data preparation process:

- reproducible
- observable
- easier to validate
- modular
- easier to extend
- compatible with semantic retrieval systems
- compatible with downstream recommendation systems

---

## Setup

Create and activate a virtual environment, then install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If you need the OpenAI-powered ontology steps later, add an `.env` file:

```bash
echo "OPENAI_API_KEY=sk-..." > .env
```

---

## Requirements

The current notebooks and scripts use:

- `python-dotenv`
- `openai`
- `pandas`
- `jupyterlab`
- `duckdb`
- `rapidfuzz`
- `numpy`
- `matplotlib`
- `ipykernel`
- `ipywidgets`

---

## Notes

- `rapidfuzz` is required for USDA deduplication.
- `duckdb` is used for local database-backed processing and larger source data handling.
- `matplotlib` and `numpy` support analysis and notebook EDA.
- `ipykernel` and `ipywidgets` make the notebook environment smoother and reproducible.
- `python-dotenv` is the correct package name for loading `.env` files in Python.

---

## Running with Docker

Docker packages Python 3.11, all pip dependencies, and the embedding model into a single image — no virtual environment setup needed.

### Build the image

```bash
docker build -t sayfit-data .
```

> The first build downloads all packages and the `all-MiniLM-L6-v2` embedding model (~90 MB). This takes a few minutes. Subsequent builds use the layer cache and are fast.

### Run the full pipeline

```bash
docker run --rm -v $(pwd)/data:/app/data sayfit-data
```

This runs both steps in sequence:

1. **Prefect validation flow** — validates `combined_final.csv` → writes to DuckDB → exports `data/processed/combined_final_validated.csv`
2. **FAISS index build** — embeds food items → writes `data/faiss_index/food.index` and `data/faiss_index/food_meta.pkl`

The `-v $(pwd)/data:/app/data` flag mounts your local `./data/` directory so all outputs land on the host machine. The `--rm` flag removes the stopped container automatically after it finishes.

### Run a single step

```bash
# Step 1 only — validation + DuckDB
docker run --rm -v $(pwd)/data:/app/data sayfit-data python flows/build_food_reference_data.py

# Step 2 only — FAISS index (requires step 1 to have run first)
docker run --rm -v $(pwd)/data:/app/data sayfit-data python scripts/build_faiss_index.py
```

### Output files

After a successful run, `./data/` contains:

| Path | Description |
|---|---|
| `data/processed/combined_final_validated.csv` | Validated food items used to build the index |
| `data/processed/rejected_food_rows.csv` | Rows that failed nutrition range validation |
| `data/sayfit_food_pipeline.duckdb` | DuckDB database with the validated food table |
| `data/faiss_index/food.index` | FAISS vector index (consumed by `sayfit-alpha`) |
| `data/faiss_index/food_meta.pkl` | Metadata pickle aligned row-for-row with the index |
