from app.services.ocr import parse_bill_text

# Trimmed real OCR output from a BESCOM bill photo (noisy Kannada lines included)
SAMPLE = """
a WeoeoSano Load 3KW-FOHP
Pe hy GUS Reg Date 25/06/2023
3a os Bill Period 12/08/2026 - 12/09/2026
23%¢8/Consumption(Units) 94
Br abades*Eligible for subsidy 67.0
3.0KW 150.0 450.00
Der dod pil! Amount (1-2) 173.94
jays gee8/ Cur.Demand Payable ® 173.94
33 Aog ? 85.00
"""


def test_parse_real_ocr_text():
    r = parse_bill_text(SAMPLE)
    assert r["units_kwh"] == 94
    assert r["sanctioned_load_kw"] == 3
    assert r["amount_billed"] == 173.94
    assert r["subsidy_units"] == 67
    assert r["billing_start"] == "12/08/2026"
    assert r["missing"] == []


def test_missing_fields_reported():
    r = parse_bill_text("nothing useful here")
    assert set(r["missing"]) == {"units_kwh", "sanctioned_load_kw", "amount_billed"}
    assert r["subsidy_units"] == 0.0


def test_subsidy_survives_ocr_misread_of_for():
    r = parse_bill_text("Consumption(Units) 94\nSar ahadés*Eligible tor subsidy 67.0\n")
    assert r["subsidy_units"] == 67


def test_subsidy_from_entitlement_line():
    r = parse_bill_text("Consumption(Units) 94\n93 Entitiemen| Units 67.0\n")
    assert r["subsidy_units"] == 67


def test_subsidy_from_units_chargeable():
    r = parse_bill_text("Consumption(Units) 94\nMII ahwodés*Unils chargeable 27.0\n")
    assert r["subsidy_units"] == 67


BILL2 = """
Bill Pariod 12/06/2026 «12/08/2026
Pres. Aily, 7620
Prov. Rdg. 7285
Constant 1
Consumption(Units) 335
Entitlement Units 134.0
Wer slog 6i/ Amaunt(t-2) 424,00
i. ele. cloclEx.Load. Wp Panalty 337.50
"""


def test_multi_month_bill_fields():
    r = parse_bill_text(BILL2)
    assert r["billing_days"] == 61
    assert r["amount_billed"] == 424.00
    assert r["md_penalty"] == 337.50
    # no "Eligible" or "chargeable" line: entitlement is scaled by 61/30
    assert r["subsidy_units"] == 272.47


def test_units_corrected_from_meter_readings():
    r = parse_bill_text(BILL2.replace("Consumption(Units) 335", "Consumption(Units) 345"))
    assert r["units_kwh"] == 335
    assert r["warnings"]


def test_amount_from_subtotals_when_line_unreadable():
    r = parse_bill_text("Sub-Total-1 2881.47\nSub-Total-2 2457.47\n")
    assert r["amount_billed"] == 424.00


def test_recorded_md_parsed():
    r = parse_bill_text("Recorded M0 2.75, 2.75 KW\nConsumption(Units) 10\n")
    assert r["recorded_md_kw"] == 2.75


def test_subsidy_missed_decimal_corrected():
    # If dot matrix print drops decimal point in 144.4 -> 1444
    r = parse_bill_text("Consumption(Units) 150\nEligible for subsidy 1444\n")
    assert r["subsidy_units"] == 144.4


def test_sanctioned_load_decimal_and_various_consumption_labels():
    text = (
        "Sanctioned Load 4.1 KW\n"
        "Pres. Rdg 14500\n"
        "Prev. Rdg 14380\n"
        "Units Consumed : 120\n"
        "Cur.Demand Payable : 424.00\n"
        "Recorded MD 2.75 KW\n"
        "Ex.Load Penalty 337.50\n"
        "FPPCA: 120@0.15, 50@0.05\n"
        "Tariff: LT-2(a) Domestic\n"
        "RR No: W2LT12345\n"
        "Account ID: 1234567890\n"
    )
    r = parse_bill_text(text)
    assert r["sanctioned_load_kw"] == 4.1
    assert r["units_kwh"] == 120
    assert r["amount_billed"] == 424.00
    assert r["recorded_md_kw"] == 2.75
    assert r["md_penalty"] == 337.50
    assert r["fppca"] == "120@0.15,50@0.05"
    assert "LT-2(a)" in r["tariff_category"]
    assert r["rr_no"] == "W2LT12345"
    assert r["account_id"] == "1234567890"
    assert r["confidence"] >= 0.9
    assert r["missing"] == []
    assert 120 in r["candidates"]


def test_hp_to_kw_conversion():
    text = "Load 5 HP\nUnits Consumed 100\nCur.Demand Payable 500.00\n"
    r = parse_bill_text(text)
    assert r["sanctioned_load_kw"] == 3.73


def test_ocr_image_end_to_end():
    import io
    from PIL import Image, ImageDraw
    from app.services.ocr import ocr_image

    img = Image.new("RGB", (600, 400), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((20, 20), "BESCOM SPOT BILLING", fill=(0, 0, 0))
    draw.text((20, 60), "Sanctioned Load 4.1 KW", fill=(0, 0, 0))
    draw.text((20, 100), "Consumption(Units) 120", fill=(0, 0, 0))
    draw.text((20, 140), "Cur.Demand Payable 424.00", fill=(0, 0, 0))
    draw.text((20, 180), "Eligible for subsidy 144.4", fill=(0, 0, 0))

    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    text = ocr_image(buf.getvalue())
    r = parse_bill_text(text)
    assert r["sanctioned_load_kw"] == 4.1
    assert r["units_kwh"] == 120
    assert r["amount_billed"] == 424.0
    assert r["subsidy_units"] == 144.4
    assert r["missing"] == []



