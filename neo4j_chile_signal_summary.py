from neo4j_retrieval import get_driver, NEO4J_DATABASE

SIGNAL_ID = "signal_chile_flu"


def fetch_signal_summary(tx, signal_id):
    query = """
    MATCH (o:Observation)-[:OF_SIGNAL]->(:Signal {id: $signal_id})
    MATCH (o)-[:FOR_WEEK]->(w:Week)
    WITH o, w
    ORDER BY w.iso_year, w.iso_week

    WITH
      collect({
        observation_id: o.id,
        iso_year: w.iso_year,
        iso_week: w.iso_week,
        week_start_date: w.week_start_date,
        positivity: o.positivity,
        inf_all: o.inf_all,
        spec_processed_nb: o.spec_processed_nb
      }) AS rows

    RETURN
      size(rows) AS total_weeks,
      reduce(best = null, row IN rows |
        CASE
          WHEN best IS NULL OR row.positivity > best.positivity THEN row
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

    print("Chile signal summary")
    print("-" * 40)
    print(f"Total observed weeks: {summary['total_weeks']}")
    print(
        f"Peak positivity: {peak['positivity']:.4f} "
        f"at {peak['iso_year']}-W{int(peak['iso_week']):02d}"
    )
    print(
        f"Peak positive specimens: {peak['inf_all']} "
        f"out of {peak['spec_processed_nb']}"
    )
    print(
        f"Latest positivity: {latest['positivity']:.4f} "
        f"at {latest['iso_year']}-W{int(latest['iso_week']):02d}"
    )


if __name__ == "__main__":
    driver = get_driver()
    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            summary = session.execute_read(fetch_signal_summary, SIGNAL_ID)
        print_signal_summary(summary)
    finally:
        driver.close()