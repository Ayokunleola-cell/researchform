# backend/api/routers/export.py
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import io

from api.deps import get_db, get_current_user
from api.models.database import Survey, Question, Response, User

router = APIRouter()

async def get_survey_data(survey_id: str, user: User, db: AsyncSession):
    r = await db.execute(select(Survey).where(Survey.id == survey_id, Survey.user_id == user.id))
    s = r.scalar_one_or_none()
    if not s: raise HTTPException(404, "Survey not found")

    qr = await db.execute(select(Question).where(Question.survey_id == survey_id).order_by(Question.position))
    qs = qr.scalars().all()

    rr = await db.execute(select(Response).where(Response.survey_id == survey_id))
    rs = rr.scalars().all()

    return s, qs, rs

@router.get("/{survey_id}/csv")
async def export_csv(survey_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    import csv
    survey, questions, responses = await get_survey_data(survey_id, user, db)

    output = io.StringIO()
    qs_non_header = [q for q in questions if q.type != "section_header"]
    headers = ["response_id", "submitted_at"] + [q.variable_name or f"q{i+1}" for i, q in enumerate(qs_non_header)]
    writer = csv.writer(output)
    writer.writerow(headers)

    for resp in responses:
        row = [resp.id, str(resp.submitted_at)]
        for q in qs_non_header:
            val = resp.answers.get(q.id, "")
            if isinstance(val, list):
                val = "; ".join(str(v) for v in val)
            row.append(val)
        writer.writerow(row)

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{survey.title}.csv"'},
    )

@router.get("/{survey_id}/xlsx")
async def export_xlsx(survey_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        raise HTTPException(500, "openpyxl not installed")

    survey, questions, responses = await get_survey_data(survey_id, user, db)
    qs_non_header = [q for q in questions if q.type != "section_header"]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Responses"

    # Header row
    headers = ["Response ID", "Submitted At"] + [q.variable_name or f"q{i+1}" for i, q in enumerate(qs_non_header)]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="6366F1")
        cell.alignment = Alignment(horizontal="center")

    # Data
    for row_idx, resp in enumerate(responses, 2):
        ws.cell(row=row_idx, column=1, value=resp.id)
        ws.cell(row=row_idx, column=2, value=str(resp.submitted_at))
        for col_idx, q in enumerate(qs_non_header, 3):
            val = resp.answers.get(q.id, "")
            if isinstance(val, list): val = "; ".join(str(v) for v in val)
            ws.cell(row=row_idx, column=col_idx, value=val)

    # Codebook sheet
    ws2 = wb.create_sheet("Codebook")
    ws2.append(["Variable", "Question", "Type", "Measurement Level", "Required"])
    for q in qs_non_header:
        ws2.append([q.variable_name, q.text, q.type, q.measurement_level, "Yes" if q.required else "No"])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{survey.title}.xlsx"'},
    )

@router.get("/{survey_id}/sav")
async def export_sav(survey_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Export as SPSS .sav with value labels."""
    try:
        import pyreadstat
        import pandas as pd
    except ImportError:
        raise HTTPException(500, "pyreadstat not installed — pip install pyreadstat")

    survey, questions, responses = await get_survey_data(survey_id, user, db)
    qs_non_header = [q for q in questions if q.type != "section_header"]

    rows = []
    for resp in responses:
        row = {}
        for q in qs_non_header:
            vname = q.variable_name or f"q{q.position+1}"
            val = resp.answers.get(q.id)
            if isinstance(val, list):
                val = "; ".join(str(v) for v in val)
            row[vname] = val
        rows.append(row)

    df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=[q.variable_name or f"q{i+1}" for i, q in enumerate(qs_non_header)])

    # Build value labels
    variable_value_labels = {}
    column_labels = {}
    for q in qs_non_header:
        vname = q.variable_name or f"q{q.position+1}"
        column_labels[vname] = q.text[:60] if q.text else vname
        if q.type in ("likert", "single_choice", "rating") and q.options:
            labels = {}
            for i, opt in enumerate(q.options):
                labels[i + 1] = str(opt)
                # Replace string values with numeric codes
                if vname in df.columns:
                    df[vname] = df[vname].replace(opt, i + 1)
            variable_value_labels[vname] = labels
        if vname in df.columns:
            try:
                df[vname] = pd.to_numeric(df[vname], errors="ignore")
            except Exception:
                pass

    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".sav", delete=False) as tmp:
        tmp_path = tmp.name

    pyreadstat.write_sav(
        df, tmp_path,
        column_labels=column_labels,
        variable_value_labels=variable_value_labels,
    )

    with open(tmp_path, "rb") as f:
        data = f.read()
    os.unlink(tmp_path)

    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{survey.title}.sav"'},
    )

@router.get("/{survey_id}/codebook")
async def export_codebook(survey_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Export variable codebook as PDF."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
        from reportlab.lib import colors
    except ImportError:
        raise HTTPException(500, "reportlab not installed — pip install reportlab")

    survey, questions, responses = await get_survey_data(survey_id, user, db)
    qs_non_header = [q for q in questions if q.type != "section_header"]

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=60, bottomMargin=60, leftMargin=72, rightMargin=72)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(f"Codebook: {survey.title}", styles["Title"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Generated from ResearchForm · {len(responses)} responses", styles["Normal"]))
    story.append(Spacer(1, 24))

    data = [["#", "Variable", "Question", "Type", "Measurement Level"]]
    for i, q in enumerate(qs_non_header):
        data.append([str(i+1), q.variable_name or f"q{i+1}", q.text[:60] or "", q.type, q.measurement_level or ""])

    t = Table(data, colWidths=[30, 90, 220, 80, 90])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#6366F1")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F5F6FA")]),
        ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#E4E6EF")),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
    ]))
    story.append(t)
    doc.build(story)

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{survey.title}_codebook.pdf"'},
    )
