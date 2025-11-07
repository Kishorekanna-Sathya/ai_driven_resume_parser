# AI-Powered Resume Parser & Visualization Hub

This is a full-stack application that parses .pdf and .docx resumes, extracts structured data using **LangChain with a Gemini LLM**, stores it in a PostgreSQL database, and visualizes the results.

## Tech Stack

-   **Backend:** FastAPI (Python)
-   **LLM Framework:** LangChain
-   **AI Service:** Google Gemini (via `langchain-google-genai`) 
-   **API Model:** gemini-2.5-flash
-   **Data Processing:** Pandas
-   **Frontend:** Vanilla JavaScript (SPA-style)
-   **Data Visualization:** D3.js
-   **Database:** PostgreSQL
-   **Python Libs:** SQLAlchemy, Pydantic, PyPDF2, python-docx

## Project Structure
resume_parser_project/
│   README.md
│
├───backend
│       .env.example
│       app.py
│       db.py
│       requirements.txt
│       services.py
│
└───frontend
    │   candidates.html
    │   index.html
    │   README.md
    │   upload.html
    │
    ├───css
    │       style.css
    │
    └───js
            main.js
