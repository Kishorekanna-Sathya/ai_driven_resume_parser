import os
import json
import google.generativeai as genai

# --- Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY is None:
    raise EnvironmentError("GEMINI_API_KEY not set in .env file")
genai.configure(api_key=GEMINI_API_KEY)

def get_structured_data(resume_text: str) -> dict | None:
    """
    Sends text to the configured LLM and gets structured JSON data back.
    """
    if not resume_text or len(resume_text) < 50:
        print("Resume text is too short, skipping LLM call.")
        return None

    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
    Parse the following resume text and extract the information as a valid JSON object.
    Only output the JSON object, nothing else. Use "null" for any missing fields.
    Ensure "total_experience_years" is a number (float or int).
    Ensure "passed_out_year" and "total_years" (in experience) are numbers (int or float).
    Ensure "skills" has only technical skills
    Ensure "city" has only city name, if no city then state, else null.


    The JSON object must follow this exact structure:
    {{
      "name": "string or null",
      "email": "string or null",
      "phone": "string or null",
      "linkedin_url": "string or null",
      "total_experience_years": "number or null",
      "city": "string or null",
      "degrees": [
        {{
          "college_name": "string",
          "degree_name": "string or null",
          "passed_out_year": "integer or null"
        }}
      ],
      "experience": [
        {{
          "company_name": "string",
          "total_years": "number or null",
          "role": "string",
          "description": "string or null"
        }}
      ],
      "skills": ["string", "string", ...],
      "certifications": ["string", "string", ...]
    }}

    Here is the resume text:
    ---
    {resume_text}
    ---
    """
    
    try:
        response = model.generate_content(prompt)
        # More robust JSON extraction
        text_response = response.text
        first_brace = text_response.find('{')
        last_brace = text_response.rfind('}')
        if first_brace == -1 or last_brace == -1:
            print(f"Warning: Could not find a JSON object in the LLM response.")
            return None
        json_text = text_response[first_brace:last_brace+1]
        parsed_data = json.loads(json_text)
        return parsed_data
        
    except Exception as e:
        print(f"Error parsing with LLM: {e}")
        print(f"LLM raw response: {response.text if 'response' in locals() else 'N/A'}")
        return None
