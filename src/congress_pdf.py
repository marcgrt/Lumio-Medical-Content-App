"""Generate a printable A3 congress calendar poster as PDF.

Uses fpdf2 (pure Python, no native deps) to render a landscape A3 poster.
Congresses displayed as colored rows in a clean table, grouped by month or specialty.
"""

import logging
from datetime import date
from pathlib import Path
from typing import List

from fpdf import FPDF

logger = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

_SPEC_COLORS: dict[str, tuple] = {
    "Kardiologie": (239, 68, 68), "Onkologie": (168, 85, 247), "Neurologie": (59, 130, 246),
    "Diabetologie/Endokrinologie": (245, 158, 11), "Pneumologie": (6, 182, 212),
    "Gastroenterologie": (34, 197, 94), "Rheumatologie": (236, 72, 153),
    "Allgemeinmedizin": (132, 204, 22), "Radiologie": (99, 102, 241),
    "Urologie": (20, 184, 166), "Gynäkologie": (244, 114, 182),
    "Dermatologie": (251, 146, 60), "Pädiatrie": (56, 189, 248),
    "Chirurgie": (100, 116, 139), "Infektiologie": (250, 204, 21),
    "Psychiatrie": (139, 92, 246), "Health Economics": (148, 163, 184),
    "Orthopädie": (120, 113, 108), "Anästhesiologie": (232, 121, 249),
    "Intensivmedizin": (244, 63, 94), "Nephrologie": (14, 165, 233),
    "HNO": (217, 70, 239), "Augenheilkunde": (45, 212, 191),
    "Geriatrie": (163, 163, 163), "Ernährungsmedizin": (101, 163, 13),
    "Palliativmedizin": (192, 132, 252), "Allergologie": (251, 191, 36),
    "Nuklearmedizin": (129, 140, 248), "Notfallmedizin": (251, 113, 133),
}

