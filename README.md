# SayFit — Food Tracking Data Pipeline

In this subolder the food macro database powering **SayFit**, is build.

The pipeline ingests two public nutrition datasets (USDA FoodData Central + Open Food Facts), cleans and harmonises them, then classifies every food item into a 3-level category hierarchy using an LLM. The resulting dataset is used for fast fuzzy lookup at query time.

---

## Repository Structure

```
csv_capstone/
│
├── data_acq.ipynb                  # Step 1 — Data acquisition & cleaning
├── eda_new.ipynb                   # Step 3 — Exploratory analysis & visualisations
│
├── building_ont_filter/            # Step 2 — Category ontology pipeline
│   ├── building_ont_filter_new.ipynb   # Main ontology builder (run this)
│   ├── building_ont_filter.ipynb       # V1 prototype (reference only)
│   ├── mapping.ipynb                   # Category mapping experiments
│   ├── mapping_usda_only.ipynb         # USDA-specific mapping experiments
│   ├── eda_ontology.ipynb              # EDA over ontology outputs
│   │
│   ├── category_mapping2.csv/json  # Final LLM category mapping (L1/L2 lookup)
│   ├── category_mapping.csv/json   # V1 mapping (reference)
│   ├── usda_data_dedup_final.csv   # Deduplicated USDA input for LLM classification
│   ├── usda_data_ontology.csv      # USDA with L1/L2/L3 applied
│   ├── usda_dedup_ontology.csv     # Intermediate dedup + ontology (v1)
│   ├── usda_dedup_ontology2.csv    # Intermediate dedup + ontology (v2)
│   └── off_data_ontology.csv       # OFF with ontology applied
│
├── FoodData_Central_csv_2025-12-18/    # Raw USDA CSVs (read-only source)
│   ├── food.csv
│   ├── food_nutrient.csv
│   ├── food_category.csv
│   ├── food_portion.csv
│   ├── branded_food.csv
│   ├── nutrient.csv
│   └── ... (30+ supporting tables)
│
├── old/                            # Raw source archives (do not load in notebook)
│   ├── en.openfoodfacts.org.products.csv   # 12 GB raw OFF TSV download
│   ├── FoodData_Central_branded_food_json_2025-12-18.json  # 3.1 GB USDA JSON
│   └── off_nutrition_clean.csv             # Cleaned OFF subset (item_id, brand, serving_size)
│
├── usda_final.csv                  # Final USDA output with ontology labels
├── combined_final.csv              # Final combined USDA + OFF dataset
├── usda_data_cats.csv              # Intermediate: USDA items with raw categories
├── usda_data_clean2.csv            # Intermediate: cleaned USDA items
├── off_data_clean2.csv             # Intermediate: cleaned OFF items
├── usda.duckdb                     # USDA DuckDB database (~675 MB, not in repo — see build_usda_duckdb.py)
├── off.duckdb                      # OFF DuckDB database (~9 MB)
├── build_usda_duckdb.py            # Script to regenerate usda.duckdb from raw CSVs
│
├── requirements.txt
├── .env                            # OpenAI API key (never commit)
└── .python-version                 # pyenv Python version pin
```

---

## Data Sources

