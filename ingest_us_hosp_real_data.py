import pandas as pd

from neo4j_retrieval import get_driver, NEO4J_DATABASE

INPUT_FILE = "us_hosp_weekly_clean.csv"
SIGNAL_ID = "signal_us_hosp"
REGION_ID = "region_us"
DISEASE_ID = "disease_influenza"


def normalize_row(row):
    season = str(row["season"]).strip()
    calendar_year = int(float(row["calendar_year"]))
    mmwr_week = int(float(row["mmwr_week"]))

    week_id = f"week_{season}_{calendar_year}_{mmwr_week:02d}".replace("-", "_")
    observation_id = f"obs_us_hosp_{season}_{calendar_year}_{mmwr_week:02d}".replace("-", "_")

    return {
        "week_id": week_id,
        "observation_id": observation_id,
        "season": season,
        "calendar_year": calendar_year,
        "mmwr_week": mmwr_week,
        "weekly_rate": float(row["weekly_rate"]),
        "cumulative_rate": float(row["cumulative_rate"]),
        "catchment": str(row["CATCHMENT"]).strip(),
        "network": str(row["NETWORK"]).strip(),
    }


def create_constraints(tx):
    tx.run(
        "CREATE CONSTRAINT week_id_unique IF NOT EXISTS "
        "FOR (w:Week) REQUIRE w.id IS UNIQUE"
    )
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
    MERGE (w:Week {id: $week_id})
    SET w.season = $season,
        w.calendar_year = $calendar_year,
        w.mmwr_week = $mmwr_week

    MERGE (o:Observation {id: $observation_id})
    SET o.season = $season,
        o.calendar_year = $calendar_year,
        o.mmwr_week = $mmwr_week,
        o.weekly_rate = $weekly_rate,
        o.cumulative_rate = $cumulative_rate,
        o.catchment = $catchment,
        o.network = $network,
        o.source = "CDC FluSurv-NET"

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
    print("Real-data ingestion complete.")
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