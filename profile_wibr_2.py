"""Follow-up profile: keys, overlap between the two files, offense codes and edit timestamps.

    uvx --with duckdb --with pandas python profile_wibr_2.py
"""
import duckdb

con = duckdb.connect()
for t in ["wibr", "wibrarchive"]:
    con.execute(f"CREATE VIEW {t} AS SELECT * FROM read_csv_auto('data/{t}.csv', all_varchar=true, sample_size=-1)")


def show(title, sql):
    print(f"\n--- {title}")
    print(con.execute(sql).df().to_string(index=False))


for t in ["wibr", "wibrarchive"]:
    show(f"{t}: rows vs distinct Case_Number", f"""
        SELECT COUNT(*) AS rows, COUNT(DISTINCT Case_Number) AS cases,
               COUNT(*) - COUNT(DISTINCT Case_Number) AS repeated_rows
        FROM {t}""")
    show(f"{t}: example of a repeated Case_Number (if any)", f"""
        SELECT * FROM {t} WHERE Case_Number = (
            SELECT Case_Number FROM {t} GROUP BY 1 HAVING COUNT(*) > 1 LIMIT 1)""")
    show(f"{t}: edit timestamps", f"""
        SELECT MIN(Incident_Last_Edited) AS first_incident_edit, MAX(Incident_Last_Edited) AS last_incident_edit,
               MIN(Offense_Last_Edited) AS first_offense_edit, MAX(Offense_Last_Edited) AS last_offense_edit,
               MAX(Incident_Date) AS latest_incident
        FROM {t}""")

show("Case_Number present in BOTH files", """
    SELECT COUNT(*) AS cases_in_both FROM (
        SELECT DISTINCT Case_Number FROM wibr INTERSECT SELECT DISTINCT Case_Number FROM wibrarchive)""")

show("Offenses per incident (both files)", """
    SELECT len(string_split(Offense_All, ';')) AS offenses, COUNT(*) AS incidents
    FROM (SELECT Offense_All FROM wibr UNION ALL SELECT Offense_All FROM wibrarchive)
    GROUP BY 1 ORDER BY 1""")

show("Top 40 offense codes (both files)", """
    SELECT trim(code) AS code, COUNT(*) AS n
    FROM (SELECT unnest(string_split(Offense_All, ';')) AS code FROM wibr
          UNION ALL SELECT unnest(string_split(Offense_All, ';')) FROM wibrarchive)
    GROUP BY 1 ORDER BY 2 DESC LIMIT 40""")

show("Police_District values (both files)", """
    SELECT Police_District, COUNT(*) AS n
    FROM (SELECT Police_District FROM wibr UNION ALL SELECT Police_District FROM wibrarchive)
    GROUP BY 1 ORDER BY 2 DESC LIMIT 15""")

show("Weapon_Used_All top values", """
    SELECT Weapon_Used_All, COUNT(*) AS n
    FROM (SELECT Weapon_Used_All FROM wibr UNION ALL SELECT Weapon_Used_All FROM wibrarchive)
    GROUP BY 1 ORDER BY 2 DESC LIMIT 12""")

show("Coordinates outside the Milwaukee area (rough box)", """
    SELECT COUNT(*) AS outside FROM (SELECT * FROM wibr UNION ALL SELECT * FROM wibrarchive)
    WHERE TRY_CAST(Address_Latitude AS DOUBLE) NOT BETWEEN 42.8 AND 43.25
       OR TRY_CAST(Address_Longitude AS DOUBLE) NOT BETWEEN -88.1 AND -87.8""")

show("Future-dated incidents", """
    SELECT Case_Number, Incident_Date, Incident_Last_Edited FROM (SELECT * FROM wibr UNION ALL SELECT * FROM wibrarchive)
    WHERE TRY_CAST(Incident_Date AS TIMESTAMP) > now()""")
