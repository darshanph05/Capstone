# Capstone Merged Project

Project includes 2 parts:
- Admin dashboard & survey builder
- Student survey flow (including link to participate)

## Run on Windows (PowerShell)

```powershell

python -m venv .venv

allow this as well: Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

.\.venv\Scripts\activate


python -m pip install --upgrade pip
python -m pip install -r requirements.txt

```

Then open:
- Admin: http://127.0.0.1:8001


## How to get survey's link from admin
1. Login admin page.
2. Open survey builder.
3. Press Publish.
4. System generates distributed link `/take-survey/<survey_id>` 

## Note
- Result of the survey stored in `survey_results.csv`.

