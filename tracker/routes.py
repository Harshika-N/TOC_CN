import uuid
from datetime import datetime, timezone
from flask import Blueprint, jsonify, render_template, request
from .classification import classify, priority
from .db import get_db
from .dispatch import dispatch, process_queue
from .validation import validate_identifier, route_key

bp = Blueprint("main", __name__)
NOW = lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")

@bp.get("/")
def index():
    return render_template("index.html")

@bp.get("/api/reports")
def reports():
    db=get_db(); rows=db.execute("SELECT r.*,h.name handler_name,d.name depot_name FROM reports r LEFT JOIN handlers h ON h.id=r.handler_id LEFT JOIN depots d ON d.id=r.depot_id ORDER BY CASE r.priority WHEN 'Critical' THEN 0 WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END,r.created_at DESC").fetchall()
    return jsonify([dict(x) for x in rows])

@bp.post("/api/reports")
def create_report():
    data=request.get_json(silent=True) or request.form
    bus=(data.get("bus_id") or "").strip().upper()
    validation=validate_identifier(bus)
    if not validation["valid"]: return jsonify({"error":validation["message"],"validation":validation}),400
    desc=(data.get("description") or "").strip(); code=(data.get("code") or "").strip().upper()
    category=classify(desc,code)
    if not category: return jsonify({"error":"We could not identify a supported breakdown type. Add a recognized symptom or code.","validation":validation}),422
    required=["reporter","contact","urgency"]
    if any(not str(data.get(k,"")).strip() for k in required) or not desc or not code:
        return jsonify({"error":"Reporter, contact, code, description, and urgency are required."}),400
    db=get_db(); key=route_key(bus); report_id="BR-"+uuid.uuid4().hex[:8].upper(); created=NOW(); pr=priority(category,data.get("urgency"))
    db.execute("INSERT INTO reports(id,reporter,contact,bus_id,route_key,code,description,urgency,category,priority,status,routing_note,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,'Pending',?,?,?)",
        (report_id,data.get("reporter").strip(),data.get("contact").strip(),bus,key,code,desc,data.get("urgency"),category,pr,"Dispatch decision pending",created,created))
    db.commit()
    known=db.execute("SELECT 1 FROM route_distances WHERE route_key=?",(key,)).fetchone()
    if not known: db.execute("UPDATE reports SET status='Queued',routing_note=? WHERE id=?",("Unknown route zone - sent to central correction queue",report_id)); db.commit()
    else: dispatch(report_id)
    result=db.execute("SELECT r.*,h.name handler_name,d.name depot_name FROM reports r LEFT JOIN handlers h ON h.id=r.handler_id LEFT JOIN depots d ON d.id=r.depot_id WHERE r.id=?",(report_id,)).fetchone()
    return jsonify(dict(result)),201

@bp.patch("/api/reports/<report_id>/status")
def update_status(report_id):
    data=request.get_json(silent=True) or {}; status=data.get("status")
    if status not in ("Assigned","In Progress","Resolved"): return jsonify({"error":"Status must be Assigned, In Progress, or Resolved."}),400
    db=get_db(); row=db.execute("SELECT * FROM reports WHERE id=?",(report_id,)).fetchone()
    if not row: return jsonify({"error":"Report not found."}),404
    handler=data.get("handler_id",row["handler_id"])
    if handler and not db.execute("SELECT 1 FROM handlers WHERE id=?",(handler,)).fetchone(): return jsonify({"error":"Unknown handler."}),400
    allowed={"Pending":{"Assigned"},"Queued":{"Assigned"},"Assigned":{"In Progress","Resolved"},"In Progress":{"Resolved"},"Escalated":{"Resolved"},"Resolved":set()}
    if status not in allowed[row["status"]]: return jsonify({"error":f"Cannot move a {row['status']} report to {status}."}),409
    db.execute("UPDATE reports SET status=?,handler_id=?,updated_at=? WHERE id=?",(status,handler,NOW(),report_id)); db.commit()
    process_queue()
    return jsonify({"ok":True})

@bp.get("/api/handlers")
def handlers():
    rows=get_db().execute("SELECT h.*,d.name depot_name,(SELECT COUNT(*) FROM reports r WHERE r.handler_id=h.id AND r.status IN ('Assigned','In Progress')) load FROM handlers h JOIN depots d ON d.id=h.depot_id ORDER BY h.id").fetchall()
    return jsonify([dict(x) for x in rows])

@bp.patch("/api/handlers/<handler_id>")
def update_handler(handler_id):
    data=request.get_json(silent=True) or {}; db=get_db()
    if not db.execute("SELECT 1 FROM handlers WHERE id=?",(handler_id,)).fetchone(): return jsonify({"error":"Handler not found."}),404
    if "available" in data: db.execute("UPDATE handlers SET available=? WHERE id=?",(int(bool(data["available"])),handler_id))
    if "capacity" in data:
        try: cap=int(data["capacity"])
        except (ValueError,TypeError): return jsonify({"error":"Capacity must be a positive whole number."}),400
        if cap<1: return jsonify({"error":"Capacity must be a positive whole number."}),400
        db.execute("UPDATE handlers SET capacity=? WHERE id=?",(cap,handler_id))
    db.commit(); process_queue(); return jsonify({"ok":True})

@bp.get("/api/routing")
def routing():
    db=get_db(); distances=db.execute("SELECT rd.route_key,d.name depot_name,rd.km FROM route_distances rd JOIN depots d ON d.id=rd.depot_id ORDER BY rd.route_key,rd.km").fetchall()
    return jsonify({"distances":[dict(x) for x in distances],"handlers":[dict(x) for x in db.execute("SELECT h.id,h.name,d.name depot_name,h.available,h.capacity,(SELECT COUNT(*) FROM reports r WHERE r.handler_id=h.id AND r.status IN ('Assigned','In Progress')) load FROM handlers h JOIN depots d ON d.id=h.depot_id")],"queue":[dict(x) for x in db.execute("SELECT id,bus_id,category,priority,status,routing_note,created_at FROM reports WHERE status IN ('Queued','Escalated') ORDER BY created_at,id")]})

@bp.get("/api/analytics")
def analytics():
    db=get_db()
    return jsonify({"categories":[dict(x) for x in db.execute("SELECT category,COUNT(*) count FROM reports GROUP BY category ORDER BY category")],"zones":[dict(x) for x in db.execute("SELECT route_key zone,COUNT(*) count FROM reports GROUP BY route_key ORDER BY route_key")],"resolved":db.execute("SELECT COUNT(*) FROM reports WHERE status='Resolved'").fetchone()[0],"unresolved":db.execute("SELECT COUNT(*) FROM reports WHERE status!='Resolved'").fetchone()[0]})
