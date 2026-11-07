# ResourceFlow — Building Resource Management System

A full-stack demo application for monitoring simulated water and electricity availability across multiple buildings. It uses HTML/CSS/JavaScript, Flask, SQLite and Chart.js.

## Features

- Admin login
- Five sample buildings
- Water and electricity readings
- Simulated readings generated every 10 seconds while the dashboard is open
- Admin-configurable minimum thresholds for each building and resource
- Dashboard cards, status indicators and historical line graph
- Low-resource alert history
- Email notification through SMTP when a threshold is crossed
- SQLite database created automatically on first run

> **Important demo detail:** Both water and electricity are modeled as *available levels* in this demo. Electricity is shown in kWh of available supply, not as a live utility meter reading or energy-consumption calculation. The simulation is not connected to physical sensors.

## 1. Requirements

- Python 3.9 or newer
- Internet connection for the Chart.js CDN and Google Fonts (the application itself runs locally)
- A modern browser

SQLite is included with Python. You do not need MySQL, MySQL Workbench, or a separate database server.

## 2. Run the application

Open a terminal in this project folder.

### Windows (PowerShell)

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

If PowerShell blocks activation, use Command Prompt:

```bat
py -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
python app.py
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Open this address in your browser:

```text
http://127.0.0.1:5000
```

### Demo login

- Username: `admin`
- Password: `admin123`

Change these values using environment variables before exposing the app to a network.

## 3. Email alert configuration (optional)

The application still records alerts without email configuration. In that case, the terminal prints a message explaining that SMTP is not configured.

To send real email, configure these environment variables before starting Flask:

- `SMTP_HOST`
- `SMTP_PORT` (usually `587` for STARTTLS)
- `SMTP_USER`
- `SMTP_PASSWORD`
- `ALERT_FROM`
- `ALERT_TO`

For example, in Windows PowerShell:

```powershell
$env:SMTP_HOST="smtp.gmail.com"
$env:SMTP_PORT="587"
$env:SMTP_USER="your-sender@gmail.com"
$env:SMTP_PASSWORD="your-app-password"
$env:ALERT_FROM="your-sender@gmail.com"
$env:ALERT_TO="admin-recipient@gmail.com"
python app.py
```

For Gmail, use an **App Password** where available; do not put your normal Gmail password in the code. Keep credentials private and do not commit them to Git. SMTP email sending requires an account/provider that permits SMTP access.

The backend avoids repeatedly emailing for the same building/resource: it creates at most one alert per 15-minute window while that resource remains below its threshold. A new alert can be generated after that window.

## 4. Project structure

```text
resource_management_system/
├── app.py
├── alerts.py
├── requirements.txt
├── README.md
├── .gitignore
├── templates/
│   ├── login.html
│   ├── dashboard.html
│   └── settings.html
└── static/
    ├── css/
    │   └── style.css
    └── js/
        ├── dashboard.js
        └── settings.js
```

The `resource_management.db` SQLite database is created automatically in the project folder when the app starts.

## 5. How it works

1. The dashboard calls `POST /api/simulate` every 10 seconds while it is open.
2. Flask generates a simulated reading for each building and resource.
3. Each reading is stored in SQLite.
4. The backend compares the new reading with that building/resource's admin threshold.
5. If it is below the threshold, the backend records an alert and attempts to send an email.
6. The dashboard refreshes the cards, graph and alert list.

The dashboard must remain open for the browser-driven simulation to continue. For a production system, move simulation/sensor polling into a dedicated background worker or scheduled service.

## 6. Main API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/overview` | Latest reading and threshold for each building |
| POST | `/api/simulate` | Generate and save simulated readings |
| GET | `/api/history` | Recent history for a building/resource |
| GET | `/api/limits` | Read all admin thresholds |
| POST | `/api/limits` | Update a threshold |
| GET | `/api/alerts` | Read recent alerts |
| GET | `/api/buildings` | List buildings |

All API endpoints require an authenticated admin session.

## 7. Customization

- Edit the `BUILDINGS` list in `app.py` to change sample buildings.
- Edit `RESOURCE_CONFIG` in `app.py` to change capacities, units and default thresholds.
- The admin can also change thresholds from the **Admin settings** page.
- Delete `resource_management.db` while the app is stopped if you want to recreate the database with fresh sample data.

## 8. Before real-world deployment

This is a college/demo starter project, not a production-ready building control system. Before deployment:
- Replace demo credentials and `SECRET_KEY` with strong secrets.
- Use HTTPS and secure cookie settings.
- Add CSRF protection and stronger user management.
- Run Flask behind a production WSGI server; do not use Flask's debug server.
- Move periodic monitoring out of the browser and into a background worker.
- Connect validated IoT sensor or meter data rather than simulated values.
- Secure SMTP credentials and restrict access to the admin dashboard.