_MONTH_NAMES = [
    "", "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]


def _safe(text: str) -> str:
    """Make text safe for fpdf (latin-1 encoding)."""
    return text.encode("latin-1", errors="replace").decode("latin-1")


def generate_congress_pdf(congresses: list[dict], year: int = 2026, group_by: str = "month") -> bytes:
    """Generate an A3 landscape PDF poster.

    Args:
        congresses: List of congress dicts.
        year: Calendar year.
        group_by: "month" or "specialty".

    Returns:
        PDF bytes.
    """
    # Filter to target year
    year_congresses = [
        c for c in congresses
        if c.get("date_start", "").startswith(str(year))
    ]
    year_congresses.sort(key=lambda c: c.get("date_start", ""))

    # Group
    if group_by == "specialty":
        specs = sorted(set(c.get("specialty", "Sonstige") for c in year_congresses))
        grouped = [(spec, [c for c in year_congresses if c.get("specialty", "Sonstige") == spec]) for spec in specs]
    else:
        grouped = []
        for m in range(1, 13):
            mc = [c for c in year_congresses if c.get("date_start", "")[5:7] == f"{m:02d}"]
            if mc:
                grouped.append((_MONTH_NAMES[m], mc))

    # Create PDF — A3 Landscape
    pdf = FPDF(orientation="L", unit="mm", format="A3")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Try to use a nicer font, fall back to Helvetica
    pdf.set_font("Helvetica", size=10)

    # Header
    logo_path = _STATIC_DIR / "logo.png"
    if logo_path.exists():
        pdf.image(str(logo_path), x=16, y=12, w=18)

    pdf.set_xy(38, 12)
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 10, _safe(f"Kongresskalender {year}"), ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(107, 114, 128)
    pdf.set_x(38)
    group_label = "Fachgebiet" if group_by == "specialty" else "Monat"
    pdf.cell(0, 5, _safe(f"{len(year_congresses)} Kongresse | Gruppiert nach {group_label}"), ln=True)

    # Green accent line
    pdf.set_draw_color(132, 204, 22)
    pdf.set_line_width(0.8)
    pdf.line(16, 28, 400, 28)

    pdf.set_y(32)

    # Table header
    col_widths = [30, 120, 55, 50, 40, 80]  # Color+Short, Name, City, Dates, Type+CME, Specialty
    headers = ["Kurz", "Name", "Ort", "Datum", "Typ / CME", "Fachgebiet"]

    pdf.set_font("Helvetica", "B", 7)
    pdf.set_text_color(107, 114, 128)
    for i, h in enumerate(headers):
        pdf.cell(col_widths[i], 6, _safe(h))
    pdf.ln()

    pdf.set_draw_color(229, 231, 235)
    pdf.line(16, pdf.get_y(), 391, pdf.get_y())
    pdf.ln(2)

    # Rows
    for group_name, group_congresses in grouped:
        # Group header
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(75, 85, 99)
        pdf.cell(0, 7, _safe(group_name.upper()), ln=True)
        pdf.set_draw_color(229, 231, 235)
        pdf.line(16, pdf.get_y(), 391, pdf.get_y())
        pdf.ln(1)

        for c in group_congresses:
            spec = c.get("specialty", "")
            color = _SPEC_COLORS.get(spec, (139, 139, 160))
            short = c.get("short", "")[:12]
            name = c.get("name", "")[:55]
            city = c.get("city", "")
            country = c.get("country", "")
            loc = f"{city}, {country}" if country != "Deutschland" else city

            ds = c.get("date_start", "")
            de = c.get("date_end", "")
            dates = f"{ds[8:10]}.{ds[5:7]}." if ds else ""
            if de and de != ds:
                dates += f" - {de[8:10]}.{de[5:7]}."

            ctype = "INT" if c.get("congress_type") == "international" else "DE"
            cme = c.get("cme_points")
            type_cme = ctype
            if cme:
                type_cme += f" | {cme} CME"

            # Color dot
            pdf.set_fill_color(*color)
            y_before = pdf.get_y()
            pdf.circle(pdf.get_x() + 3, y_before + 2.5, 1.5, style="F")

            # Short name (bold)
            pdf.set_x(pdf.get_x() + 7)
            pdf.set_font("Helvetica", "B", 7.5)
            pdf.set_text_color(26, 26, 46)
            pdf.cell(col_widths[0] - 7, 5, _safe(short))

            # Name
            pdf.set_font("Helvetica", "", 7)
            pdf.set_text_color(75, 85, 99)
            pdf.cell(col_widths[1], 5, _safe(name))

            # City
            pdf.cell(col_widths[2], 5, _safe(loc[:25]))

            # Dates
            pdf.set_font("Helvetica", "", 7)
            pdf.set_text_color(107, 114, 128)
            pdf.cell(col_widths[3], 5, _safe(dates))

            # Type + CME
            pdf.set_font("Helvetica", "B", 6.5)
            if ctype == "INT":
                pdf.set_text_color(29, 78, 216)
            else:
                pdf.set_text_color(21, 128, 61)
            pdf.cell(col_widths[4], 5, _safe(type_cme))

            # Specialty
            pdf.set_font("Helvetica", "", 7)
            pdf.set_text_color(*color)
            pdf.cell(col_widths[5], 5, _safe(spec))

            pdf.ln()

            # Subtle row separator
            pdf.set_draw_color(243, 244, 246)
            pdf.line(16, pdf.get_y(), 391, pdf.get_y())

        pdf.ln(2)

    # Footer
    pdf.set_y(-20)
    pdf.set_font("Helvetica", "", 6.5)
    pdf.set_text_color(156, 163, 175)

    # Legend: unique specialties
    used_specs = sorted(set(c.get("specialty", "Sonstige") for c in year_congresses))
    legend_parts = []
    for spec in used_specs[:15]:  # max 15 in footer
        legend_parts.append(spec)
    pdf.cell(0, 4, _safe("Fachgebiete: " + " | ".join(legend_parts)))
    pdf.ln()

    pdf.set_text_color(200, 200, 210)
    pdf.cell(0, 4, _safe(f"Erstellt am {date.today().strftime('%d.%m.%Y')} | lumio.app"))

    pdf_bytes = pdf.output()
    logger.info("Generated congress PDF: %d bytes, %d congresses", len(pdf_bytes), len(year_congresses))
    return bytes(pdf_bytes)
