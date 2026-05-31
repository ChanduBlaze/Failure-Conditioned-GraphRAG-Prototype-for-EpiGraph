from neo4j_retrieval import get_driver, NEO4J_DATABASE

SIGNAL_ID = "signal_us_hosp"


def fetch_signal_summary(tx, signal_id):
    query = """
    MATCH (o:Observation)-[:OF_SIGNAL]->(:Signal {id: $signal_id})
    MATCH (o)-[:FOR_WEEK]->(w:Week)
    WITH o, w
    ORDER BY w.calendar_year, w.mmwr_week

    WITH
      collect({
        observation_id: o.id,
        season: w.season,
        calendar_year: w.calendar_year,
        mmwr_week: w.mmwr_week,
        weekly_rate: o.weekly_rate,
        cumulative_rate: o.cumulative_rate
      }) AS rows

    RETURN
      size(rows) AS total_weeks,
      reduce(best = null, row IN rows |
        CASE
          WHEN best IS NULL OR row.weekly_rate > best.weekly_rate THEN row
          ELSE best
        END
      ) AS peak_row,
      rows[-1] AS latest_row
    """
    record = tx.run(query, signal_id=signal_id).single()
    return record.data()


def print_signal_summary(summary):
    peak = summary["peak_row"]
    latest = summary["latest_row"]

    print("Target signal summary")
    print("-" * 40)
    print(f"Total observed weeks: {summary['total_weeks']}")
    print(
        f"Peak weekly rate: {peak['weekly_rate']} "
        f"at {peak['season']} | {peak['calendar_year']}-W{int(peak['mmwr_week']):02d}"
    )
    print(
        f"Latest cumulative rate: {latest['cumulative_rate']} "
        f"at {latest['season']} | {latest['calendar_year']}-W{int(latest['mmwr_week']):02d}"
    )


if __name__ == "__main__":
    driver = get_driver()
    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            summary = session.execute_read(fetch_signal_summary, SIGNAL_ID)
        print_signal_summary(summary)
    finally:
        driver.close()