import os
import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from database import connect

OUTPUT_PATH = "logs_report.pdf"


def export_logs():
    """
    Relit toutes les données depuis la base SQLite,
    supprime l'ancien PDF s'il existe, puis génère un nouveau.
    """

    # ── 1. Supprimer l'ancien PDF pour forcer la régénération ──────────────
    if os.path.exists(OUTPUT_PATH):
        os.remove(OUTPUT_PATH)

    # ── 2. Lire les logs frais depuis la DB ────────────────────────────────
    conn = connect()
    cur  = conn.cursor()
    cur.execute("SELECT id, user, status, watermark FROM logs ORDER BY id DESC")
    rows = cur.fetchall()

    cur.execute("SELECT COUNT(*) FROM logs")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM logs WHERE status='GRANTED'")
    granted = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM logs WHERE status='DENIED'")
    denied = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM logs WHERE status='BANNED'")
    banned = cur.fetchone()[0]
    conn.close()

    # ── 3. Styles ──────────────────────────────────────────────────────────
    styles = getSampleStyleSheet()

    style_title = ParagraphStyle(
        "title",
        fontSize=22,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#00e5ff"),
        alignment=TA_CENTER,
        spaceAfter=4,
    )
    style_sub = ParagraphStyle(
        "sub",
        fontSize=9,
        fontName="Helvetica",
        textColor=colors.HexColor("#5a7a8a"),
        alignment=TA_CENTER,
        spaceAfter=2,
    )
    style_section = ParagraphStyle(
        "section",
        fontSize=11,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#e8f4f8"),
        spaceAfter=6,
        spaceBefore=14,
    )
    style_normal = ParagraphStyle(
        "normal",
        fontSize=9,
        fontName="Helvetica",
        textColor=colors.HexColor("#e8f4f8"),
    )

    # ── 4. Construire le document ──────────────────────────────────────────
    doc = SimpleDocTemplate(
        OUTPUT_PATH,
        pagesize=A4,
        leftMargin=1.8*cm, rightMargin=1.8*cm,
        topMargin=1.8*cm,  bottomMargin=1.8*cm,
    )

    story = []
    now_str = datetime.datetime.now().strftime("%Y-%m-%d  %H:%M:%S")

    # En-tête
    story.append(Paragraph("VisionLock — Access Report", style_title))
    
    story.append(Spacer(1, 0.3*cm))
    story.append(HRFlowable(width="100%", thickness=1,
                             color=colors.HexColor("#1a3a4a")))
    story.append(Spacer(1, 0.4*cm))

    # Résumé statistiques
    story.append(Paragraph("RÉSUMÉ", style_section))
    stat_data = [
        ["Total logs", "Granted", "Denied", "Banned"],
        [str(total), str(granted), str(denied), str(banned)],
    ]
    stat_table = Table(stat_data, colWidths=[4*cm]*4)
    stat_table.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), colors.HexColor("#0b1520")),
        ("TEXTCOLOR",   (0, 0), (-1, 0), colors.HexColor("#5a7a8a")),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, 0), 8),
        ("LETTERSPACING",(0,0),(-1,0), 1),

        ("BACKGROUND",  (0, 1), (0, 1), colors.HexColor("#0f1e2e")),
        ("TEXTCOLOR",   (0, 1), (0, 1), colors.HexColor("#00e5ff")),  # total cyan
        ("BACKGROUND",  (1, 1), (1, 1), colors.HexColor("#0f1e2e")),
        ("TEXTCOLOR",   (1, 1), (1, 1), colors.HexColor("#00ff9d")),  # granted green
        ("BACKGROUND",  (2, 1), (2, 1), colors.HexColor("#0f1e2e")),
        ("TEXTCOLOR",   (2, 1), (2, 1), colors.HexColor("#ff2d55")),  # denied red
        ("BACKGROUND",  (3, 1), (3, 1), colors.HexColor("#0f1e2e")),
        ("TEXTCOLOR",   (3, 1), (3, 1), colors.HexColor("#ff6b2b")),  # banned orange

        ("FONTNAME",    (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 1), (-1, 1), 16),
        ("ALIGN",       (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUND",(0,0),(-1,-1), [colors.HexColor("#0f1e2e")]),
        ("BOX",         (0, 0), (-1, -1), 0.5, colors.HexColor("#1a3a4a")),
        ("INNERGRID",   (0, 0), (-1, -1), 0.5, colors.HexColor("#1a3a4a")),
        ("TOPPADDING",  (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING",(0,0),(-1,-1), 10),
    ]))
    story.append(stat_table)
    story.append(Spacer(1, 0.5*cm))

    # Table des logs
    story.append(Paragraph("JOURNAL D'ACCÈS", style_section))

    header = ["ID", "UTILISATEUR", "STATUT", "HORODATAGE"]
    table_data = [header] + [
        [str(r[0]), str(r[1] or "—"), str(r[2] or "—"), str(r[3] or "—")]
        for r in rows
    ]

    col_widths = [1.5*cm, 5*cm, 4*cm, 6.5*cm]
    log_table  = Table(table_data, colWidths=col_widths, repeatRows=1)

    # Couleurs par statut
    row_styles = [
        ("BACKGROUND",   (0, 0), (-1, 0),  colors.HexColor("#0b1520")),
        ("TEXTCOLOR",    (0, 0), (-1, 0),  colors.HexColor("#5a7a8a")),
        ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, 0),  8),
        ("ALIGN",        (0, 0), (-1, -1), "LEFT"),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME",     (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",     (0, 1), (-1, -1), 8),
        ("TEXTCOLOR",    (0, 1), (-1, -1), colors.HexColor("#e8f4f8")),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),
         [colors.HexColor("#0f1e2e"), colors.HexColor("#0b1520")]),
        ("BOX",          (0, 0), (-1, -1), 0.5, colors.HexColor("#1a3a4a")),
        ("INNERGRID",    (0, 0), (-1, -1), 0.3, colors.HexColor("#1a3a4a")),
        ("TOPPADDING",   (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 7),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
    ]

    # Colorier chaque ligne selon le statut
    for i, row in enumerate(rows, start=1):
        status = str(row[2]).upper()
        if "GRANT" in status:
            row_styles.append(("TEXTCOLOR", (2, i), (2, i), colors.HexColor("#00ff9d")))
        elif "BANNED" in status:
            row_styles.append(("TEXTCOLOR", (2, i), (2, i), colors.HexColor("#ff6b2b")))
        elif "DENY" in status or "FAIL" in status:
            row_styles.append(("TEXTCOLOR", (2, i), (2, i), colors.HexColor("#ff2d55")))

    log_table.setStyle(TableStyle(row_styles))
    story.append(log_table)

    # Pied de page
    story.append(Spacer(1, 0.6*cm))
    story.append(HRFlowable(width="100%", thickness=1,
                             color=colors.HexColor("#1a3a4a")))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(
        f"VisionLock AI Security  •  {now_str}  •  {total} entrée(s)",
        style_sub
    ))

    doc.build(story)
    print(f"[PDF] Généré : {OUTPUT_PATH}  ({len(rows)} logs)")