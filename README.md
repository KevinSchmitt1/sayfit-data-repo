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
