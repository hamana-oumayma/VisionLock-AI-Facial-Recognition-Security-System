
from database import connect

def show_dashboard():
    conn = connect()
    cur = conn.cursor()

    cur.execute("SELECT status, COUNT(*) FROM logs GROUP BY status")
    print("DASHBOARD:")
    for row in cur.fetchall():
        print(row)

if __name__ == "__main__":
    show_dashboard()
