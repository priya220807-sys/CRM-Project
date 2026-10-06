import csv
import io
import re
from datetime import datetime
from functools import wraps

from flask import Blueprint, Response, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt, get_jwt_identity, jwt_required
from sqlalchemy import func

from extensions import db
from models import INTERACTION_TYPES, LEAD_STATUSES, Customer, Interaction, Lead, User
from notifications import notify_lead_update

api = Blueprint("api", __name__)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------------------------------------------------------------- helpers
def err(message, code=400):
    return jsonify(error=message), code


def current_user():
    return db.session.get(User, int(get_jwt_identity()))


def admin_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*a, **kw):
        if current_user().role != "admin":
            return err("Admin access required", 403)
        return fn(*a, **kw)
    return wrapper


def can_access_lead(user, lead):
    return user.role == "admin" or lead.assigned_to == user.id


def clean(data, key):
    v = data.get(key)
    return v.strip() if isinstance(v, str) else v


def validate_customer(data, partial=False):
    name, email = clean(data, "name"), clean(data, "email")
    if not partial or "name" in data:
        if not name or len(name) > 100:
            return "Name is required (max 100 characters)"
    if not partial or "email" in data:
        if not email or not EMAIL_RE.match(email):
            return "A valid email is required"
    phone = clean(data, "phone")
    if phone and not re.match(r"^[0-9+\-() ]{6,30}$", phone):
        return "Phone number format is invalid"
    return None


