from fastapi import FastAPI, File, UploadFile, Depends, HTTPException, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload
import os

# Import for running sync functions in a threadpool
from starlette.concurrency import run_in_threadpool

# Import local modules
import services
from db import (
    get_db, create_db_and_tables, Candidate, Skill, 
    Company, College, Degree, Experience, Certification
)

app = FastAPI()

# --- Startup Event ---
@app.on_event("startup")
def on_startup():
    """Runs when the app starts. Creates DB tables."""
    print("Starting up and creating database tables if they don't exist...")
    create_db_and_tables()
    print("Startup complete.")

# --- API Endpoints ---

@app.post("/recreate-db/")
def do_recreate_db():
    """
    Drops all tables and recreates them.
    WARNING: This will delete all existing data.
    """
    recreate_db_and_tables()
    return {"message": "Database tables recreated successfully."}

@app.post("/upload-resumes/")
async def upload_resumes(files: List[UploadFile] = File(...), db: Session = Depends(get_db)):
    """
    Handles uploading multiple resume files, processing them,
    and storing the extracted data in the database.
    """
    processed_files = []
    errors = []
    
    for file in files:
        if not file.filename:
            continue

        print(f"Processing file: {file.filename}")
        
        # 1. Await the ASYNC text extraction
        resume_text = await services.extract_text_from_file(file)
        if not resume_text:
            errors.append(f"Could not extract text from {file.filename} (is it empty or unsupported?)")
            continue

        # 2. Run the SYNC (blocking) LangChain call in a threadpool
        try:
            json_data = await run_in_threadpool(services.get_data_from_gemini, resume_text)
        except Exception as e:
             errors.append(f"LangChain/Gemini call failed for {file.filename}: {str(e)}")
             continue # Go to next file

        if not json_data:
            errors.append(f"Could not parse data from {file.filename} (LLM returned no data)")
            continue

        # 3. Run the SYNC (blocking) database insert in a threadpool
        try:
            await run_in_threadpool(services.insert_json_data_into_db, json_data, db)
            processed_files.append(file.filename)
        except Exception as e:
            # The service function re-raises the error, so we catch it here.
            errors.append(f"Error inserting data for {file.filename}: {str(e)}")

    return {
        "message": f"Processing complete.",
        "processed_files": processed_files,
        "errors": errors
    }





@app.get("/api/candidates/table")
def get_candidates_table(db: Session = Depends(get_db)):
    """Fetches candidate data formatted for a simple table view."""
    
    candidates = db.query(Candidate).options(
        joinedload(Candidate.skills),
        joinedload(Candidate.certifications),  # <-- ADD THIS LINE
        joinedload(Candidate.experiences).joinedload(Experience.company),
        joinedload(Candidate.degrees).joinedload(Degree.college)
    ).all()
    
    result = []
    for c in candidates:
        result.append({
            "id": c.id,
            "name": c.name,
            "email": c.email,
            "phone": c.phone,                    # <-- Already here
            "linkedin": c.linkedin_url,
            "total_exp": c.total_experience_years,
            "city": c.city, 
            "skills": [s.name for s in c.skills],
            "certifications": [cert.name for cert in c.certifications], # <-- ADD THIS LINE
            "companies": [exp.company.name for exp in c.experiences if exp.company],
            "colleges": [deg.college.name for deg in c.degrees if deg.college],
        })
    return result


@app.get("/api/candidate/{candidate_id}")
def get_candidate_detail(candidate_id: int, db: Session = Depends(get_db)):
    """Fetches the full, detailed data for a single candidate."""
    
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
    """Fetches unique values for filters."""
    skills = [s[0] for s in db.query(Skill.name).distinct().all()]
    cities = [c[0] for c in db.query(Candidate.city).distinct().all() if c[0] is not None]
    return {"skills": skills, "cities": cities}

@app.get("/api/analytics")
def get_analytics(db: Session = Depends(get_db)):
    """Fetches aggregated data for the analytics dashboard."""
    return services.get_analytics_data(db)



# --- HTML Partial Serving ---
# Add these routes BEFORE the static file mounting

@app.get("/dashboard.html")
async def get_dashboard():
    file_path = os.path.join(frontend_dir, "dashboard.html")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="dashboard.html not found.")
    return FileResponse(file_path)

@app.get("/candidates.html")
async def get_candidates():
    file_path = os.path.join(frontend_dir, "candidates.html")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="candidates.html not found.")
    return FileResponse(file_path)

@app.get("/upload.html")
async def get_upload():
    file_path = os.path.join(frontend_dir, "upload.html")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="upload.html not found.")
    return FileResponse(file_path)

@app.get("/candidate-detail.html")
async def get_candidate_detail_html():
    file_path = os.path.join(frontend_dir, "candidate-detail.html")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="candidate-detail.html not found.")
    return FileResponse(file_path)

# --- Static File Serving ---
# (This existing code comes AFTER the new routes above)

# --- Static File Serving ---
base_dir = os.path.dirname(os.path.abspath(__file__))
frontend_dir = os.path.join(base_dir, "..", "frontend")

if not os.path.exists(frontend_dir):
    print(f"Error: Frontend directory not found at {frontend_dir}")
    print("Please ensure the 'frontend' and 'backend' directories are siblings.")

app.mount("/js", StaticFiles(directory=os.path.join(frontend_dir, "js")), name="js")
app.mount("/css", StaticFiles(directory=os.path.join(frontend_dir, "css")), name="css")

@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    file_path = os.path.join(frontend_dir, "index.html")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="index.html not found.")
    return FileResponse(file_path)

@app.get("/")
async def get_index():
    file_path = os.path.join(frontend_dir, "index.html")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="index.html not found.")
    return FileResponse(file_path)