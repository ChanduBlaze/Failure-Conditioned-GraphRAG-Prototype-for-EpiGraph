import pandas as pd

INPUT_FILE = "DataExport_042326.xlsx"
SHEET_NAME = "DataExport"
OUTPUT_FILE = "chile_flu_weekly_clean.csv"

YEARS_TO_KEEP = {2024, 2025}


def main():
    df = pd.read_excel(INPUT_FILE, sheet_name=SHEET_NAME)
    df.columns = [col.strip() for col in df.columns]

    df = df[df["COUNTRY/AREA/TERRITORY"].astype(str).str.strip() == "Chile"].copy()
    df = df[df["ISO_YEAR"].isin(YEARS_TO_KEEP)].copy()

    numeric_cols = [
        "SPEC_PROCESSED_NB",
        "INF_ALL",
        "INF_NEGATIVE",
        "ILI_ACTIVITY",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    grouped = (
        df.groupby(
            ["COUNTRY/AREA/TERRITORY", "ISO_YEAR", "ISO_WEEK", "ISO_SDATE"],
            as_index=False,
        )
        .agg(
            {
                "SPEC_PROCESSED_NB": "sum",
                "INF_ALL": "sum",
                "INF_NEGATIVE": "sum",
                "ILI_ACTIVITY": "first",
                "ORIGIN_SOURCE": "count",
            }
        )
        .rename(
            columns={
                "COUNTRY/AREA/TERRITORY": "country",
                "ISO_YEAR": "iso_year",
                "ISO_WEEK": "iso_week",
                "ISO_SDATE": "iso_sdate",
                "SPEC_PROCESSED_NB": "spec_processed_nb",
                "INF_ALL": "inf_all",
                "INF_NEGATIVE": "inf_negative",
                "ILI_ACTIVITY": "ili_activity",
                "ORIGIN_SOURCE": "source_count",
            }
        )
    )

    grouped["positivity"] = grouped["inf_all"] / grouped["spec_processed_nb"]
    grouped["positivity"] = grouped["positivity"].fillna(0.0)

    grouped["iso_week"] = grouped["iso_week"].astype(int)
    grouped["iso_year"] = grouped["iso_year"].astype(int)
    grouped["source_count"] = grouped["source_count"].astype(int)
    grouped["iso_sdate"] = pd.to_datetime(grouped["iso_sdate"], errors="coerce")

    grouped = grouped.sort_values(["iso_year", "iso_week"]).reset_index(drop=True)

    print(grouped.head(15))
    print("\nRow count:", len(grouped))
    print("Years:", sorted(grouped["iso_year"].unique().tolist()))

    grouped.to_csv(OUTPUT_FILE, index=False)
    print(f"\nSaved cleaned file to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()