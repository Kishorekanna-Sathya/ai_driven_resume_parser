from fastapi import FastAPI, File, UploadFile, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload
from starlette.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

import os
import shutil
from typing import List
from pathlib import Path

import services
from db import (
    get_db, create_db_and_tables, recreate_db_and_tables,
    Candidate, Skill, Company, College, Degree, Experience, Certification
)

# ---------------------------------------------------------
# App Initialization
# ---------------------------------------------------------

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_FOLDER = "uploaded_resumes"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

base_dir = os.path.dirname(os.path.abspath(__file__))
frontend_dir = os.path.join(base_dir, "..", "frontend")

if not os.path.exists(frontend_dir):
    print(f"Frontend directory not found at: {frontend_dir}")

# ---------------------------------------------------------
# Startup
# ---------------------------------------------------------

@app.on_event("startup")
def on_startup():
    print("Creating tables if missing...")
    create_db_and_tables()

# ---------------------------------------------------------
# DATABASE & PROCESSING ENDPOINTS (MUST COME FIRST)
# ---------------------------------------------------------

@app.post("/recreate-db/")
def do_recreate_db():
    recreate_db_and_tables()
    return {"message": "Database recreated."}


@app.post("/upload-resumes/")
async def upload_resumes(files: List[UploadFile] = File(...), db: Session = Depends(get_db)):
    processed_files = []
    errors = []

    for file in files:
        if not file.filename:
            continue

        print(f"Processing file: {file.filename}")

        # 1. Save temp file
        temp_path = os.path.join(UPLOAD_FOLDER, f"temp_{file.filename}")
        try:
            with open(temp_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            await file.seek(0)
        except Exception as e:
            errors.append(f"Could not save {file.filename}: {e}")
            continue

        # 2. Extract text
        resume_text = await services.extract_text_from_file(file)
        if not resume_text:
            errors.append(f"Could not extract text from {file.filename}")
            os.remove(temp_path)
            continue

        # 3. Parse with LLM (threadpool)
        try:
            json_data = await run_in_threadpool(services.get_data_from_gemini, resume_text)
        except Exception as e:
            errors.append(f"Gemini parse error on {file.filename}: {e}")
            os.remove(temp_path)
            continue

        if not json_data:
            errors.append(f"No parsed data for {file.filename}")
            os.remove(temp_path)
            continue

        # 4. Insert into DB (threadpool)
        try:
            candidate_id = await run_in_threadpool(
                services.insert_json_data_into_db, json_data, db
            )

            final_path = os.path.join(
                UPLOAD_FOLDER, f"candidate_{candidate_id}{os.path.splitext(file.filename)[1]}"
            )

            if os.path.exists(final_path):
                os.remove(final_path)

            os.rename(temp_path, final_path)
            processed_files.append(file.filename)

        except Exception as e:
            errors.append(f"DB insert error for {file.filename}: {e}")
            os.remove(temp_path)

    return {
        "message": "Processing complete.",
        "processed_files": processed_files,
        "errors": errors
    }


# ---------------------------------------------------------
# API ENDPOINTS
# ---------------------------------------------------------

@app.get("/api/candidates/table")
def get_candidates_table(db: Session = Depends(get_db)):
    candidates = db.query(Candidate).options(
        joinedload(Candidate.skills),
        joinedload(Candidate.certifications),
        joinedload(Candidate.experiences).joinedload(Experience.company),
        joinedload(Candidate.degrees).joinedload(Degree.college)
    ).all()

    result = []
    for c in candidates:
        result.append({
            "id": c.id,
            "name": c.name,
            "email": c.email,
            "phone": c.phone,
            "linkedin": c.linkedin_url,
            "total_exp": c.total_experience_years,
            "city": c.city,
            "skills": [s.name for s in c.skills],
            "certifications": [cert.name for cert in c.certifications],
            "companies": [exp.company.name for exp in c.experiences if exp.company],
            "colleges": [deg.college.name for deg in c.degrees if deg.college],
        })
    return result


@app.get("/api/candidate/{candidate_id}")
def get_candidate_detail(candidate_id: int, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).options(
        joinedload(Candidate.skills),
        joinedload(Candidate.certifications),
        joinedload(Candidate.experiences).joinedload(Experience.company),
        joinedload(Candidate.degrees).joinedload(Degree.college)
    ).filter(Candidate.id == candidate_id).first()

    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    return {
        "id": candidate.id,
        "name": candidate.name,
        "email": candidate.email,
        "phone": candidate.phone,
        "linkedin_url": candidate.linkedin_url,
        "total_experience_years": candidate.total_experience_years,
        "city": candidate.city,
        "skills": [s.name for s in candidate.skills],
        "certifications": [c.name for c in candidate.certifications],
        "degrees": [{
            "college_name": d.college.name if d.college else 'N/A',
            "degree_name": d.degree_name,
            "passed_out_year": d.passed_out_year
        } for d in candidate.degrees],
        "experiences": [{
            "company_name": e.company.name if e.company else 'N/A',
            "total_years": e.total_years,
            "role": e.role,
            "description": e.description
        } for e in candidate.experiences]
    }


@app.get("/api/filters")
def get_filters(db: Session = Depends(get_db)):
    skills = [s[0] for s in db.query(Skill.name).distinct().all()]
    cities = [c[0] for c in db.query(Candidate.city).distinct().all() if c[0]]
    return {"skills": skills, "cities": cities}


@app.get("/api/analytics")
def get_analytics(db: Session = Depends(get_db)):
    return services.get_analytics_data(db)


@app.get("/api/test-data")
def test_data(db: Session = Depends(get_db)):
    candidates = db.query(Candidate).all()
    return {
        "total_candidates": len(candidates),
        "candidate_names": [c.name for c in candidates],
    }


# ---------------------------------------------------------
# ✅ Resume file serving (MUST be BEFORE catch-all)
# ---------------------------------------------------------

@app.get("/api/resume/{candidate_id}")
async def get_resume_file(candidate_id: int):
    print(f"Looking for resume for candidate {candidate_id}")

    for ext in [".pdf", ".docx"]:
        file_path = os.path.join(UPLOAD_FOLDER, f"candidate_{candidate_id}{ext}")

        print("Checking:", file_path, "Exists:", os.path.exists(file_path))

        if os.path.exists(file_path):
            media_type = (
                "application/pdf"
                if ext == ".pdf"
                else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )

            return FileResponse(
                file_path,
                media_type=media_type,
                filename=f"resume_{candidate_id}{ext}"
            )

    raise HTTPException(status_code=404, detail="Resume file not found")


# ---------------------------------------------------------
# HTML PARTIAL ROUTES (BEFORE STATIC)
# ---------------------------------------------------------

@app.get("/dashboard.html")
async def get_dashboard():
    return FileResponse(os.path.join(frontend_dir, "dashboard.html"))


@app.get("/candidates.html")
async def get_candidates_html():
    return FileResponse(os.path.join(frontend_dir, "candidates.html"))


@app.get("/upload.html")
async def get_upload_html():
    return FileResponse(os.path.join(frontend_dir, "upload.html"))


@app.get("/candidate-detail.html")
async def get_candidate_detail_html():
    return FileResponse(os.path.join(frontend_dir, "candidate-detail.html"))


# ---------------------------------------------------------
# Static files
# ---------------------------------------------------------

class NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        resp = await super().get_response(path, scope)
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp

app.mount("/js", NoCacheStaticFiles(directory=os.path.join(frontend_dir, "js")), name="js")
app.mount("/css", NoCacheStaticFiles(directory=os.path.join(frontend_dir, "css")), name="css")


# ---------------------------------------------------------
# ✅ Catch-all route MUST be last
# ---------------------------------------------------------

@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    return FileResponse(os.path.join(frontend_dir, "index.html"))


@app.get("/")
async def get_index():
    return FileResponse(os.path.join(frontend_dir, "index.html"))
