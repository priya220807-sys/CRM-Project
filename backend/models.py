from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db

LEAD_STATUSES = ["new", "contacted", "qualified", "proposal", "won", "lost"]
INTERACTION_TYPES = ["note", "call", "email", "meeting"]
ROLES = ["admin", "sales"]


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="sales")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {"id": self.id, "username": self.username, "email": self.email, "role": self.role}


class Customer(db.Model):
    __tablename__ = "customers"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30))
    company = db.Column(db.String(100))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    leads = db.relationship("Lead", backref="customer", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "email": self.email, "phone": self.phone,
            "company": self.company, "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Lead(db.Model):
    __tablename__ = "leads"
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="new")
    assigned_to = db.Column(db.Integer, db.ForeignKey("users.id"))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    assignee = db.relationship("User", backref="leads")
    interactions = db.relationship("Interaction", backref="lead", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id, "customer_id": self.customer_id,
            "customer_name": self.customer.name if self.customer else None,
            "company": self.customer.company if self.customer else None,
            "status": self.status, "assigned_to": self.assigned_to,
            "assigned_username": self.assignee.username if self.assignee else None,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Interaction(db.Model):
    __tablename__ = "interactions"
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id"), nullable=False)
    interaction_type = db.Column(db.String(20), nullable=False)
    description = db.Column(db.Text, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    author = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id, "lead_id": self.lead_id,
            "customer_name": self.lead.customer.name if self.lead and self.lead.customer else None,
            "interaction_type": self.interaction_type, "description": self.description,
            "date": self.date.isoformat() if self.date else None,
            "created_by": self.author.username if self.author else None,
        }
