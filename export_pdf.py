
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from database import connect

def export_logs():
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT * FROM logs")
    logs = cur.fetchall()

    c = canvas.Canvas("logs_report.pdf", pagesize=letter)
    y = 750

    c.drawString(200, 800, "SMARTACCESS SECURITY LOGS")

    for log in logs:
        c.drawString(50, y, str(log))
        y -= 20

    c.save()

if __name__ == "__main__":
    export_logs()
