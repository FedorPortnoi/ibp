#!/bin/bash
# Load ALL leak CSVs from data/raw/ into the IBP leak database.
# Usage: ./scripts/load_all.sh
set -e
cd "$(dirname "$0")/.."

echo "=== IBP Leak Database Bulk Loader ==="
echo "Directory: data/raw/"

for csv in data/raw/*.csv; do
  fname=$(basename "$csv")
  fname_lower=$(echo "$fname" | tr '[:upper:]' '[:lower:]')

  if [[ "$fname_lower" =~ vk ]]; then
    echo "Loading VK2012: $csv"
    python scripts/load_leaks.py vk_2012 "$csv" --dedup
  elif [[ "$fname_lower" =~ (beeline|mts|megafon|tele2|telco) ]]; then
    carrier="unknown"
    [[ "$fname_lower" =~ beeline ]] && carrier="beeline"
    [[ "$fname_lower" =~ mts ]] && carrier="mts"
    [[ "$fname_lower" =~ megafon ]] && carrier="megafon"
    [[ "$fname_lower" =~ tele2 ]] && carrier="tele2"
    echo "Loading Telco ($carrier): $csv"
    python scripts/load_leaks.py telco "$csv" --carrier "$carrier" --dedup
  elif [[ "$fname_lower" =~ getcontact|gc_ ]]; then
    echo "Loading GetContact: $csv"
    python scripts/load_leaks.py getcontact "$csv" --dedup
  else
    echo "SKIP: $csv (unknown source type)"
  fi
done

for jsonl in data/raw/*.jsonl; do
  [ -f "$jsonl" ] || continue
  echo "Loading JSONL (getcontact): $jsonl"
  python scripts/load_leaks.py getcontact "$jsonl" --dedup
done

echo ""
echo "=== DONE ==="
python -c "
from app.services.phase2.sources.leak_sources import LeakDB
db = LeakDB.get_instance()
total = db.count()
print(f'Total records: {total:,}')
for tag in ('vk_2012', 'getcontact', 'telco'):
    c = db.count(tag)
    print(f'  {tag}: {c:,}')
"
