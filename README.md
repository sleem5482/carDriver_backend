# Driver Trip Tracking & Control System

FastAPI backend with PostgreSQL for tracking driver trips, managing vehicles, and providing admin oversight.

## Quick Start

```bash
# 1. Activate virtual environment
.\venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
# Edit .env with your PostgreSQL and Cloudinary credentials

# 4. Seed the database (creates admin user)
python -m app.seed

# 5. Run the server
uvicorn app.main:app --reload

# 6. Open API docs
# http://127.0.0.1:8000/docs
```

## API Overview

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/login` | Login with phone + password → JWT |

### Admin Dashboard
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/admin/users/` | List all users |
| POST | `/admin/users/` | Create user (with vehicle assignment) |
| GET | `/admin/users/{id}` | Get user details + available vehicles |
| PUT | `/admin/users/{id}` | Update user + re-assign vehicle |
| DELETE | `/admin/users/{id}` | Delete user |
| GET | `/admin/vehicles/` | List all vehicles |
| POST | `/admin/vehicles/` | Create vehicle |
| PUT | `/admin/vehicles/{id}` | Update vehicle |
| DELETE | `/admin/vehicles/{id}` | Delete vehicle |
| GET | `/admin/trips/` | List trips (with filters) |
| GET | `/admin/trips/{id}` | Trip detail view |
| GET | `/admin/audit-logs/` | View audit trail |

### Driver Mobile App
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/driver/status` | Driver info + active trip status |
| POST | `/driver/trip/start` | Start trip (multipart with odometer image) |
| POST | `/driver/trip/end` | End trip (multipart with odometer image) |

## Default Admin Credentials
- **Phone:** `+201000000000`
- **Password:** `admin123`
