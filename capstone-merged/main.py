from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from urllib.parse import urlparse
import uvicorn
import json
import uuid
import time
import datetime
import csv
import os

load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

ADMIN_TEMPLATE_FILES = {
    "admin_login.html",
    "admin_home.html",
    "admin_mysurveys.html",
    "admin_surveybuilder.html",
    "admin_distributions.html",
    "admin_dataanalysis.html",
    "admin_results.html"
}

session_db = {}
surveys_db = {}

survey_configs = {
    "default": {
        "allow_school_change": False,
        "default_school": "Ambience Partner School",
        "time_limit_minutes": 30,
        "optional_questions": [1, 11],
        "correct_angles": {
            "0": 45, "1": 45, "2": 67, "3": 90, "4": 120,
            "5": 166, "6": 35, "7": 110, "8": 180, "9": 10
        }
    }
}

CSV_FILENAME = "survey_results.csv"

HEADERS = [
    "Session_ID", "Start_Timestamp", "Consent", "Full_Name", "DOB", "Grade", "School",
    "Total_Elapsed_Sec", "Spatial_Time_Remaining", "MR_Time_Remaining"
]

for i in range(1, 10):
    HEADERS.extend([f"Q{i}_Angle", f"Q{i}_CorrectAngle", f"Q{i}_Deviance"])

for i in range(11, 21):
    HEADERS.append(f"Q{i}_Selections")

for i in range(21, 26):
    HEADERS.append(f"Q{i}_Feedback")

for i in range(26, 31):
    HEADERS.append(f"Q{i}_YN")


