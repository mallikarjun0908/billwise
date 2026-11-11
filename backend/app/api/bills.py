import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import Bill, Premises
from ..services.coach import build_coach
from ..services.ocr import ocr_image, parse_bill_text
from ..services.storage import save_upload
from ..services.tariff_engine import Tariff, compute_net_bill, verify_bill

router = APIRouter(prefix="/api")

ALLOWED = {"application/pdf", "image/jpeg", "image/png"}
TARIFF_FILE = Path(__file__).resolve().parents[3] / "tariffs" / "sample_domestic.json"
if not TARIFF_FILE.exists():  # docker layout: /app/tariffs
    TARIFF_FILE = Path("/app/tariffs/sample_domestic.json")


@router.post("/premises")
def create_premises(label: str, sanctioned_load_kw: float = 1.0, db: Session = Depends(get_db)):
    p = Premises(label=label, sanctioned_load_kw=sanctioned_load_kw)
    db.add(p)
    db.commit()
    return {"id": p.id, "label": p.label}


@router.post("/premises/{premises_id}/bills")
async def upload_bill(premises_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not db.get(Premises, premises_id):
        raise HTTPException(404, "Premises not found")
    if file.content_type not in ALLOWED:
        raise HTTPException(415, "Only PDF, JPG or PNG files are allowed")
    data = await file.read()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"File exceeds {settings.max_upload_mb} MB")

    stored = save_upload(data, file.content_type)

    bill = Bill(premises_id=premises_id, file_path=stored, status="uploaded")
    db.add(bill)
    db.commit()
    # TODO (Week 2): enqueue OCR + extraction job here
    return {"bill_id": bill.id, "status": bill.status}


def _parse_fppca(text: str | None):
    """'236.15@0.02,98.85@0.32' -> [(236.15, 0.02), (98.85, 0.32)]"""
    if not text or not text.strip():
        return None
    segs = []
    for part in re.split(r"[,\s;]+", text.strip()):
        if not part:
            continue
        try:
            u, r = part.split("@")
            segs.append((float(u), float(r)))
        except ValueError:
            raise HTTPException(422, "FPPCA must look like 236.15@0.02,98.85@0.32")
    return segs or None


@router.post("/bills/{bill_id}/verify")
def verify(bill_id: int, units_kwh: float, amount_billed: float, subsidy_units: float = 0.0,
           billing_days: int | None = None, fppca: str | None = None,
           md_penalty: float | None = None, recorded_md_kw: float | None = None,
           db: Session = Depends(get_db)):
    """Manual-entry path: verify a bill without OCR.

    amount_billed = the "Bill Amount (1-2)" line (before penalties and arrears).
    """
    bill = db.get(Bill, bill_id)
    if not bill:
        raise HTTPException(404, "Bill not found")
    tariff = Tariff.from_file(TARIFF_FILE)
    segs = _parse_fppca(fppca)
    net_bill = compute_net_bill(tariff, units_kwh, bill.premises.sanctioned_load_kw,
                                subsidy_units, billing_days=billing_days, fppca_segments=segs)
    v = verify_bill(tariff, units_kwh, bill.premises.sanctioned_load_kw, amount_billed,
                    subsidy_units, billing_days=billing_days, fppca_segments=segs)
    bill.units_kwh, bill.amount_billed = units_kwh, amount_billed
    bill.amount_recomputed, bill.variance = float(v.recomputed), float(v.variance)
    bill.status = "done"
    db.commit()
    notes = []
    if billing_days and billing_days > 45 and not segs:
        notes.append("This looks like a multi-month bill. Enter the FPPCA lines "
                     "(units@rate) in the advanced box for an accurate check.")
    coach = build_coach(tariff, units_kwh, bill.premises.sanctioned_load_kw, subsidy_units,
                        billing_days, segs, v.flagged, float(v.variance), md_penalty, recorded_md_kw)
    return {"recomputed": float(v.recomputed), "billed": float(v.billed),
            "variance": float(v.variance), "flagged": v.flagged, "message": v.message,
            "notes": notes, "coach": coach,
            "breakdown": {
                "gross": net_bill.gross.as_dict(),
                "subsidy": net_bill.subsidy.as_dict() if net_bill.subsidy else None,
                "net": float(net_bill.net),
            }}


@router.post("/scan")
def scan(file: UploadFile = File(...)):
    """Read a bill photo with OCR and suggest values for the form. Nothing is saved."""
    if file.content_type not in {"image/jpeg", "image/png"}:
        raise HTTPException(415, "Photo scanning supports JPG or PNG. For PDFs, type the values in.")
    data = file.file.read()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"File exceeds {settings.max_upload_mb} MB")
    try:
        text = ocr_image(data)
    except Exception as e:  # e.g. Tesseract not installed
        raise HTTPException(503, f"OCR is not available: {e}")
    return parse_bill_text(text)
