"""Step 1 for the Milwaukee crime project: download MPD's two NIBRS CSVs and profile them.

Run from the project folder (uv installs the packages into a throwaway environment):
    uvx --with duckdb --with requests python profile_wibr.py

If the download is blocked, save the two files by hand from the portal into data/ as
wibr.csv and wibrarchive.csv, then run the same command again; it skips files that exist.
"""
import os

import duckdb
import requests

FILES = {
    "wibr.csv": "https://data.milwaukee.gov/dataset/e5feaad3-ee73-418c-b65d-ef810c199390/resource/"
                "87843297-a6fa-46d4-ba5d-cb342fb2d3bb/download/wibr.csv",
    "wibrarchive.csv": "https://data.milwaukee.gov/dataset/5a537f5c-10d7-40a2-9b93-3527a4c89fbd/resource/"
                       "395db729-a30a-4e53-ab66-faeb5e1899c8/download/wibrarchive.csv",
}
os.makedirs("data", exist_ok=True)

for name, url in FILES.items():
    path = os.path.join("data", name)
    if os.path.exists(path):
        print(f"{name}: already downloaded ({os.path.getsize(path) / 1e6:.1f} MB)")
        continue
    print(f"Downloading {name} ...")
    with requests.get(url, stream=True, timeout=(30, 600),
                      headers={"User-Agent": "Mozilla/5.0 (portfolio project; github.com/zaidatom585)"}) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    print(f"  saved {os.path.getsize(path) / 1e6:.1f} MB")

con = duckdb.connect()
for name in FILES:
    t = name.replace(".csv", "")
    con.execute(f"CREATE VIEW {t} AS SELECT * FROM read_csv_auto('data/{name}', all_varchar=true, sample_size=-1)")
    cols = [r[0] for r in con.execute(f"DESCRIBE {t}").fetchall()]
    n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"\n==================== {name}: {n:,} rows, {len(cols)} columns")
    print("Columns:", ", ".join(cols))
    print(con.execute(f"SELECT * FROM {t} LIMIT 3").df().T.to_string())

    if "IncidentNum" in cols:
        d = con.execute(f"SELECT COUNT(DISTINCT IncidentNum) FROM {t}").fetchone()[0]
        print(f"\nDistinct IncidentNum: {d:,} ({n - d:,} repeated rows)")
    date_col = next((c for c in cols if "date" in c.lower()), None)
    if date_col:
        print(f"\nRows per year ({date_col}):")
        print(con.execute(f"""
            SELECT year(try_strptime({date_col}, ['%Y-%m-%d %H:%M:%S', '%m/%d/%Y %H:%M:%S', '%m/%d/%Y %I:%M:%S %p',
                                                  '%Y-%m-%dT%H:%M:%S'])) AS year, COUNT(*) AS rows
            FROM {t} GROUP BY ALL ORDER BY year""").df().to_string(index=False))
    print("\nShare of blank values per column:")
    blanks = con.execute("SELECT " + ", ".join(
        f"ROUND(100 * AVG(CASE WHEN \"{c}\" IS NULL OR trim(\"{c}\") = '' THEN 1 ELSE 0 END), 1) AS \"{c}\""
        for c in cols) + f" FROM {t}").df().T
    print(blanks.to_string(header=False))

if all(os.path.exists(os.path.join("data", f)) for f in FILES):
    try:
        overlap = con.execute("SELECT COUNT(*) FROM (SELECT DISTINCT IncidentNum FROM wibr "
                              "INTERSECT SELECT DISTINCT IncidentNum FROM wibrarchive)").fetchone()[0]
        print(f"\nIncidentNum present in BOTH files: {overlap:,}")
    except duckdb.Error as e:
        print("\nOverlap check skipped:", e)