def format_time_remaining(time_spent_sec, time_limit_minutes=30):
    if time_spent_sec == "empty":
        return "empty"
    remaining_sec = max(0, (time_limit_minutes * 60) - time_spent_sec)
    mins = int(remaining_sec // 60)
    secs = int(remaining_sec % 60)
    return f"{mins:02d}:{secs:02d}"


def update_csv_record(session_id):
    session = session_db.get(session_id)
    if not session:
        return

    info = session.get("student_info", {})
    row = {
        "Session_ID": session_id,
        "Start_Timestamp": session.get("start_date_str", "empty"),
        "Consent": info.get("consent", "empty"),
        "Full_Name": info.get("full_name", "empty"),
        "DOB": info.get("dob", "empty"),
        "Grade": info.get("grade", "empty"),
        "School": info.get("school", "empty"),
        "Total_Elapsed_Sec": session.get("total_elapsed_seconds", "empty"),
        "Spatial_Time_Remaining": format_time_remaining(session.get("spatial_total_sec", "empty")),
        "MR_Time_Remaining": format_time_remaining(session.get("mr_total_sec", "empty"))
    }

    for i in range(1, 10):
        ans = session.get(f"q_{i}_answer")
        if not ans or ans == "empty":
            row[f"Q{i}_Angle"] = "empty"
            row[f"Q{i}_CorrectAngle"] = "empty"
            row[f"Q{i}_Deviance"] = "empty"
        else:
            row[f"Q{i}_Angle"] = ans.get("angle", "empty")
            row[f"Q{i}_CorrectAngle"] = ans.get("correct_angle", "empty")
            row[f"Q{i}_Deviance"] = ans.get("angle_of_deviance", "empty")

    for i in range(11, 21):
        ans = session.get(f"q_{i}_answer")
        if not ans or ans == "empty":
            row[f"Q{i}_Selections"] = "empty"
        else:
            choices = ans.get("choices", [])
            row[f"Q{i}_Selections"] = ",".join(map(str, choices)) if choices else "empty"

    for i in range(21, 26):
        ans = session.get(f"q_{i}_answer")
        if not ans or ans == "empty":
            row[f"Q{i}_Feedback"] = "empty"
        else:
            row[f"Q{i}_Feedback"] = ans.get("text", "empty")

    for i in range(26, 31):
        ans = session.get(f"q_{i}_answer")
        if not ans or ans == "empty":
            row[f"Q{i}_YN"] = "empty"
        else:
            row[f"Q{i}_YN"] = ans.get("choice", "empty")

    rows = []
    if os.path.isfile(CSV_FILENAME):
        with open(CSV_FILENAME, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

    updated = False
    for idx, r in enumerate(rows):
        if r["Session_ID"] == session_id:
            rows[idx] = row
            updated = True
            break

    if not updated:
        rows.append(row)

    with open(CSV_FILENAME, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(rows)


# --- ADMIN ROUTES ---


def render_admin(request: Request, page_name: str):
    return templates.TemplateResponse(
        request=request,
        name=f"admin/{page_name}",
        context={"request": request}
    )


def render_survey(request: Request, page_name: str, context: dict | None = None):
    data = {"request": request}
    if context:
        data.update(context)
    return templates.TemplateResponse(
        request=request,
        name=f"survey/{page_name}",
        context=data
    )

@app.get("/", response_class=HTMLResponse)
async def landing_page(request: Request):
    return render_admin(request, "admin_login.html")


@app.get("/admin", response_class=HTMLResponse)
async def admin_landing(request: Request):
    return render_admin(request, "admin_login.html")


@app.get("/take/{token}")
async def take_survey_by_token(token: str):
    return RedirectResponse(url=f"/survey/{token}", status_code=303)


@app.get("/survey/consent", response_class=HTMLResponse)
async def survey_consent_page(request: Request):
    return render_survey(request, "consent.html")


@app.get("/survey/student-details", response_class=HTMLResponse)
async def survey_student_details_page(request: Request):
    return render_survey(request, "student_details.html")


@app.get("/survey/instructions", response_class=HTMLResponse)
async def survey_instructions_page(request: Request):
    return render_survey(request, "instructions.html")


@app.get("/survey/questions", response_class=HTMLResponse)
async def survey_questions_page(request: Request):
    return render_survey(request, "next_question.html")


@app.get("/survey/submitted", response_class=HTMLResponse)
async def survey_submitted_page(request: Request):
    return render_survey(request, "submitted.html")


@app.get("/survey/{token}", response_class=HTMLResponse)
async def survey_entry_by_token(request: Request, token: str):
    return render_survey(request, "consent.html")


@app.get("/{page_name}.html", response_class=HTMLResponse)
async def admin_html_page(request: Request, page_name: str):
    file_name = f"{page_name}.html"
    if file_name not in ADMIN_TEMPLATE_FILES:
        return RedirectResponse(url="/admin_login.html", status_code=303)
    return render_admin(request, file_name)


@app.get("/dashboard.css")
async def dashboard_css():
    return FileResponse("static/dashboard.css")


@app.get("/bootstrap.css")
async def bootstrap_css():
    return FileResponse("static/bootstrap.css")


@app.get("/app-config.js")
async def app_config_js(request: Request):
    configured_api_base = (os.getenv("FRONTEND_API_BASE_URL", "") or "").strip()
    request_host = (request.url.hostname or "").strip()
    request_scheme = (request.url.scheme or "http").strip()
    loopback_hosts = {"localhost", "127.0.0.1"}

    api_base_url = configured_api_base
    if configured_api_base:
        parsed = urlparse(configured_api_base)
        configured_host = (parsed.hostname or "").strip()
        configured_port = parsed.port or 8000

        # If FE is opened via non-loopback host but API base is loopback,
        # switch to current host to avoid browser private network blocking.
        if configured_host in loopback_hosts and request_host and request_host not in loopback_hosts:
            api_base_url = f"{request_scheme}://{request_host}:{configured_port}"
    else:
        fallback_host = request_host or "127.0.0.1"
        api_base_url = f"{request_scheme}://{fallback_host}:8000"

    allowed_roles_raw = os.getenv("FRONTEND_ADMIN_ALLOWED_ROLES", "ADMIN")
    allowed_roles = [r.strip().upper() for r in allowed_roles_raw.split(",") if r.strip()]
    payload = {
        "apiBaseUrl": api_base_url,
        "adminAllowedRoles": allowed_roles or ["ADMIN"],
    }
    script = f"window.APP_CONFIG = {json.dumps(payload)};"
    return Response(content=script, media_type="application/javascript")


@app.post("/api/publish_survey")
async def publish_survey(request: Request):
    data = await request.json()
    survey_id = str(uuid.uuid4())[:8]
    surveys_db[survey_id] = data
    base_url = str(request.base_url).rstrip("/")
    return JSONResponse(
        content={
            "status": "success",
            "survey_id": survey_id,
            "link": f"{base_url}/take-survey/{survey_id}"
        }
    )


@app.post("/api/save_survey")
async def save_survey(request: Request):
    data = await request.json()
    survey_id = str(uuid.uuid4())[:8]
    surveys_db[survey_id] = data
    base_url = str(request.base_url).rstrip("/")
    return JSONResponse(
        content={
            "status": "success",
            "survey_id": survey_id,
            "link": f"{base_url}/take-survey/{survey_id}"
        }
    )


# --- STUDENT SURVEY FLOW ---

@app.get("/take-survey/{survey_id}")
async def take_survey(request: Request, survey_id: str):
    session_id = str(uuid.uuid4())
    session_db[session_id] = {
        "max_q": 0,
        "current_q": 0,
        "survey_id": survey_id,
        "start_time_unix": time.time(),
        "start_date_str": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    return RedirectResponse(url=f"/consent/{session_id}", status_code=303)


@app.get("/consent/{session_id}", response_class=HTMLResponse)
async def consent_page(request: Request, session_id: str):
    return render_survey(request, "consent.html", {"session_id": session_id})


@app.get("/student-details/{session_id}", response_class=HTMLResponse)
async def student_details_page(request: Request, session_id: str, consent_given: str = None):
    if session_id in session_db:
        if "student_info" not in session_db[session_id]:
            session_db[session_id]["student_info"] = {}
        if consent_given:
            session_db[session_id]["student_info"]["consent"] = consent_given

        update_csv_record(session_id)

    config = survey_configs["default"]
    return render_survey(request, "student_details.html", {
        "session_id": session_id,
        "allow_school_change": config["allow_school_change"],
        "default_school": config["default_school"]
    })


@app.post("/submit-details/")
async def submit_details(
    session_id: str = Form(...),
    full_name: str = Form(...),
    dob: str = Form(...),
    grade: str = Form(...),
    school: str = Form(None)
):
    if session_id not in session_db:
        session_db[session_id] = {"max_q": 0, "student_info": {}}

    session_db[session_id]["student_info"].update({
        "full_name": full_name,
        "dob": dob,
        "grade": grade,
        "school": school
    })
    update_csv_record(session_id)

    return RedirectResponse(url=f"/instructions/{session_id}", status_code=303)


@app.get("/instructions/{session_id}", response_class=HTMLResponse)
async def instructions(request: Request, session_id: str):
    return render_survey(request, "instructions.html", {"session_id": session_id})


@app.get("/question/{session_id}/{q_id}", response_class=HTMLResponse)
async def get_question(request: Request, session_id: str, q_id: int):
    if session_id not in session_db:
        session_db[session_id] = {"max_q": 0}

    max_progress = session_db[session_id].get("max_q", 0)
    if q_id > max_progress:
        return RedirectResponse(url=f"/question/{session_id}/{max_progress}", status_code=303)

    if q_id == 0 and "spatial_start" not in session_db[session_id]:
        session_db[session_id]["spatial_start"] = time.time()
    elif q_id == 11 and "mr_start" not in session_db[session_id]:
        session_db[session_id]["mr_start"] = time.time()

    saved_image = session_db[session_id].get("uploaded_image", "")
    saved_answer = session_db[session_id].get(f"q_{q_id}_answer", None)

    config = survey_configs["default"]
    is_optional = q_id in config.get("optional_questions", [])
    correct_angle = config.get("correct_angles", {}).get(str(q_id), 0)

    return render_survey(request, "next_question.html", {
        "session_id": session_id,
        "q_id": q_id,
        "saved_image": saved_image,
        "saved_answer": json.dumps(saved_answer) if saved_answer else "null",
        "is_optional": is_optional,
        "correct_angle": correct_angle,
        "time_to_send": 0,
        "timer_state": "running"
    })


@app.post("/submit_answer/")
async def submit_answer(
    session_id: str = Form(...),
    q_id: int = Form(...),
    answer_data: str = Form(...),
    image_data: str = Form(None)
):
    if session_id not in session_db:
        session_db[session_id] = {"max_q": 0}

    if answer_data == '"empty"':
        session_db[session_id][f"q_{q_id}_answer"] = "empty"
    else:
        session_db[session_id][f"q_{q_id}_answer"] = json.loads(answer_data) if answer_data else None

    if image_data:
        session_db[session_id]["uploaded_image"] = image_data

    if q_id == 9 and "spatial_start" in session_db[session_id]:
        session_db[session_id]["spatial_total_sec"] = round(
            time.time() - session_db[session_id]["spatial_start"], 2
        )
    elif q_id == 20 and "mr_start" in session_db[session_id]:
        session_db[session_id]["mr_total_sec"] = round(
            time.time() - session_db[session_id]["mr_start"], 2
        )

    current_max = session_db[session_id].get("max_q", 0)
    if q_id == current_max:
        session_db[session_id]["max_q"] = q_id + 1

    update_csv_record(session_id)

    if q_id == 30:
        return RedirectResponse(url=f"/finish_survey/{session_id}", status_code=303)

    next_q = q_id + 1
    return RedirectResponse(url=f"/question/{session_id}/{next_q}", status_code=303)


@app.get("/finish_survey/{session_id}", response_class=HTMLResponse)
async def finish_survey(request: Request, session_id: str):
    if session_id in session_db:
        session = session_db[session_id]
        session["complete"] = True

        end_time = time.time()
        session["finish_time_unix"] = end_time
        session["finish_date_str"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if "start_time_unix" in session:
            session["total_elapsed_seconds"] = round(end_time - session["start_time_unix"], 2)

        update_csv_record(session_id)

    return render_survey(request, "submitted.html")


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
