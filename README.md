# Kalakriti — Local Artist & Handcraft Marketplace

Full-stack web application built according to the **System Architecture Flow** and **Flowchart** (Separate Frontend & Python Flask Backend with SQLite Database & Image Storage).

## Folder Structure
```text
local_artisan_handcraft_marketplace/
├── backend/
│   ├── app.py                  # Python Flask REST API + SQLite DB + Image Storage
│   ├── requirements.txt        # Python dependencies
│   └── static/uploads/         # Uploaded craft images
├── frontend/
│   ├── index.html              # Public Portal (Customer & Artisan Login/Register + Marketplace + Artisan Studio)
│   ├── admin.html              # Separate Admin Portal (Admin Login + Users, Products, Orders & Reports)
│   ├── css/style.css           # Responsive styling
│   └── js/
│       ├── app.js              # Customer & Artisan frontend logic
│       └── admin.js            # Admin dashboard frontend logic
└── README.md
```

## How to Run

### 1. Start the Backend (Python Flask)
```bash
cd backend
pip install -r requirements.txt
```

Set a unique initial admin password before starting the backend. In PowerShell:
```powershell
$env:KALAKRITI_ADMIN_PASSWORD = "replace-with-a-unique-password"
python app.py
```
Keep this password out of source control. The first run initializes the admin account (`admin@kalakriti.in`) and the SQLite database (`artisan_marketplace.db`) on `http://127.0.0.1:5000`. Sample artisan and customer accounts are seeded with random, undisclosed passwords; register a new public account to sign in as a customer or artisan.

### 2. Start the Frontend
Open `frontend/index.html` (Public Portal) or `frontend/admin.html` (Admin Portal) in your browser, or serve the `frontend/` folder with VS Code Live Server / `python -m http.server 8000`.
