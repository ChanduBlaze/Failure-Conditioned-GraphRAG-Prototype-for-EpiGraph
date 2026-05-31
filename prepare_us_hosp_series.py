import pandas as pd

INPUT_FILE = "FluSurveillance_Custom_Download_Data.csv"
OUTPUT_FILE = "us_hosp_weekly_clean.csv"

df = pd.read_csv(INPUT_FILE, skiprows=2)

# Clean column names
df.columns = [col.strip() for col in df.columns]

# Keep only the simplest overall weekly series
filtered = df[
    (df["CATCHMENT"] == "Entire Network") &
    (df["AGE CATEGORY"] == "Overall") &
    (df["SEX CATEGORY"] == "Overall") &
    (df["RACE CATEGORY"] == "Overall") &
    (df["VIRUS TYPE CATEGORY"] == "Overall")
].copy()

# Keep only the columns we need first
filtered = filtered[
    ["CATCHMENT", "NETWORK", "YEAR", "YEAR.1", "WEEK", "WEEKLY RATE", "CUMULATIVE RATE"]
].copy()

filtered = filtered.rename(columns={
    "YEAR": "season",
    "YEAR.1": "calendar_year",
    "WEEK": "mmwr_week",
    "WEEKLY RATE": "weekly_rate",
    "CUMULATIVE RATE": "cumulative_rate",
})

filtered = filtered.sort_values(["season", "calendar_year", "mmwr_week"]).reset_index(drop=True)

print(filtered.head(15))
print("\nRow count:", len(filtered))

filtered.to_csv(OUTPUT_FILE, index=False)
print(f"\nSaved cleaned file to: {OUTPUT_FILE}")