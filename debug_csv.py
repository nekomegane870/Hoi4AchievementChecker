import csv
from pathlib import Path

csv_path = Path("achievement_list.csv")
print(f"File path: {csv_path.absolute()}")

encodings = ["utf-8-sig", "utf-8", "cp932", "shift_jis"]

for enc in encodings:
    print(f"\n--- Testing encoding: {enc} ---")
    try:
        with open(csv_path, encoding=enc, errors="replace") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            print(f"Header: {fieldnames}")
            
            # Check first 2 non-empty rows
            count = 0
            for row in reader:
                if any(row.values()) and row.get("Achievements Name"):
                    print(f"Row {count}: {row}")
                    count += 1
                if count >= 2:
                    break
    except Exception as e:
        print(f"Error with {enc}: {e}")