# ---------------------------------------------------------------- auth
@api.post("/auth/signup")
def signup():
    d = request.get_json(silent=True) or {}
    username, email, password = clean(d, "username"), clean(d, "email"), d.get("password")
    if not username or len(username) < 3:
        return err("Username must be at least 3 characters")
    if not email or not EMAIL_RE.match(email):
        return err("A valid email is required")
    if not password or len(password) < 6:
        return err("Password must be at least 6 characters")
    if User.query.filter((User.username == username) | (User.email == email)).first():
        return err("Username or email already exists", 409)
    # The very first account becomes the admin; everyone else is a sales rep.
    role = "admin" if User.query.count() == 0 else "sales"
    user = User(username=username, email=email, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    token = create_access_token(identity=str(user.id))
    return jsonify(token=token, user=user.to_dict()), 201


@api.post("/auth/login")
def login():
    d = request.get_json(silent=True) or {}
    user = User.query.filter_by(username=clean(d, "username")).first()
    if not user or not user.check_password(d.get("password") or ""):
        return err("Invalid username or password", 401)
    return jsonify(token=create_access_token(identity=str(user.id)), user=user.to_dict())


@api.post("/auth/logout")
@jwt_required()
def logout():
    from app import BLOCKLIST
    BLOCKLIST.add(get_jwt()["jti"])
    return jsonify(message="Logged out")


@api.get("/auth/me")
@jwt_required()
def me():
    return jsonify(current_user().to_dict())


@api.get("/users")
@jwt_required()
def list_users():
    return jsonify([u.to_dict() for u in User.query.order_by(User.username)])


@api.put("/users/<int:uid>/role")
@admin_required
def set_role(uid):
    user = db.get_or_404(User, uid)
    role = (request.get_json(silent=True) or {}).get("role")
    if role not in ("admin", "sales"):
        return err("Role must be 'admin' or 'sales'")
    user.role = role
    db.session.commit()
    return jsonify(user.to_dict())


# ---------------------------------------------------------------- customers
@api.get("/customers")
@jwt_required()
def list_customers():
    q = Customer.query
    term = request.args.get("q", "").strip()
    if term:
        like = f"%{term}%"
        q = q.filter(Customer.name.ilike(like) | Customer.email.ilike(like) | Customer.company.ilike(like))
    return jsonify([c.to_dict() for c in q.order_by(Customer.id.desc())])


@api.post("/customers")
@jwt_required()
def create_customer():
    d = request.get_json(silent=True) or {}
    problem = validate_customer(d)
    if problem:
        return err(problem)
    c = Customer(name=clean(d, "name"), email=clean(d, "email"), phone=clean(d, "phone"),
                 company=clean(d, "company"), notes=d.get("notes"))
    db.session.add(c)
    db.session.commit()
    return jsonify(c.to_dict()), 201


@api.get("/customers/<int:cid>")
@jwt_required()
def get_customer(cid):
    return jsonify(db.get_or_404(Customer, cid).to_dict())


@api.put("/customers/<int:cid>")
@jwt_required()
def update_customer(cid):
    c = db.get_or_404(Customer, cid)
    d = request.get_json(silent=True) or {}
    problem = validate_customer(d, partial=True)
    if problem:
        return err(problem)
    for f in ("name", "email", "phone", "company", "notes"):
        if f in d:
            setattr(c, f, clean(d, f))
    db.session.commit()
    return jsonify(c.to_dict())


@api.delete("/customers/<int:cid>")
@admin_required
def delete_customer(cid):
    db.session.delete(db.get_or_404(Customer, cid))
    db.session.commit()
    return jsonify(message="Customer deleted")


# ---------------------------------------------------------------- leads
@api.get("/leads")
@jwt_required()
def list_leads():
    user = current_user()
    q = Lead.query
    if user.role != "admin":
        q = q.filter(Lead.assigned_to == user.id)  # reps only see their own leads
    status = request.args.get("status")
    if status:
        if status not in LEAD_STATUSES:
            return err("Invalid status filter")
        q = q.filter(Lead.status == status)
    assigned = request.args.get("assigned_to", type=int)
    if assigned and user.role == "admin":
        q = q.filter(Lead.assigned_to == assigned)
    return jsonify([l.to_dict() for l in q.order_by(Lead.updated_at.desc())])


@api.post("/leads")
@jwt_required()
def create_lead():
    user = current_user()
    d = request.get_json(silent=True) or {}
    if not db.session.get(Customer, d.get("customer_id") or 0):
        return err("Valid customer_id is required")
    status = d.get("status", "new")
    if status not in LEAD_STATUSES:
        return err(f"Status must be one of {LEAD_STATUSES}")
    assigned = d.get("assigned_to") if user.role == "admin" and d.get("assigned_to") else user.id
    if not db.session.get(User, assigned):
        return err("Assigned user does not exist")
    lead = Lead(customer_id=d["customer_id"], status=status, assigned_to=assigned, notes=d.get("notes"))
    db.session.add(lead)
    db.session.commit()
    if assigned != user.id:
        notify_lead_update(lead, f"A new lead for {lead.customer.name} was assigned to you.")
    return jsonify(lead.to_dict()), 201


@api.get("/leads/<int:lid>")
@jwt_required()
def get_lead(lid):
    lead = db.get_or_404(Lead, lid)
    if not can_access_lead(current_user(), lead):
        return err("Forbidden", 403)
    return jsonify(lead.to_dict())


@api.route("/leads/<int:lid>", methods=["PUT", "PATCH"])
@jwt_required()
def update_lead(lid):
    user = current_user()
    lead = db.get_or_404(Lead, lid)
    if not can_access_lead(user, lead):
        return err("Forbidden", 403)
    d = request.get_json(silent=True) or {}
    if "status" in d:
        if d["status"] not in LEAD_STATUSES:
            return err(f"Status must be one of {LEAD_STATUSES}")
        old, lead.status = lead.status, d["status"]
        if old != lead.status:
            notify_lead_update(lead, f"Lead for {lead.customer.name} moved from {old} to {lead.status}.")
    if "notes" in d:
        lead.notes = d["notes"]
    if "assigned_to" in d and user.role == "admin":
        if not db.session.get(User, d["assigned_to"] or 0):
            return err("Assigned user does not exist")
        lead.assigned_to = d["assigned_to"]
    db.session.commit()
    return jsonify(lead.to_dict())


@api.delete("/leads/<int:lid>")
@jwt_required()
def delete_lead(lid):
    lead = db.get_or_404(Lead, lid)
    if not can_access_lead(current_user(), lead):
        return err("Forbidden", 403)
    db.session.delete(lead)
    db.session.commit()
    return jsonify(message="Lead deleted")


# ---------------------------------------------------------------- interactions
@api.get("/leads/<int:lid>/interactions")
@jwt_required()
def list_interactions(lid):
    lead = db.get_or_404(Lead, lid)
    if not can_access_lead(current_user(), lead):
        return err("Forbidden", 403)
    items = Interaction.query.filter_by(lead_id=lid).order_by(Interaction.date.desc())
    return jsonify([i.to_dict() for i in items])


@api.post("/leads/<int:lid>/interactions")
@jwt_required()
def create_interaction(lid):
    user = current_user()
    lead = db.get_or_404(Lead, lid)
    if not can_access_lead(user, lead):
        return err("Forbidden", 403)
    d = request.get_json(silent=True) or {}
    itype, desc = d.get("interaction_type"), (d.get("description") or "").strip()
    if itype not in INTERACTION_TYPES:
        return err(f"interaction_type must be one of {INTERACTION_TYPES}")
    if not desc:
        return err("Description is required")
    when = datetime.utcnow()
    if d.get("date"):
        try:
            when = datetime.fromisoformat(d["date"].replace("Z", ""))
        except ValueError:
            return err("Invalid date format (use ISO 8601)")
    item = Interaction(lead_id=lid, interaction_type=itype, description=desc, date=when, created_by=user.id)
    db.session.add(item)
    lead.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(item.to_dict()), 201


def _own_interaction(iid):
    item = db.get_or_404(Interaction, iid)
    return item if can_access_lead(current_user(), item.lead) else None


@api.put("/interactions/<int:iid>")
@jwt_required()
def update_interaction(iid):
    item = _own_interaction(iid)
    if not item:
        return err("Forbidden", 403)
    d = request.get_json(silent=True) or {}
    if "interaction_type" in d:
        if d["interaction_type"] not in INTERACTION_TYPES:
            return err(f"interaction_type must be one of {INTERACTION_TYPES}")
        item.interaction_type = d["interaction_type"]
    if "description" in d:
        if not (d["description"] or "").strip():
            return err("Description cannot be empty")
        item.description = d["description"].strip()
    db.session.commit()
    return jsonify(item.to_dict())


@api.delete("/interactions/<int:iid>")
@jwt_required()
def delete_interaction(iid):
    item = _own_interaction(iid)
    if not item:
        return err("Forbidden", 403)
    db.session.delete(item)
    db.session.commit()
    return jsonify(message="Interaction deleted")


# ---------------------------------------------------------------- dashboard + export
@api.get("/dashboard/stats")
@jwt_required()
def dashboard_stats():
    user = current_user()
    lq, iq = Lead.query, Interaction.query.join(Lead)
    if user.role != "admin":
        lq, iq = lq.filter(Lead.assigned_to == user.id), iq.filter(Lead.assigned_to == user.id)
    counts = dict(
        lq.with_entities(Lead.status, func.count(Lead.id)).group_by(Lead.status).all()
    )
    by_status = {s: counts.get(s, 0) for s in LEAD_STATUSES}
    total_leads = sum(by_status.values())
    closed = by_status["won"] + by_status["lost"]
    recent = iq.order_by(Interaction.date.desc()).limit(10).all()
    return jsonify(
        total_customers=Customer.query.count(),
        total_leads=total_leads,
        leads_by_status=by_status,
        win_rate=round(by_status["won"] / closed * 100, 1) if closed else 0,
        recent_interactions=[i.to_dict() for i in recent],
    )


def _csv_response(filename, header, rows):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(rows)
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={filename}"})


@api.get("/export/customers")
@jwt_required()
def export_customers():
    rows = [[c.id, c.name, c.email, c.phone, c.company, c.notes] for c in Customer.query.all()]
    return _csv_response("customers.csv", ["id", "name", "email", "phone", "company", "notes"], rows)


@api.get("/export/leads")
@jwt_required()
def export_leads():
    user = current_user()
    q = Lead.query if user.role == "admin" else Lead.query.filter_by(assigned_to=user.id)
    rows = [[l.id, l.customer.name, l.customer.company,
             l.status, l.assignee.username if l.assignee else "", l.notes] for l in q.all()]
    return _csv_response("leads.csv", ["id", "customer", "company", "status", "assigned_to", "notes"], rows)
