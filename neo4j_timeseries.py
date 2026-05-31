from neo4j_retrieval import get_driver, NEO4J_DATABASE

SIGNAL_ID = "signal_us_hosp"


def fetch_signal_timeseries(tx, signal_id):
    query = """
    MATCH (o:Observation)-[:OF_SIGNAL]->(:Signal {id: $signal_id})
    MATCH (o)-[:FOR_WEEK]->(w:Week)
    RETURN
      o.id AS observation_id,
      w.season AS season,
      w.calendar_year AS calendar_year,
      w.mmwr_week AS mmwr_week,
      o.weekly_rate AS weekly_rate,
      o.cumulative_rate AS cumulative_rate
    ORDER BY w.calendar_year, w.mmwr_week
    """
    result = tx.run(query, signal_id=signal_id)
    return [record.data() for record in result]


def print_timeseries(rows, limit=15):
    print("Target signal real-data time series")
    print("-" * 40)
    print(f"Total rows: {len(rows)}")
    print()

    for row in rows[:limit]:
        print(
            f"{row['season']} | "
            f"{row['calendar_year']}-W{int(row['mmwr_week']):02d} | "
            f"weekly_rate={row['weekly_rate']} | "
            f"cumulative_rate={row['cumulative_rate']}"
        )


if __name__ == "__main__":
    driver = get_driver()
    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            rows = session.execute_read(fetch_signal_timeseries, SIGNAL_ID)
        print_timeseries(rows)
    finally:
        driver.close()