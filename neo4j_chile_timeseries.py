from neo4j_retrieval import get_driver, NEO4J_DATABASE

SIGNAL_ID = "signal_chile_flu"


def fetch_signal_timeseries(tx, signal_id):
    query = """
    MATCH (o:Observation)-[:OF_SIGNAL]->(:Signal {id: $signal_id})
    MATCH (o)-[:FOR_WEEK]->(w:Week)
    RETURN
      o.id AS observation_id,
      w.iso_year AS iso_year,
      w.iso_week AS iso_week,
      w.week_start_date AS week_start_date,
      o.positivity AS positivity,
      o.inf_all AS inf_all,
      o.spec_processed_nb AS spec_processed_nb
    ORDER BY w.iso_year, w.iso_week
    """
    result = tx.run(query, signal_id=signal_id)
    return [record.data() for record in result]


def print_timeseries(rows, limit=15):
    print("Chile influenza real-data time series")
    print("-" * 40)
    print(f"Total rows: {len(rows)}")
    print()

    for row in rows[:limit]:
        print(
            f"{row['iso_year']}-W{int(row['iso_week']):02d} | "
            f"positivity={row['positivity']:.4f} | "
            f"inf_all={row['inf_all']} | "
            f"spec_processed_nb={row['spec_processed_nb']}"
        )


if __name__ == "__main__":
    driver = get_driver()
    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            rows = session.execute_read(fetch_signal_timeseries, SIGNAL_ID)
        print_timeseries(rows)
    finally:
        driver.close()