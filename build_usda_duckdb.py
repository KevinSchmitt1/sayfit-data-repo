"""
Build usda.duckdb from the raw USDA FoodData Central CSVs.

Usage:
    python build_usda_duckdb.py

Expects the raw CSVs in:
    raw_data/FoodData_Central_csv_2025-12-18/

Produces:
    usda.duckdb  (~675 MB)
"""

import duckdb

DATA_DIR = "raw_data/FoodData_Central_csv_2025-12-18"
DB_PATH = "usda.duckdb"

con = duckdb.connect(DB_PATH)

print("Loading raw CSV tables...")

con.execute(f"""
    CREATE OR REPLACE TABLE food AS
    SELECT fdc_id, data_type, description, food_category_id, publication_date
    FROM read_csv('{DATA_DIR}/food.csv', all_varchar=True, null_padding=True, parallel=False)
""")
print("  food: done")

con.execute(f"""
    CREATE OR REPLACE TABLE food_category AS
    SELECT * FROM read_csv('{DATA_DIR}/food_category.csv', all_varchar=True, null_padding=True, parallel=False)
""")
print("  food_category: done")

con.execute(f"""
    CREATE OR REPLACE TABLE food_nutrient AS
    SELECT * FROM read_csv('{DATA_DIR}/food_nutrient.csv', all_varchar=True, null_padding=True, parallel=False)
""")
print("  food_nutrient: done")

con.execute(f"""
    CREATE OR REPLACE TABLE food_portion AS
    SELECT * FROM read_csv('{DATA_DIR}/food_portion.csv', all_varchar=True, null_padding=True, parallel=False)
""")
print("  food_portion: done")

con.execute(f"""
    CREATE OR REPLACE TABLE nutrient AS
    SELECT * FROM read_csv('{DATA_DIR}/nutrient.csv', all_varchar=True, null_padding=True, parallel=False)
""")
print("  nutrient: done")

print("Creating typed tables...")

con.execute("""
    CREATE OR REPLACE TABLE food_typed AS
    SELECT TRY_CAST(fdc_id AS BIGINT) AS fdc_id, description
    FROM food
    WHERE TRY_CAST(fdc_id AS BIGINT) IS NOT NULL
""")

con.execute("""
    CREATE OR REPLACE TABLE food_nutrient_typed AS
    SELECT
        TRY_CAST(fdc_id     AS BIGINT)  AS fdc_id,
        TRY_CAST(nutrient_id AS INTEGER) AS nutrient_id,
        TRY_CAST(amount      AS DOUBLE)  AS amount
    FROM food_nutrient
    WHERE TRY_CAST(fdc_id AS BIGINT) IS NOT NULL
""")

con.execute("""
    CREATE OR REPLACE TABLE nutrient_typed AS
    SELECT TRY_CAST(id AS INTEGER) AS id, name
    FROM nutrient
    WHERE TRY_CAST(id AS INTEGER) IS NOT NULL
""")
print("  typed tables: done")

print("Building usda_macros (pivot food_nutrient on 4 macro nutrient IDs)...")

# Nutrient IDs: 1008=Energy(kcal), 1003=Protein, 1005=Carbohydrate, 1004=Fat
con.execute("""
    CREATE OR REPLACE TABLE usda_macros AS
    SELECT
        f.fdc_id,
        f.description,
        MAX(CASE WHEN fn.nutrient_id = 1008 THEN fn.amount END) AS kcal_100g,
        MAX(CASE WHEN fn.nutrient_id = 1003 THEN fn.amount END) AS protein_100g,
        MAX(CASE WHEN fn.nutrient_id = 1005 THEN fn.amount END) AS carbs_100g,
        MAX(CASE WHEN fn.nutrient_id = 1004 THEN fn.amount END) AS fat_100g
    FROM food_typed f
    LEFT JOIN food_nutrient_typed fn
        ON f.fdc_id = fn.fdc_id
       AND fn.nutrient_id IN (1008, 1003, 1005, 1004)
    GROUP BY f.fdc_id, f.description
""")
print("  usda_macros: done")

print("Building usda_macros_clean (drop rows missing any macro)...")

con.execute("""
    CREATE OR REPLACE TABLE usda_macros_clean AS
    SELECT *
    FROM usda_macros
    WHERE kcal_100g    IS NOT NULL
      AND protein_100g IS NOT NULL
      AND carbs_100g   IS NOT NULL
      AND fat_100g     IS NOT NULL
""")
print("  usda_macros_clean: done")

# Summary
for t in ["food", "food_category", "food_nutrient", "food_portion", "nutrient",
          "food_typed", "food_nutrient_typed", "nutrient_typed",
          "usda_macros", "usda_macros_clean"]:
    n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"  {t}: {n:,} rows")

con.close()
print(f"\nDone — {DB_PATH} written.")
