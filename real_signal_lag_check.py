from datetime import date

import pandas as pd

from neo4j_retrieval import get_driver, NEO4J_DATABASE

US_SIGNAL_ID = "signal_us_hosp"
CHILE_SIGNAL_ID = "signal_chile_flu"

MAX_LAG_WEEKS = 40
PLAUSIBLE_MAX_LAG_WEEKS = 16
MIN_OVERLAP_WEEKS = 8


def fetch_signal_rows(tx, signal_id):
    query = """
    MATCH (o:Observation)-[:OF_SIGNAL]->(:Signal {id: $signal_id})
    MATCH (o)-[:FOR_WEEK]->(w:Week)
    RETURN
      o.id AS observation_id,
      w.week_start_date AS week_start_date,
      w.calendar_year AS calendar_year,
      w.mmwr_week AS mmwr_week,
      w.iso_year AS iso_year,
      w.iso_week AS iso_week,
      o.weekly_rate AS weekly_rate,
      o.positivity AS positivity
    ORDER BY
      w.week_start_date,
      w.calendar_year,
      w.mmwr_week,
      w.iso_year,
      w.iso_week
    """
    result = tx.run(query, signal_id=signal_id)
    return [record.data() for record in result]


def coerce_week_start_date(row):
    raw = row.get("week_start_date")

    if raw is not None and str(raw).strip():
        return pd.to_datetime(raw)

    iso_year = row.get("iso_year")
    iso_week = row.get("iso_week")

    if pd.notna(iso_year) and pd.notna(iso_week):
        return pd.Timestamp(date.fromisocalendar(int(iso_year), int(iso_week), 1))

    calendar_year = row.get("calendar_year")
    mmwr_week = row.get("mmwr_week")

    if pd.notna(calendar_year) and pd.notna(mmwr_week):
        return pd.Timestamp(date.fromisocalendar(int(calendar_year), int(mmwr_week), 1))

    raise ValueError(f"Could not infer week_start_date for row: {row}")


def build_us_dataframe(rows):
    df = pd.DataFrame(rows)
    df["week_start_date"] = df.apply(coerce_week_start_date, axis=1)
    df["us_weekly_rate"] = pd.to_numeric(df["weekly_rate"], errors="coerce")
    df = df[["week_start_date", "us_weekly_rate"]].dropna().drop_duplicates()
    df = df.sort_values("week_start_date").reset_index(drop=True)
    return df


def build_chile_dataframe(rows):
    df = pd.DataFrame(rows)
    df["week_start_date"] = df.apply(coerce_week_start_date, axis=1)
    df["chile_positivity"] = pd.to_numeric(df["positivity"], errors="coerce")
    df = df[["week_start_date", "chile_positivity"]].dropna().drop_duplicates()
    df = df.sort_values("week_start_date").reset_index(drop=True)
    return df


def compute_lag_results(us_df, chile_df, max_lag_weeks=40):
    results = []

    for lag in range(0, max_lag_weeks + 1):
        shifted_chile = chile_df.copy()
        shifted_chile["aligned_week"] = shifted_chile["week_start_date"] + pd.to_timedelta(
            lag, unit="W"
        )

        merged = us_df.merge(
            shifted_chile[["aligned_week", "chile_positivity"]],
            left_on="week_start_date",
            right_on="aligned_week",
            how="inner",
        )

        overlap_weeks = len(merged)

        if overlap_weeks >= 2:
            correlation = merged["us_weekly_rate"].corr(merged["chile_positivity"])
        else:
            correlation = None

        results.append(
            {
                "lag_weeks": lag,
                "overlap_weeks": overlap_weeks,
                "correlation": correlation,
            }
        )

    return pd.DataFrame(results)


def filter_valid_results(results_df):
    return results_df[
        results_df["correlation"].notna()
        & (results_df["overlap_weeks"] >= MIN_OVERLAP_WEEKS)
    ].copy()


def get_best_result(results_df):
    if results_df.empty:
        return None

    ranked = results_df.sort_values(
        ["correlation", "overlap_weeks"],
        ascending=[False, False],
    ).reset_index(drop=True)

    return ranked.iloc[0]


def print_result_row(label, row):
    print(
        f"{label}: {int(row['lag_weeks'])} weeks | "
        f"correlation={row['correlation']:.4f} | "
        f"overlap_weeks={int(row['overlap_weeks'])}"
    )


def print_lag_results(results_df):
    print("Real signal lag check")
    print("-" * 40)
    print(
        "Interpretation: lag_weeks = k means Chile positivity is shifted forward by k weeks,\n"
        "so a positive lag suggests Chile may lead US hospitalizations by k weeks.\n"
    )

    valid = filter_valid_results(results_df)

    if valid.empty:
        print("No valid lag results found.")
        return

    best_overall = get_best_result(valid)
    plausible = valid[valid["lag_weeks"] <= PLAUSIBLE_MAX_LAG_WEEKS].copy()
    best_plausible = get_best_result(plausible)

    print_result_row("Best overall lag", best_overall)

    if best_plausible is not None:
        print_result_row("Best plausible lag", best_plausible)
    else:
        print(f"No plausible lag found in 0..{PLAUSIBLE_MAX_LAG_WEEKS} weeks.")

    print("\nTop plausible lag candidates:")
    if best_plausible is not None:
        plausible_ranked = plausible.sort_values(
            ["correlation", "overlap_weeks"],
            ascending=[False, False],
        ).reset_index(drop=True)

        top_n = min(10, len(plausible_ranked))
        for _, row in plausible_ranked.head(top_n).iterrows():
            print(
                f"- lag={int(row['lag_weeks']):02d} | "
                f"correlation={row['correlation']:.4f} | "
                f"overlap_weeks={int(row['overlap_weeks'])}"
            )
    else:
        print("- none")

    print("\nInterpretation note:")
    print(
        f"- Lags above about {PLAUSIBLE_MAX_LAG_WEEKS} weeks are more likely to reflect "
        "shared seasonality or cross-season alignment than a short importation-style lead."
    )
    print(
        "- For the demo, prefer the best plausible lag rather than the best overall lag."
    )
    print(
        "- This is still a simple exploratory Pearson-correlation check, not a causal test."
    )


if __name__ == "__main__":
    driver = get_driver()

    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            us_rows = session.execute_read(fetch_signal_rows, US_SIGNAL_ID)
            chile_rows = session.execute_read(fetch_signal_rows, CHILE_SIGNAL_ID)

        us_df = build_us_dataframe(us_rows)
        chile_df = build_chile_dataframe(chile_rows)

        results_df = compute_lag_results(
            us_df,
            chile_df,
            max_lag_weeks=MAX_LAG_WEEKS,
        )

        print_lag_results(results_df)

    finally:
        driver.close()