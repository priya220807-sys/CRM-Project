"""Populate the database with demo data:  python seed.py"""
from datetime import datetime, timedelta
from app import app
from extensions import db
from models import Customer, Interaction, Lead, User

with app.app_context():
    db.drop_all()
    db.create_all()
    admin = User(username="admin", email="admin@crm.com", role="admin"); admin.set_password("admin123")
    rep1 = User(username="priya", email="priya@crm.com", role="sales"); rep1.set_password("sales123")
    rep2 = User(username="rahul", email="rahul@crm.com", role="sales"); rep2.set_password("sales123")
    db.session.add_all([admin, rep1, rep2]); db.session.commit()

    people = [("Aarav Sharma", "Infosys"), ("Neha Verma", "TCS"), ("Karan Singh", "Wipro"),
              ("Sneha Iyer", "Zoho"), ("Vikram Rao", "Flipkart"), ("Meera Nair", "Paytm"),
              ("Rohan Gupta", "Swiggy"), ("Anjali Das", "Freshworks")]
    customers = []
    for i, (n, c) in enumerate(people):
        cu = Customer(name=n, email=f"{n.split()[0].lower()}@{c.lower()}.com",
                      phone=f"98765{10000 + i}", company=c, notes="Imported demo customer")
        customers.append(cu)
    db.session.add_all(customers); db.session.commit()

    statuses = ["new", "contacted", "qualified", "proposal", "won", "lost", "contacted", "new"]
    leads = []
    for i, cu in enumerate(customers):
        leads.append(Lead(customer_id=cu.id, status=statuses[i],
                          assigned_to=(rep1 if i % 2 == 0 else rep2).id, notes="Interested in CRM plan"))
    db.session.add_all(leads); db.session.commit()

    kinds = ["call", "email", "note", "meeting"]
    for i, l in enumerate(leads):
        for j in range(2):
            db.session.add(Interaction(lead_id=l.id, interaction_type=kinds[(i + j) % 4],
                                       description=f"Follow-up #{j + 1} with {l.customer.name}",
                                       date=datetime.utcnow() - timedelta(days=i + j),
                                       created_by=l.assigned_to))
    db.session.commit()
    print("Seeded. Logins -> admin/admin123, priya/sales123, rahul/sales123")
