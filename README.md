# MiniCRM - Customer & Lead Management System

A full-stack CRM web application to manage customers, sales leads and interactions,
with an admin dashboard for monitoring the sales pipeline.

**Stack:** React 18 (Vite) + Recharts | Flask + SQLAlchemy | JWT auth | SQLite (PostgreSQL ready)

## Features
- Signup / Login / Logout (JWT, token revocation on logout)
- Customers: list, search, add, edit, delete
- Leads: CRUD, filter by status & assigned user, **drag-and-drop Kanban board**
- Interactions (note / call / email / meeting) logged per lead
- Dashboard: totals, leads by status, win-rate, pipeline chart, recent-activity feed
- CSV export (customers, leads) and Print/Save-as-PDF
- **Role-based access control:** first user = `admin`; others = `sales`
  (reps only see their own leads; only admins can delete customers / reassign leads)
- Optional e-mail notifications on lead assignment / status change (SMTP via `.env`)
- Input validation + JSON error handling; automated tests (pytest)

## Project structure
```
CRMProject/
├── backend/   app.py, config.py, models.py, routes.py, notifications.py, seed.py, test_api.py, requirements.txt
├── frontend/  src/{components,pages,services,context}, package.json, vite.config.js
├── docs/      CRM_Project_Report.docx
├── README.md
└── .gitignore
```

## Setup & run

### 1. Backend (Python 3.10+)
```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows   (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
cp .env.example .env           # optional - edit secrets
python seed.py                 # optional - demo data
python app.py                  # API on http://127.0.0.1:5000
```
Demo logins after seeding: `admin / admin123`, `priya / sales123`, `rahul / sales123`.
Without seeding, the first account you sign up becomes the admin.

### 2. Frontend (Node 18+)
```bash
cd frontend
npm install
npm run dev                    # http://localhost:5173  (proxies /api to Flask)
```

### 3. Run tests
```bash
cd backend && pip install pytest && python -m pytest -q
```

## REST API summary
| Method | Endpoint | Description |
|---|---|---|
| POST | /api/auth/signup, /login, /logout | Authentication |
| GET | /api/auth/me, /api/users | Current user / user list |
| GET POST | /api/customers | List (`?q=` search) / create |
| GET PUT DELETE | /api/customers/:id | Read / update / delete (admin) |
| GET POST | /api/leads | List (`?status=&assigned_to=`) / create |
| GET PUT PATCH DELETE | /api/leads/:id | Read / update / status change / delete |
| GET POST | /api/leads/:id/interactions | List / create interactions |
| PUT DELETE | /api/interactions/:id | Update / delete interaction |
| GET | /api/dashboard/stats | Counts, leads by status, recent feed |
| GET | /api/export/customers, /export/leads | CSV downloads |

All routes except signup/login require `Authorization: Bearer <token>`.

## Deployment (Railway / Render / PythonAnywhere)
- **Backend:** push `backend/` ; start command `gunicorn app:app` (Procfile included);
  set `SECRET_KEY`, `JWT_SECRET_KEY`, and optionally `DATABASE_URL` (PostgreSQL).
- **Frontend:** `npm run build`, deploy `dist/` to Netlify/Vercel/Railway static;
  set `VITE_API_URL=https://<your-backend>/api` before building.

## Author
[Your Name] - [Roll No.] - [College / Department] - GitHub: [repo link]
