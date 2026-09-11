"""Render an unclassified observed-data report without a running database."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.services.firms import FIRMSClient
from app.services.pdf_report import generate_incident_pdf

if __name__ == "__main__":
    raw = ROOT / "data/raw/observed/firms_south_asia_7d.csv"
    observations = FIRMSClient().parse_firms_csv(raw.read_text(encoding="utf-8"), "NASA_FIRMS_PUBLIC_SNAPSHOT")
    record = min(observations, key=lambda h: (h["latitude"] - 22.35) ** 2 + (h["longitude"] - 69.87) ** 2)
    record["brightness"] = record.get("bright_ti4")
    for field in ("confidence", "scan", "track"):
        record[field] = record["raw_data"].get(field)
    target = ROOT / "output/pdf/observed-incident-review.pdf"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(generate_incident_pdf(record).getvalue())
    print(target)
