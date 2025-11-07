import os
import json
import pandas as pd
import mimetypes
from io import BytesIO
from docx import Document
from PyPDF2 import PdfReader
from sqlalchemy.orm import Session
from typing import List, Optional

# --- LangChain Imports ---
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

# DB imports
from db import (
    Candidate, Skill, Company, College, Degree, Experience, Certification
)

# --- Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY is None:
    raise EnvironmentError("GEMINI_API_KEY not set in .env file")
# Note: We will now pass this key manually

# --- 1. Pydantic Models for Structured Output ---
# (Unchanged)
class DegreeModel(BaseModel):
    college_name: str = Field(description="Name of the college or university")
    degree_name: Optional[str] = Field(description="The name of the degree (e.g., B.S. in Computer Science)")
    passed_out_year: Optional[int] = Field(description="Year of graduation")

class ExperienceModel(BaseModel):
    company_name: str = Field(description="Name of the company")
    total_years: Optional[float] = Field(description="Duration in years at this company")
    role: str = Field(description="Job title or role")
    description: Optional[str] = Field(description="Brief description of responsibilities")

class ResumeModel(BaseModel):
    name: Optional[str] = Field(description="Candidate's full name")
    email: Optional[str] = Field(description="Candidate's email address")
    phone: Optional[str] = Field(description="Candidate's phone number")
    linkedin_url: Optional[str] = Field(description="URL to the candidate's LinkedIn profile")
    total_experience_years: Optional[float] = Field(description="Total years of professional experience")
    city: Optional[str] = Field(description="Candidate's city and state (e.g., San Francisco, CA)")
    degrees: List[DegreeModel] = Field(description="List of educational degrees")
    experience: List[ExperienceModel] = Field(description="List of professional work experiences")
    skills: List[str] = Field(description="List of technical skills")
    certifications: List[str] = Field(description="List of certifications")


# --- 2. Text Extraction (Async) ---
# (Unchanged)
async def extract_text_from_file(file):
    """Extracts raw text from an uploaded file (PDF or DOCX only)."""
    filename = file.filename
    file_bytes = await file.read() # Use await as this is async
    
    mime_type, _ = mimetypes.guess_type(filename)
    
    text = ""
    try:
        if mime_type == 'application/pdf':
            reader = PdfReader(BytesIO(file_bytes))
            for page in reader.pages:
                text += page.extract_text()
            if not text:
                print(f"File {filename} is image-based or has no text. Skipping.")
                return None
                
        elif mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' or mime_type == 'application/msword':
            if mime_type == 'application/msword':
                 print(f"Warning: .doc file ({filename}) is not supported, only .docx. Skipping.")
                 return None
            doc = Document(BytesIO(file_bytes))
            for para in doc.paragraphs:
                text += para.text + "\n"
                
        else:
            print(f"Unsupported file type for {filename}: {mime_type}. Skipping.")
            return None

    except Exception as e:
        print(f"Error extracting text from {filename}: {e}")
        return None
        
    return text

# --- 3. LangChain LLM Parsing (Sync) ---

# In backend/services.py

