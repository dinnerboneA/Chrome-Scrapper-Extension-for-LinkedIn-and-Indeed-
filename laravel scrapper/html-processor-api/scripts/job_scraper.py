import sys
import io
import os
import json
import re
from bs4 import BeautifulSoup

# Reconfigure stdout to ensure UTF-8 output, solving encoding errors.
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def clean(content):
    """
    Cleans text by preserving line breaks, fixing encoding errors,
    and normalizing whitespace.
    """
    if not content:
        return "Not available"

    text = ""
    # If content is a BeautifulSoup tag, process it to preserve line breaks
    if hasattr(content, 'find_all'):
        # Convert <br> tags to a simple newline
        for br in content.find_all("br"):
            br.replace_with("\n")
        # Get text, using a newline as a separator for block tags like <p> and <div>
        text = content.get_text(separator="\n", strip=True)
    else:
        text = str(content)

    # Fix any potential encoding errors in the scraped text
    cleaned_content = text.encode('utf-8', 'replace').decode('utf-8')

    # --- THIS IS THE FIX ---
    # Replace multiple spaces and tabs, but keep the newlines
    text = re.sub(r'[ \t]+', ' ', cleaned_content)
    # Condense multiple newlines into a maximum of two (a paragraph break)
    text = re.sub(r'\n{3,}', '\n\n', text.strip())
    # --- END OF FIX ---

    # Remove common junk phrases
    junk_phrases = [
        "Skip to main content", "See more", "...see more"
    ]
    for phrase in junk_phrases:
        text = text.replace(phrase, "")
        
    return text.strip() if text.strip() else "Not available"



def extract_job_data(input_html_path):
    """
    Main function to orchestrate job posting extraction.
    Each field is wrapped in a try/except block for robustness.
    """
    if not os.path.exists(input_html_path):
        return {"type": "job", "error": f"File not found at {input_html_path}"}

    with open(input_html_path, "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "lxml")

    # --- Extract fields safely ---
    try:
        job_title = clean(soup.select_one("h1.t-24"))
    except Exception:
        job_title = "Not available"

    try:
        company_name = clean(soup.select_one(".job-details-jobs-unified-top-card__company-name a"))
    except Exception:
        company_name = "Not available"
        
    try:
        primary_desc_container = soup.select_one(".job-details-jobs-unified-top-card__primary-description-container")
        location = clean(primary_desc_container.select_one("span.tvm__text--low-emphasis")) if primary_desc_container else "Not available"
    except Exception:
        location = "Not available"

    try:
        tertiary_desc_container = soup.select_one(".job-details-jobs-unified-top-card__tertiary-description-container")
        date_posted = "Not available"
        applicants_count = "Not available"
        if tertiary_desc_container:
            date_posted_span = tertiary_desc_container.find("span", string=re.compile(r"ago|Posted", re.I))
            date_posted = clean(date_posted_span) if date_posted_span else "Not available"
            
            applicants_element = tertiary_desc_container.find("strong", string=re.compile(r"applicant|apply", re.I))
            applicants_count = clean(applicants_element) if applicants_element else "Not available"
    except Exception:
        date_posted = "Not available"
        applicants_count = "Not available"

    try:
        workplace_type = "Not available"
        employment_type = "Not available"
        detail_buttons = soup.select(".job-details-fit-level-preferences button strong")
        if len(detail_buttons) > 0:
            workplace_type = clean(detail_buttons[0])
        if len(detail_buttons) > 1:
            employment_type = clean(detail_buttons[1])
    except Exception:
        workplace_type = "Not available"
        employment_type = "Not available"

    try:
        description_element = soup.select_one("div#job-details")
        job_description = clean(description_element)
    except Exception:
        job_description = "Not available"

    experience_level = "Not available"
    
    data = {
        "type": "job",
        "job_title": job_title,
        "company_name": company_name,
        "location": location,
        "date_posted": date_posted,
        "workplace_type": workplace_type,
        "applicants_count": applicants_count,
        "employment_type": employment_type,
        "experience_level": experience_level,
        "job_description": job_description
    }
    return data

if __name__ == "__main__":
    if len(sys.argv) > 1:
        html_file_path = sys.argv[1]
        job_data = extract_job_data(html_file_path)
        print(json.dumps(job_data, indent=2, ensure_ascii=False))
    else:
        error_data = {"error": "No file path provided to the Python script."}
        print(json.dumps(error_data, indent=2))