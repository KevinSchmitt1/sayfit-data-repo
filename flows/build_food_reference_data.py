from pathlib import Path

import duckdb
import pandas as pd
from prefect import flow, task, get_run_logger


INPUT_CSV = Path("combined_final.csv")
OUTPUT_CSV = Path("data/processed/combined_final_validated.csv")
DUCKDB_PATH = Path("data/sayfit_food_pipeline.duckdb")


@task
def check_input_file() -> Path:
    logger = get_run_logger()

    if not INPUT_CSV.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_CSV}")

    logger.info(f"Found input file: {INPUT_CSV}")
    return INPUT_CSV


@task
def load_csv(path: Path) -> pd.DataFrame:
    logger = get_run_logger()

    df = pd.read_csv(path)
    logger.info(f"Loaded rows: {len(df)}")
    logger.info(f"Loaded columns: {list(df.columns)}")

    return df


@task
def basic_cleaning(df: pd.DataFrame) -> pd.DataFrame:
    logger = get_run_logger()

    before = len(df)

    df = df.copy()
    df = df.drop_duplicates()
    df = df.dropna(how="all")

    after = len(df)

    logger.info(f"Rows before cleaning: {before}")
    logger.info(f"Rows after cleaning: {after}")
    logger.info(f"Rows removed: {before - after}")

    return df

@task
def validate_food_data(df: pd.DataFrame) -> pd.DataFrame:
    logger = get_run_logger()

    before = len(df)
    df = df.copy()

    required_columns = [
        "item_name",
        "kcal_100g",
        "fat_100g",
        "carbs_100g",
        "protein_100g",
    ]

    missing_columns = [col for col in required_columns if col not in df.columns]

    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    missing_name_rows = len(df[df["item_name"].isna()])

    empty_name_rows = len(
        df[df["item_name"].astype(str).str.strip() == ""]
    )

    df = df[df["item_name"].notna()]
    df = df[df["item_name"].astype(str).str.strip() != ""]

    numeric_columns = [
        "kcal_100g",
        "fat_100g",
        "carbs_100g",
        "protein_100g",
    ]

    for col in numeric_columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    invalid_numeric_rows = len(
        df[df[numeric_columns].isna().any(axis=1)]
    )

    df = df.dropna(subset=numeric_columns)

    invalid_range_mask = (
        ~df["kcal_100g"].between(0, 1000)
        | ~df["fat_100g"].between(0, 100)
        | ~df["carbs_100g"].between(0, 100)
        | ~df["protein_100g"].between(0, 100)
    )

    rejected_rows = df[invalid_range_mask].copy()

    invalid_kcal_rows = len(
        df[~df["kcal_100g"].between(0, 1000)]
    )

    invalid_fat_rows = len(
        df[~df["fat_100g"].between(0, 100)]
    )

    invalid_carbs_rows = len(
        df[~df["carbs_100g"].between(0, 100)]
    )

    invalid_protein_rows = len(
        df[~df["protein_100g"].between(0, 100)]
    )

    df = df[df["kcal_100g"].between(0, 1000)]
    df = df[df["fat_100g"].between(0, 100)]
    df = df[df["carbs_100g"].between(0, 100)]
    df = df[df["protein_100g"].between(0, 100)]

    rejected_output_path = Path(
        "data/processed/rejected_food_rows.csv"
    )

    rejected_output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    rejected_rows.to_csv(
        rejected_output_path,
        index=False
    )

    logger.info(
        f"Rejected rows exported to: {rejected_output_path}"
    )

    logger.info(
        f"Rejected rows exported: {len(rejected_rows)}"
    )

    after = len(df)

    logger.info(f"Rows before validation: {before}")
    logger.info(f"Rows after validation: {after}")
    logger.info(f"Rows removed by validation: {before - after}")

    logger.info(f"Missing item_name rows: {missing_name_rows}")
    logger.info(f"Empty item_name rows: {empty_name_rows}")

    logger.info(f"Invalid numeric rows: {invalid_numeric_rows}")

    logger.info(f"Invalid kcal rows: {invalid_kcal_rows}")
    logger.info(f"Invalid fat rows: {invalid_fat_rows}")
    logger.info(f"Invalid carbs rows: {invalid_carbs_rows}")
    logger.info(f"Invalid protein rows: {invalid_protein_rows}")

    return df

@task
def write_to_duckdb(df: pd.DataFrame) -> None:
    logger = get_run_logger()

    DUCKDB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with duckdb.connect(str(DUCKDB_PATH)) as con:
        con.execute("DROP TABLE IF EXISTS food_items_final")
        con.register("food_df", df)
        con.execute("CREATE TABLE food_items_final AS SELECT * FROM food_df")

        count = con.execute("SELECT COUNT(*) FROM food_items_final").fetchone()[0]

    logger.info(f"Wrote {count} rows to DuckDB table food_items_final")


@task
def export_validated_csv(df: pd.DataFrame) -> Path:
    logger = get_run_logger()

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_CSV, index=False)

    logger.info(f"Exported validated CSV to {OUTPUT_CSV}")
    return OUTPUT_CSV


@flow(name="sayfit-food-reference-data-pipeline")
def build_food_reference_data():
    input_path = check_input_file()
    df = load_csv(input_path)
    clean_df = basic_cleaning(df)
    validated_df = validate_food_data(clean_df)
    write_to_duckdb(validated_df)
    output_path = export_validated_csv(validated_df)

    return output_path


if __name__ == "__main__":
    build_food_reference_data()

