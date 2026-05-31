import pandas as pd

from neo4j_retrieval import get_driver, NEO4J_DATABASE

INPUT_FILE = "chile_flu_weekly_clean.csv"
SIGNAL_ID = "signal_chile_flu"
REGION_ID = "region_chile"
DISEASE_ID = "disease_influenza"


def normalize_row(row):
    iso_year = int(row["iso_year"])
    iso_week = int(row["iso_week"])
    week_key = f"{iso_year}-W{iso_week:02d}"
    week_id = f"week_{iso_year}_{iso_week:02d}"
    observation_id = f"obs_chile_flu_{iso_year}_{iso_week:02d}"

    iso_sdate = pd.to_datetime(row["iso_sdate"], errors="coerce")
    iso_sdate = None if pd.isna(iso_sdate) else iso_sdate.date().isoformat()

    return {
        "week_id": week_id,
        "week_key": week_key,
        "observation_id": observation_id,
        "iso_year": iso_year,
        "iso_week": iso_week,
        "iso_sdate": iso_sdate,
        "country": str(row["country"]).strip(),
        "spec_processed_nb": int(row["spec_processed_nb"]),
        "inf_all": int(row["inf_all"]),
        "inf_negative": float(row["inf_negative"]) if pd.notna(row["inf_negative"]) else None,
        "ili_activity": float(row["ili_activity"]) if pd.notna(row["ili_activity"]) else None,
        "source_count": int(row["source_count"]),
        "positivity": float(row["positivity"]),
    }


def create_constraints(tx):
    tx.run(
        "CREATE CONSTRAINT observation_id_unique IF NOT EXISTS "
        "FOR (o:Observation) REQUIRE o.id IS UNIQUE"
    )


def verify_anchor_nodes(tx):
    query = """
    RETURN
      EXISTS { MATCH (:Signal {id: $signal_id}) } AS signal_exists,
      EXISTS { MATCH (:Region {id: $region_id}) } AS region_exists,
      EXISTS { MATCH (:Disease {id: $disease_id}) } AS disease_exists
    """
    record = tx.run(
        query,
        signal_id=SIGNAL_ID,
        region_id=REGION_ID,
        disease_id=DISEASE_ID,
    ).single()

    if not record["signal_exists"]:
        raise ValueError(f"Missing Signal node: {SIGNAL_ID}")
    if not record["region_exists"]:
        raise ValueError(f"Missing Region node: {REGION_ID}")
    if not record["disease_exists"]:
        raise ValueError(f"Missing Disease node: {DISEASE_ID}")


def ingest_row(tx, item):
    query = """
    MERGE (w:Week {calendar_year: $iso_year, mmwr_week: $iso_week})
    ON CREATE SET
        w.id = $week_id
    SET
        w.week_key = $week_key,
        w.iso_year = $iso_year,
        w.iso_week = $iso_week,
        w.week_start_date = $iso_sdate

    MERGE (o:Observation {id: $observation_id})
    SET
        o.country = $country,
        o.iso_year = $iso_year,
        o.iso_week = $iso_week,
        o.week_key = $week_key,
        o.week_start_date = $iso_sdate,
        o.spec_processed_nb = $spec_processed_nb,
        o.inf_all = $inf_all,
        o.inf_negative = $inf_negative,
        o.ili_activity = $ili_activity,
        o.source_count = $source_count,
        o.positivity = $positivity,
        o.source = "WHO FluNet"

    WITH o, w
    MATCH (s:Signal {id: $signal_id})
    MATCH (r:Region {id: $region_id})
    MATCH (d:Disease {id: $disease_id})

    MERGE (o)-[:OF_SIGNAL]->(s)
    MERGE (o)-[:IN_REGION]->(r)
    MERGE (o)-[:ABOUT_DISEASE]->(d)
    MERGE (o)-[:FOR_WEEK]->(w)
    """
    tx.run(
        query,
        signal_id=SIGNAL_ID,
        region_id=REGION_ID,
        disease_id=DISEASE_ID,
        **item,
    )


def print_ingest_summary(tx):
    query = """
    MATCH (o:Observation)-[:OF_SIGNAL]->(:Signal {id: $signal_id})
    RETURN count(o) AS observation_count
    """
    record = tx.run(query, signal_id=SIGNAL_ID).single()
    print("Chile real-data ingestion complete.")
    print("-" * 40)
    print(f"Observation nodes linked to {SIGNAL_ID}: {record['observation_count']}")


def main():
    df = pd.read_csv(INPUT_FILE)

    driver = get_driver()
    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            session.execute_write(create_constraints)
            session.execute_read(verify_anchor_nodes)

            for _, row in df.iterrows():
                item = normalize_row(row)
                session.execute_write(ingest_row, item)

            session.execute_read(print_ingest_summary)
    finally:
        driver.close()


if __name__ == "__main__":
    main()