# Pipeline TODO & Documentation

## Current State

`combined_final.csv` (~148k rows) is committed directly to the repo. It is the result of a series of
manual notebook steps and serves as the starting point for the automated pipeline.

## Full Data Lineage

```
Raw USDA FoodData Central CSVs          Raw OFF data
  raw_data/FoodData_Central_csv_*/        (downloaded separately)
  food.csv, food_nutrient.csv, etc.
        |                                       |
   data_acq.ipynb                          data_acq.ipynb
        |                                       |
  usda_data_cats.csv                     off_data_clean2.csv
        |                                       |
  building_ont_filter/ notebooks    building_ont_filter/ notebooks
  (ontology mapping + dedup)         (ontology mapping)
        |                                       |
   usda_final.csv                    off_data_ontology.csv
             \                       /
          OFF Ontology Data Cleaning.ipynb
                     |
              combined_final.csv          <-- committed to git, pipeline starts here
                     |
        flows/build_food_reference_data.py  (Prefect)
                     |
        data/processed/combined_final_validated.csv
                     |
        faiss_index/build_index.py
                     |
        data/faiss_index/food.index
        data/faiss_index/food_meta.pkl
```

## Running the Automated Pipeline (Steps that exist today)

Requires: `combined_final.csv` in the repo root.

**Step 1 — Start the Prefect server** (in one terminal):
```bash
.venv/bin/prefect server start
```

**Step 2 — Run the validation + export flow** (in a second terminal):
```bash
.venv/bin/python flows/build_food_reference_data.py
```

**Step 3 — Build the FAISS index:**
```bash
.venv/bin/python faiss_index/build_index.py
```

Outputs:
- `data/processed/combined_final_validated.csv`
- `data/processed/rejected_food_rows.csv`
- `data/faiss_index/food.index`
- `data/faiss_index/food_meta.pkl`

## TODO — What Is Not Yet Automated

The steps that produce `combined_final.csv` from raw data are currently spread across notebooks
and must be run manually in order. If the raw USDA or OFF data is updated, these steps need to
be re-run by hand.

### Notebooks to run in order (manual today)

| Order | Notebook | Input | Output |
|-------|----------|-------|--------|
| 1 | `data_acq.ipynb` | `raw_data/FoodData_Central_csv_*/` | `usda_data_cats.csv` |
| 2 | `building_ont_filter/mapping_usda_only.ipynb` | `usda_data_cats.csv` | `usda_final.csv` |
| 3 | `building_ont_filter/building_ont_filter_new.ipynb` | `off_data_clean2.csv` | `off_data_ontology.csv` |
| 4 | `OFF Ontology Data Cleaning.ipynb` | `off_data_ontology.csv` + `usda_final.csv` | `combined_final.csv` |

### Future work: consolidate notebooks into a Prefect flow

- [ ] Convert notebook steps 1–4 above into a single Prefect flow
      (`flows/build_combined_csv.py` or similar)
- [ ] Add raw data download step (USDA FoodData Central bulk export URL,
      OFF CSV download link)
- [ ] Chain the new flow into `build_food_reference_data.py` so the full
      pipeline runs end-to-end from raw data → FAISS index in one command
- [ ] Add the raw data source URLs and download instructions to this file
      once confirmed
