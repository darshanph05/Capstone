# Capstone Backend - FastAPI Project

The backend service is built with FastAPI, uses PostgreSQL as the database (running via Docker), and implements JWT Authentication for user verification.


------------------------------------------------------------------------

# 📌 Prerequisites

To run project, you need to install:

-   **Python 3.8+**
-   **Docker**
-   **Docker Compose**

------------------------------------------------------------------------

# 🐳 Install Docker 

### Windows / macOS

1.  Download **Docker Desktop**\
    https://www.docker.com/products/docker-desktop/

2.  Install with the guidance

3.  Open **Docker Desktop** and wait for the status:

```{=html}
<!-- -->
```
    Engine Running

4.  If Window requires, install **WSL2**.

------------------------------------------------------------------------

### Linux

Do by the guidance below:

https://docs.docker.com/engine/install/

------------------------------------------------------------------------

# 🏗 Project Structure

Project is organised by **FastAPI** structure.

    Capstone-Backend
    │
    ├── app/
    │   ├── models/        # SQLAlchemy Models (Database Tables)
    │   │   └── user.py
    │   │
    │   ├── routers/       # API Endpoints
    │   │   └── auth.py
    │   │
    │   ├── schemas/       # Pydantic Schemas (Request / Response validation)
    │   │   └── auth.py
    │   │
    │   ├── services/      # Business logic & Security
    │   │   └── auth.py
    │   │
    │   ├── database.py    # Database connection config
    │   └── main.py        # FastAPI entry point
    │
    ├── .env               # Environment variables
    ├── .gitignore
    ├── docker-compose.yml # PostgreSQL container
    ├── requirements.txt
    └── README.md

------------------------------------------------------------------------

# 🚀 Run Project

## 1️⃣ Create Virtual Environment

Open terminal in project folder.

``` bash
python -m venv venv
```

------------------------------------------------------------------------

## 2️⃣ Activate virtual environment

### Windows

``` bash
.\venv\Scripts\activate
```

### macOS / Linux

``` bash
source venv/bin/activate
```

------------------------------------------------------------------------

## 3️⃣ Install dependencies

``` bash
pip install -r requirements.txt
```

------------------------------------------------------------------------

# ⚙️ Environment Variables

Create file `.env` within root project:

    APP_NAME="Capstone Backend"
    APP_ENV=development
    PORT=8000

    # Database
    DATABASE_URL=postgresql://postgres:postgres@localhost:5432/capstone
    POSTGRES_USER=postgres
    POSTGRES_PASSWORD=postgres
    POSTGRES_DB=capstone

    # Authentication
    SECRET_KEY=yoursecretkey_please_change_this_in_production
    ALGORITHM=HS256
    ACCESS_TOKEN_EXPIRE_MINUTES=30

    # Cloudflare R2
    CLOUDFLARE_R2_ENDPOINT=https://your_account_id.r2.cloudflarestorage.com
    CLOUDFLARE_R2_ACCESS_KEY_ID=your_r2_access_key_id
    CLOUDFLARE_R2_SECRET_ACCESS_KEY=your_r2_secret_access_key
    CLOUDFLARE_R2_BUCKET_NAME=your_bucket_name
    # Optional: Public domain (custom domain or r2.dev domain) to return public URLs
    CLOUDFLARE_R2_PUBLIC_URL=https://your-public-r2-domain
    # Optional: default 10MB
    CLOUDFLARE_R2_MAX_FILE_SIZE_BYTES=10485760

    # Backward compatibility (optional): you can still use old keys R2_*

------------------------------------------------------------------------

# 🐘 Start PostgreSQL (Docker)

Run database by Docker:

``` bash
docker-compose up -d
```

If you change password within `.env`, please reset volume:

``` bash
docker-compose down -v
docker-compose up -d
```

If container **capstone_db** displays `Started`, database runs successfully.

------------------------------------------------------------------------

# ▶️ Start FastAPI Server

Run server:

``` bash
uvicorn app.main:app --reload
```

Server will runs in:

    http://127.0.0.1:8000

FastAPI automatically creates tables:

-   users
-   roles
-   surveys
-   questions
-   question_options
-   question_config
-   participants
-   attempts
-   answers

------------------------------------------------------------------------

# 🗄 Init Role Data (Important)

System requires **The role must already exist before a user can be registered**.

Connect to PostgreSQL by:

-   **HeidiSQL**
-   **DBeaver**
-   **DataGrip**

Information connected:

    Host: localhost
    Port: 5432
    Database: capstone
    User: postgres
    Password: postgres

Runs SQL:

``` sql
INSERT INTO roles (name, code, created_at)
VALUES ('Researcher', 'RESEARCHER', NOW());


```

------------------------------------------------------------------------

# 📖 API Documentation

After server runs, access:

### Swagger UI

http://127.0.0.1:8000/docs

### ReDoc

http://127.0.0.1:8000/redoc

------------------------------------------------------------------------

# 🔑 Test Flow

Test API:

    Register
       ↓
    Login
       ↓
    Get Current User (/me)
       ↓
    Upload File (/upload/file)

------------------------------------------------------------------------

# ☁️ Upload API (Cloudflare R2)

Endpoint upload requires **Bearer Token**.

## Upload any file

POST `/upload/file`

Form Data

    file: binary file

Query Params

    folder: uploads (optional)

Response

``` json
{
  "filename": "example.pdf",
  "key": "uploads/abc123...pdf",
  "url": "https://your-public-r2-domain/uploads/abc123...pdf",
  "content_type": "application/pdf",
  "size": 12345
}
```

## Upload image only

POST `/upload/image`

Form Data

    file: binary image

Query Params

    folder: images (optional)

------------------------------------------------------------------------

# 🧑‍💻 Tech Stack

-   FastAPI
-   SQLAlchemy
-   PostgreSQL
-   Docker
-   JWT Authentication
-   Pydantic