def get_data_from_gemini(resume_text: str):
    """Sends text to Gemini via LangChain and gets structured JSON data back."""
    
    if not resume_text or len(resume_text) < 50:
        print("Resume text is too short, skipping.")
        return None

    try:
        # Initialize the LLM
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash", 
            api_key=os.getenv("GEMINI_API_KEY")
        )

        # Initialize the Pydantic JSON parser
        parser = JsonOutputParser(pydantic_object=ResumeModel)

        # --- UPDATED PROMPT ---
        # This prompt is much stricter to improve quality.
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", """
                You are an expert resume parsing assistant. You must extract all information and format it as a JSON object.
                Follow these rules VERY strictly:
                1.  **skills**: List *only* key technical skills (programming languages, frameworks, libraries, databases, tools).
                    -   **DO NOT** include "soft skills" like 'Time management', 'Communication', 'Anger management', etc.
                    -   **DO NOT** include general concepts like 'Programming', 'Problem solving', 'Creativity', etc.
                2.  **linkedin_url**: Must be a valid URL (e.g., `https://www.linkedin.com/in/...`). If not found, use `null`.
                3.  **certifications**: List *only* the names of official certifications (e.g., 'AWS Certified Cloud Practitioner').
                    -   **DO NOT** list the issuing organization (like 'The Sparks Foundation') here.
                4.  **total_experience_years**: Must be a single float number (e.g., `3.5` or `0`). If not found, use `null`.
                5.  **city**: Must be *only* the city and state (e.g., "San Francisco, CA"). Do not include the full address. If not found, use `null`.
                6.  Use `null` for any field you cannot find.

            {format_instructions}
            """),
            ("human", "Here is the resume text:\n\n{resume_text}")
        ])
        # --- END OF UPDATED PROMPT ---

        # Create the processing chain
        chain = prompt_template | llm | parser

        # Invoke the chain
        parsed_data = chain.invoke({
            "resume_text": resume_text,
            "format_instructions": parser.get_format_instructions()
        })
        
        return parsed_data
        
    except Exception as e:
        print(f"Error parsing with LangChain/Gemini: {e}")
        return None



def get_or_create_no_commit(db: Session, model, **kwargs):
    """
    Utility to get an instance if it exists, or create it and add to session.
    Does NOT commit.
    """
    for obj in db.new:
        if isinstance(obj, model) and all(getattr(obj, k) == v for k, v in kwargs.items()):
            return obj
    
    instance = db.query(model).filter_by(**kwargs).first()
    if instance:
        return instance
    
    instance = model(**kwargs)
    db.add(instance)
    return instance


def get_analytics_data(db: Session):
    """Fetches aggregated data for the analytics dashboard."""
    # Skill Distribution
    skills = db.query(Skill.name).all()
    skill_counts = pd.Series([s[0] for s in skills]).value_counts().to_dict()

    # Experience Distribution
    candidates = db.query(Candidate.total_experience_years).all()
    exp_years = [c[0] for c in candidates if c[0] is not None]
    bins = [0, 2, 5, 10, 50] # 0-2, 2-5, 5-10, 10+
    labels = ['0-2 years', '2-5 years', '5-10 years', '10+ years']
    exp_distribution = pd.cut(exp_years, bins=bins, labels=labels, right=False).value_counts().to_dict()

    return {
        "skill_distribution": skill_counts,
        "experience_distribution": exp_distribution
    }
    """
    Inserts the nested JSON data into the normalized database
    as a single, atomic transaction.
    """
    try:
        if not json_data.get('name'):
            raise ValueError("Name is required to create or update a candidate.")

        candidate = db.query(Candidate).filter(Candidate.name == json_data['name']).first()
        if not candidate:
            candidate = Candidate(name=json_data['name'])
            db.add(candidate)
        
        # Update candidate fields
        candidate.email = json_data.get('email')
        candidate.phone = json_data.get('phone')
        candidate.linkedin_url = json_data.get('linkedin_url')
        candidate.total_experience_years = json_data.get('total_experience_years')
        candidate.city = json_data.get('city')
        
        # Clear old relationships
        candidate.skills.clear()
        candidate.certifications.clear()
        db.query(Degree).filter(Degree.candidate_id == candidate.id).delete(synchronize_session=False)
        db.query(Experience).filter(Experience.candidate_id == candidate.id).delete(synchronize_session=False)

        # Link Skills
        skills_to_add = []
        for skill_name in json_data.get('skills', []):
            if skill_name:
                skill = get_or_create_no_commit(db, Skill, name=skill_name.strip())
                skills_to_add.append(skill)
        candidate.skills = list(set(skills_to_add))

        # Link Certifications
        certs_to_add = []
        for cert_name in json_data.get('certifications', []):
            if cert_name:
                cert = get_or_create_no_commit(db, Certification, name=cert_name.strip())
                certs_to_add.append(cert)
        candidate.certifications = list(set(certs_to_add))

        # Add Degrees
        for degree_data in json_data.get('degrees', []):
            if degree_data and degree_data.get('college_name'):
                college = get_or_create_no_commit(db, College, name=degree_data['college_name'].strip())
                degree = Degree(
                    candidate=candidate,
                    college=college,
                    degree_name=degree_data.get('degree_name'),
                    passed_out_year=degree_data.get('passed_out_year')
                )
                db.add(degree)

        # Add Experiences
        for exp_data in json_data.get('experience', []):
            if exp_data and exp_data.get('company_name'):
                company = get_or_create_no_commit(db, Company, name=exp_data['company_name'].strip())
                exp = Experience(
                    candidate=candidate,
                    company=company,
                    total_years=exp_data.get('total_years'),
                    role=exp_data.get('role'),
                    description=exp_data.get('description')
                )
                db.add(exp)
        
        # --- Single Commit ---
        db.commit()
        print(f"Successfully inserted or updated data for candidate: {json_data.get('name')}")

    except Exception as e:
        db.rollback()
        print(f"Database error for {json_data.get('name')}. Transaction rolled back. Error: {e}")
        raise e