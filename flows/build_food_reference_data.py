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
    write_to_duckdb(clean_df)
    output_path = export_validated_csv(clean_df)

    return output_path


if __name__ == "__main__":
    build_food_reference_data()