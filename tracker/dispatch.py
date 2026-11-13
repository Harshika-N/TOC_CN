from .db import get_db

ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Normal": 3}

def dispatch(report_id):
    db = get_db()
    report = db.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
    if not report or report["status"] not in ("Pending", "Queued") or report["handler_id"]:
        return
    if report["priority"] == "Critical":
        db.execute("UPDATE reports SET routing_note=?, status='Escalated' WHERE id=?", ("Emergency authority notified; supervisor dispatch required", report_id))
        db.commit()
        return
    rows = db.execute("""SELECT d.id depot_id,d.name depot_name,d.capacity depot_capacity,
        (SELECT COUNT(*) FROM reports dr WHERE dr.depot_id=d.id AND dr.status IN ('Assigned','In Progress')) depot_load,
        h.id handler_id,h.name handler_name,h.specialties,h.capacity,
        (SELECT COUNT(*) FROM reports r WHERE r.handler_id=h.id AND r.status IN ('Assigned','In Progress')) load,rd.km
        FROM route_distances rd JOIN depots d ON d.id=rd.depot_id JOIN handlers h ON h.depot_id=d.id
        WHERE rd.route_key=? AND h.available=1 ORDER BY rd.km,d.id,h.id""", (report["route_key"],)).fetchall()
    if not rows:
        db.execute("UPDATE reports SET status='Queued',routing_note=? WHERE id=?",
                   ("Unknown route zone - sent to central correction queue", report_id))
        db.commit()
        return
    for row in rows:
        if (report["category"] not in row["specialties"].split(",") or
                row["load"] >= row["capacity"] or row["depot_load"] >= row["depot_capacity"]):
            continue
        db.execute("UPDATE reports SET status='Assigned',handler_id=?,depot_id=?,routing_note=? WHERE id=? AND handler_id IS NULL",
                   (row["handler_id"],row["depot_id"],f"{row['depot_name']} via {row['handler_name']} ({row['km']:g} km)",report_id))
        db.commit()
        return
    db.execute("UPDATE reports SET status='Queued',routing_note=? WHERE id=?", ("No eligible handler with spare capacity; waiting queue",report_id))
    db.commit()

def process_queue():
    db = get_db()
    queued = db.execute("SELECT id FROM reports WHERE status IN ('Pending','Queued') ORDER BY CASE priority WHEN 'Critical' THEN 0 WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END,created_at,id").fetchall()
    for row in queued:
        dispatch(row["id"])
