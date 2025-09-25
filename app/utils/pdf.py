# app/utils/pdf.py
from io import BytesIO
from typing import Dict, Any
import textwrap

# Try to create a real PDF using reportlab if available; otherwise return a readable byte fallback.
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    _HAS_REPORTLAB = True
except Exception:
    _HAS_REPORTLAB = False

def _safe_str(x: Any) -> str:
    if x is None:
        return ""
    if isinstance(x, (dict, list)):
        import json
        return json.dumps(x, ensure_ascii=False)
    return str(x)

def generate_prescription_pdf(pres: Dict[str, Any]) -> bytes:
    """
    Returns bytes for a PDF representing the prescription.
    If reportlab is available, uses it to render a simple one-page PDF.
    Otherwise returns a plain-text bytes fallback (still usable for testing).
    """
    if _HAS_REPORTLAB:
        buf = BytesIO()
        c = canvas.Canvas(buf, pagesize=letter)
        width, height = letter

        # Header
        c.setFont("Helvetica-Bold", 14)
        c.drawString(40, height - 50, f"Prescription #{_safe_str(pres.get('id'))}")

        # meta lines
        c.setFont("Helvetica", 10)
        c.drawString(40, height - 75, f"Patient ID: {_safe_str(pres.get('patient_id'))}")
        c.drawString(250, height - 75, f"Doctor ID: {_safe_str(pres.get('doctor_id'))}")
        c.drawString(40, height - 90, f"Created: {_safe_str(pres.get('created_at'))}")

        # Diagnosis & Notes
        y = height - 120
        c.setFont("Helvetica-Bold", 11)
        c.drawString(40, y, "Diagnosis:")
        c.setFont("Helvetica", 10)
        diag = _safe_str(pres.get("diagnosis", ""))
        diag_wrapped = textwrap.wrap(diag, 90)
        y -= 16
        for line in diag_wrapped:
            c.drawString(60, y, line)
            y -= 12

        # Medicines
        y -= 8
        c.setFont("Helvetica-Bold", 11)
        c.drawString(40, y, "Medicines:")
        y -= 16
        c.setFont("Helvetica", 10)
        meds = pres.get("raw_medicines") or []
        if isinstance(meds, str):
            meds = [meds]
        if not meds:
            c.drawString(60, y, "No medicines listed.")
            y -= 12
        else:
            for m in meds:
                line = _safe_str(m)
                line_wrapped = textwrap.wrap(line, 90)
                for sub in line_wrapped:
                    c.drawString(60, y, sub)
                    y -= 12
                y -= 2
                if y < 60:
                    c.showPage()
                    y = height - 60
        c.showPage()
        c.save()
        buf.seek(0)
        return buf.read()

    # Fallback: simple textual "PDF" bytes (useful for tests). Not a real PDF but works as bytes.
    lines = []
    lines.append(f"Prescription #{_safe_str(pres.get('id'))}")
    lines.append(f"Patient ID: {_safe_str(pres.get('patient_id'))}")
    lines.append(f"Doctor ID: {_safe_str(pres.get('doctor_id'))}")
    lines.append(f"Created: {_safe_str(pres.get('created_at'))}")
    lines.append("")
    lines.append("Diagnosis:")
    lines.append(_safe_str(pres.get("diagnosis", "")))
    lines.append("")
    lines.append("Medicines:")
    raw = pres.get("raw_medicines") or []
    if isinstance(raw, (list, tuple)):
        for item in raw:
            lines.append(_safe_str(item))
    else:
        lines.append(_safe_str(raw))

    text = "\n".join(lines)
    # Prefix so it's obvious in downloads that this is a fallback
    fallback = ("*** PDF fallback - install reportlab for real PDF generation ***\n\n" + text).encode("utf-8")
    return fallback