| Source | Format | Size | Description |
|--------|--------|------|-------------|
| [USDA FoodData Central](https://fdc.nal.usda.gov/download-foods) | CSV (30+ tables) | ~500 MB | Structured nutrition DB covering SR Legacy, Foundation Foods, FNDDS, and Branded Foods |
| [Open Food Facts](https://world.openfoodfacts.org/data) | TSV (single file) | ~12 GB | Crowdsourced global food product database with barcodes, brands, and macro nutrients |

---

## Setup

### 1. Clone & create environment

```bash
git clone <repo>
cd csv_capstone
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Download raw data

**USDA:** Download the full CSV zip from [https://fdc.nal.usda.gov/download-foods](https://fdc.nal.usda.gov/download-foods) and extract into `raw_data/FoodData_Central_csv_2025-12-18/`.

**Open Food Facts:** Download `en.openfoodfacts.org.products.csv` from [https://world.openfoodfacts.org/data](https://world.openfoodfacts.org/data) and place it in `old/`.

### 3. Add your OpenAI API key

```bash
echo "OPENAI_API_KEY=sk-..." > .env
```

This is required by Step 2 (ontology filter). The classification run costs approximately $0.05–0.10 using `gpt-4o-mini`.

---

## How to Run

Execute the three notebooks in order:

### Step 1 — `data_acq.ipynb`

Loads raw USDA CSVs and the OFF TSV, cleans both, harmonises column names, and exports intermediate files.

**What it does:**

1. Loads USDA tables from `FoodData_Central_csv_2025-12-18/` via DuckDB
2. Pivots `food_nutrient.csv` from long format to wide (one row per food item with macro columns)
3. Resolves numeric category IDs via `food_category.csv` and `wweia_food_category.csv`
4. Loads OFF from `old/en.openfoodfacts.org.products.csv` (tab-separated, 12 GB)
5. Filters language-tagged rows (e.g. `fr:lait`) and lowercases all text
6. Normalises both datasets to the shared schema: `item_name`, `cat`, `kcal_100g`, `protein_100g`, `carbs_100g`, `fat_100g`, `source`

**Outputs:**
- `usda_data_cats.csv` — USDA items with raw category strings
- `usda_data_clean2.csv` — cleaned USDA items
- `off_data_clean2.csv` — cleaned OFF items

---

### Step 2 — `building_ont_filter/building_ont_filter_new.ipynb`

The core of the pipeline. Classifies every unique food category string into a 3-level taxonomy using an LLM, then applies those labels to the full dataset.

**What it does:**

#### Phase 1: Gather categories
- Loads `usda_data_dedup_final.csv`
- Counts all unique category strings; filters to **meaningful categories** (≥3 items), discarding singletons as noise

#### Phase 2: Define taxonomy
The target taxonomy has three levels:

| Level | Description | Example |
|-------|-------------|---------|
| `cat_l1` | ~20 broad groups | `"dairy & eggs"` |
| `cat_l2` | ~60 specific groups | `"yogurt"` |
| `cat_l3` | original raw string | `"Yogurt, plain, low fat"` |

Full L1 groups include: `dairy & eggs`, `meat`, `poultry`, `seafood`, `fruits`, `vegetables`, `grains & pasta`, `bread & bakery`, `baked goods`, `snacks`, `beverages`, `condiments & sauces`, `fats & oils`, `legumes & nuts`, `prepared & frozen meals`, `soups & stews`, `spices & seasonings`, `sweets & desserts`, `baby food & formula`, `supplements & other`.

#### Phase 3: LLM batch classification
- Sends each unique category string to `gpt-4o-mini` via the OpenAI API
- The model returns one `cat_l2` label per category
- `cat_l1` is derived automatically from the L2→L1 lookup map
- Invalid responses that fall outside the defined L2 list are caught and set to `"other"`
- Results are saved immediately to `category_mapping2.csv` and `category_mapping2.json` so the API is never called twice

#### Phase 4: Apply mapping
- Maps `cat_l1` and `cat_l2` onto every row in the USDA dataset using the lookup table
- Rows with unmapped categories (tiny categories with <3 items) are assigned `"other"`

#### Phase 5: Manual fixes
- Audits all categories classified as `"other"` by the LLM
- Adds new L2 buckets where warranted (e.g. `"crusts & dough"`, `"organ meats"`, `"fast foods & restaurant foods"`)
- Patches the mapping CSV with manual overrides
- Re-applies updated mapping to the full dataset

#### Phase 6: Final filter & export
- Drops rows where `cat_l1` or `cat_l2` is `"other"` or `"baby food"` (not useful for macro search)
- Exports clean columns to `usda_final.csv`

**Outputs:**
- `category_mapping2.csv` / `category_mapping2.json` — the reusable lookup table
- `usda_dedup_ontology2.csv` — annotated USDA dataset (with all rows, including "other")
- `usda_final.csv` — final filtered USDA dataset ready for search

**Cost:** ~$0.05–0.10 (OpenAI `gpt-4o-mini`, run once)

---

### Step 3 — `eda_new.ipynb`

Exploratory analysis and visualisations for presentation purposes.

**What it does:**

1. Connects to `usda.duckdb` and `off.duckdb`
2. Runs a 4-table LEFT JOIN to produce a unified USDA view (food + nutrients + category + portions)
3. Analyses word count distributions for item descriptions and category strings
4. Merges USDA `category` and OFF `categories_en` into one unified column
5. Renders styled histograms showing macro and description distributions

All charts use a dark terminal theme: `#0a0a0a` background, `#00ff41` (matrix green) bars.

---

## Output Schema

### `usda_final.csv`

| Column | Type | Description |
|--------|------|-------------|
| `item_name` | string | Food description |
| `kcal_100g` | float | Calories per 100g |
| `fat_100g` | float | Total fat per 100g |
| `carbs_100g` | float | Total carbs per 100g |
| `protein_100g` | float | Protein per 100g |
| `source` | string | `"usda"` |
| `cat_l1` | string | Broad category (e.g. `"dairy & eggs"`) |
| `cat_l2` | string | Specific category (e.g. `"yogurt"`) |
| `cat_l3` | string | Original raw category string |

### `combined_final.csv`

Same as above but merges USDA + OFF rows with a `source` column (`"usda"` or `"off"`). Does not include `cat_l3`.

---

## Category Mapping Files

`building_ont_filter/category_mapping2.csv` and `category_mapping2.json` are the reusable lookup tables produced by the LLM classification step.

| Column | Description |
|--------|-------------|
| `original_cat` | Raw category string from USDA or OFF |
| `cat_l2` | Assigned L2 label |
| `cat_l1` | Derived L1 label |

These files are the most expensive artifact to produce (API cost + time) and should be committed to version control so the LLM batch never needs to run again.

---

## Requirements

```
dotenv
openai
pandas
jupyterlab
```

Also used (install manually if not present):
- `duckdb`
- `numpy`
- `matplotlib`

---

## Building `usda.duckdb`

`usda.duckdb` (~675 MB) is too large to commit to GitHub. Regenerate it from the raw USDA CSVs using the included build script:

```bash
python build_usda_duckdb.py
```

> **Prerequisite:** the raw CSVs must already be present at `raw_data/FoodData_Central_csv_2025-12-18/` (see [Download raw data](#2-download-raw-data) above).

The script creates the following tables inside `usda.duckdb`:

| Table | Source | Description |
|-------|--------|-------------|
| `food` | `food.csv` | All food items (fdc_id, description, food_category_id) |
| `food_category` | `food_category.csv` | 28 USDA category labels |
| `food_nutrient` | `food_nutrient.csv` | Long-format nutrient values (~27 M rows) |
| `food_portion` | `food_portion.csv` | Serving-size / gram-weight data |
| `nutrient` | `nutrient.csv` | Nutrient ID → name lookup (477 nutrients) |
| `food_typed` | derived | `food` with `fdc_id` cast to `BIGINT` |
| `food_nutrient_typed` | derived | `food_nutrient` with proper numeric types |
| `nutrient_typed` | derived | `nutrient` with `id` cast to `INTEGER` |
| `usda_macros` | derived | Wide-format pivot: one row per food with `kcal_100g`, `protein_100g`, `carbs_100g`, `fat_100g` (~2.1 M rows) |
| `usda_macros_clean` | derived | `usda_macros` with rows missing any macro dropped (~1.8 M rows) |

The pivot uses macro nutrient IDs: `1008` (Energy/kcal), `1003` (Protein), `1005` (Carbohydrate), `1004` (Total fat).

Expected runtime: ~2–5 minutes on a modern laptop. The resulting file will be ~675 MB.

---

## Notes

- **Never load `old/en.openfoodfacts.org.products.csv` or `FoodData_Central_csv_2025-12-18/` directly with `pd.read_csv()`** without chunking or a DuckDB query — these files are 12 GB and 500 MB respectively and will crash the kernel.
- `usda.duckdb` and `off.duckdb` provide a memory-safe way to query the raw data using SQL without loading it all into RAM.
- The `.env` file must contain `OPENAI_API_KEY` for the ontology builder to work. It is gitignored and must never be committed.
