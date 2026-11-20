from pathlib import Path
import csv, html, json
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm

def flatten(obj, prefix=""):
    rows=[]
    if isinstance(obj, dict):
        for k,v in obj.items():
            rows += flatten(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(obj, list):
        for i,v in enumerate(obj):
            rows += flatten(v, f"{prefix}[{i}]" )
    else:
        rows.append((prefix, json.dumps(obj, ensure_ascii=False) if isinstance(obj,(str,int,float,bool)) or obj is None else str(obj)))
    return rows

def export_report(report, path, fmt):
    path=Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    rows=flatten(report)
    if fmt=="json":
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    elif fmt=="txt":
        path.write_text("\n".join(f"{k}: {v}" for k,v in rows), encoding="utf-8")
    elif fmt=="csv":
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            w=csv.writer(f); w.writerow(["Field","Value"]); w.writerows(rows)
    elif fmt=="html":
        body="".join(f"<tr><td>{html.escape(k)}</td><td>{html.escape(str(v))}</td></tr>" for k,v in rows)
        doc=f"""<!doctype html><html><head><meta charset="utf-8"><title>ImageMetaX report</title>
<style>body{{font:15px system-ui;margin:2rem;background:#101522;color:#e8edf7}}h1{{color:#7dd3fc}}table{{border-collapse:collapse;width:100%}}td{{padding:9px;border-bottom:1px solid #334155;vertical-align:top}}td:first-child{{width:32%;color:#93c5fd;word-break:break-word}}td:last-child{{word-break:break-word}}</style></head><body><h1>ImageMetaX metadata report</h1><table>{body}</table></body></html>"""
        path.write_text(doc, encoding="utf-8")
    elif fmt=="pdf":
        styles=getSampleStyleSheet()
        story=[Paragraph("ImageMetaX Metadata Report", styles["Title"]), Spacer(1,5*mm)]
        cell=ParagraphStyle("cell", parent=styles["BodyText"], fontSize=7, leading=9, wordWrap="CJK")
        data=[[Paragraph("<b>Field</b>",cell),Paragraph("<b>Value</b>",cell)]]
        for k,v in rows:
            data.append([Paragraph(str(k).replace("&","&amp;").replace("<","&lt;"),cell),
                         Paragraph(str(v).replace("&","&amp;").replace("<","&lt;"),cell)])
        table=Table(data, colWidths=[55*mm,125*mm], repeatRows=1)
        table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#dbeafe")),
            ("GRID",(0,0),(-1,-1),.25,colors.HexColor("#cbd5e1")),("VALIGN",(0,0),(-1,-1),"TOP"),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#f8fafc")]),
            ("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5)]))
        story.append(table)
        SimpleDocTemplate(str(path), pagesize=A4, rightMargin=15*mm,leftMargin=15*mm,topMargin=15*mm,bottomMargin=15*mm).build(story)
    else:
        raise ValueError(f"Unsupported export format: {fmt}")
    return path
