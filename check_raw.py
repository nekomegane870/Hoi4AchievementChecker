with open("achievement_list.csv", "rb") as f:
    raw = f.read(500)
    print(f"Raw bytes (first 500): {raw!r}")

import chardet
with open("achievement_list.csv", "rb") as f:
    data = f.read()
    result = chardet.detect(data)
    print(f"Chardet detection: {result}")
