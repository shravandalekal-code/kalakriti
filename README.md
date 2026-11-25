# Kalakriti — Local Artist & Handcraft Marketplace

Full-stack web application built according to the **System Architecture Flow** and **Flowchart** (Separate Frontend & Python Flask Backend with SQLite locally and PostgreSQL for hosted deployments).

## Folder Structure
```text
local_artisan_handcraft_marketplace/
├── backend/
│   ├── app.py                  # Python Flask REST API + SQLite DB + Image Storage
│   ├── requirements.txt        # Python dependencies
│   ├── wsgi.py                 # Production WSGI entry point
│   └── static/uploads/         # Uploaded craft images
├── frontend/
│   ├── index.html              # Public Portal (Customer & Artisan Login/Register + Marketplace + Artisan Studio)
│   ├── admin.html              # Separate Admin Portal (Admin Login + Users, Products, Orders & Reports)
│   ├── css/style.css           # Responsive styling
│   └── js/
│       ├── config.js           # Frontend API URL configuration
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
Keep this password out of source control. Without `DATABASE_URL`, the first run initializes the admin account (`admin@kalakriti.in`) and the SQLite database (`artisan_marketplace.db`) on `http://127.0.0.1:5000`. Register a new public account to sign in as a customer or artisan.

### 2. Start the Frontend
Open `frontend/index.html` (Public Portal) or `frontend/admin.html` (Admin Portal) in your browser, or serve the `frontend/` folder with VS Code Live Server / `python -m http.server 8000`.

## Deploy on Render

The backend and frontend deploy as separate Render services.

### Backend Web Service
1. Create a Web Service from the `shravandalekal-code/kalakriti` GitHub repository and select the `main` branch.
2. Set **Root Directory** to `backend`.
3. Use **Build Command** `pip install -r requirements.txt`.
4. Use **Start Command** `gunicorn wsgi:app --workers 1 --bind 0.0.0.0:$PORT`.
5. Create a [Neon](https://console.neon.tech/signup) project on its Free plan. Neon currently lists a $0 plan with no credit card required, including 1 GB of storage and 100 compute-hours per month per project. Check its current limits before production use.
6. Copy the pooled PostgreSQL connection string from the Neon dashboard. In the Render service's Environment settings, set:
   - `KALAKRITI_ADMIN_PASSWORD`: a strong password for the initial admin account.
   - `DATABASE_URL`: the Neon pooled connection string (keep it secret; do not put it in GitHub).
   - `BACKEND_PUBLIC_URL`: the backend service's HTTPS URL, such as `https://kalakriti-api.onrender.com`.
   - `CORS_ORIGINS`: the frontend service's HTTPS URL, set after creating the frontend service.
   - `CLOUDINARY_URL` (optional): the Cloudinary connection URL from the Cloudinary console (keep it secret; do not put it in GitHub). Without it, uploaded image bytes are stored in the configured PostgreSQL database.
7. Deploy the backend. On first startup, it creates the PostgreSQL tables and initializes the admin account if the database is empty. On Render, the backend refuses to start without `DATABASE_URL` rather than silently saving accounts to temporary SQLite storage. Local development continues to use SQLite when `DATABASE_URL` is unset.

### Frontend Static Site
1. Create a Static Site from the same repository and select the `main` branch.
2. Set **Root Directory** to `frontend` and **Publish Directory** to `.`. No build step is required.
3. After the backend service is deployed, change `frontend/js/config.js` to use its API URL, for example:
   ```js
   window.KALAKRITI_API_BASE = "https://kalakriti-api.onrender.com/api";
   ```
4. Commit and push that change, then wait for the static site to redeploy.
5. Set the backend's `CORS_ORIGINS` environment variable to the frontend service's HTTPS URL and redeploy the backend.

The hosted database is PostgreSQL on Neon; Render's ordinary filesystem is not persistent across redeployments. Uploaded product images are stored in Cloudinary when `CLOUDINARY_URL` is configured, or in PostgreSQL when it is not, so Cloudinary is optional for hosted uploads. Local development without Cloudinary continues to store uploads under `UPLOAD_FOLDER`. Existing `/uploads/...` image URLs whose files disappeared from Render must be re-uploaded or replaced with hosted image URLs. Switching to Neon creates a new, empty database; it does not recover or copy user records already lost from Render's temporary SQLite database. Back up or import any recoverable data before switching databases.
