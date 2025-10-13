import sys
import io
import os
import json
import re
from bs4 import BeautifulSoup

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
        # Get text, using a newline as a separator for block tags like <p> and <li>
        text = content.get_text(separator="\n", strip=True)
    else:
        text = str(content)

    # Fix any potential encoding errors in the scraped text
    cleaned_content = text.encode('utf-8', 'replace').decode('utf-8')

    # Replace multiple spaces and tabs, but keep the newlines
    text = re.sub(r'[ \t]+', ' ', cleaned_content)
    # Condense multiple newlines into a maximum of two (a paragraph break)
    text = re.sub(r'\n{3,}', '\n\n', text.strip())
    
    # Remove common junk phrases
    junk_phrases = ["Skip to main content", "See more", "...see more"]
    for phrase in junk_phrases:
        text = text.replace(phrase, "")
        
    return text.strip() if text.strip() else "Not available"

def extract_job_data(input_html_path):
    if not os.path.exists(input_html_path):
        return {"type": "indeed_job", "error": f"File not found at {input_html_path}"}

    with open(input_html_path, "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "lxml")

    try:
        job_title = clean(soup.select_one("h1.jobsearch-JobInfoHeader-title"))
    except Exception:
        job_title = "Not available"

    try:
        company_name = clean(soup.select_one('div[data-company-name="true"] a'))
    except Exception:
        company_name = "Not available"

    try:
        location = clean(soup.select_one('div[data-testid="inlineHeader-companyLocation"]'))
    except Exception:
        location = "Not available"
        
    try:
        salary_info_div = soup.select_one("div#salaryInfoAndJobType")
        salary = clean(salary_info_div.select_one("span:first-child")) if salary_info_div else "Not available"
        job_type = clean(salary_info_div.select_one("span:last-child")) if salary_info_div else "Not available"
        # Clean up the job type string which might have " - "
        if job_type:
            job_type = job_type.replace('-', '').strip()
    except Exception:
        salary = "Not available"
        job_type = "Not available"

    try:
        job_description = clean(soup.select_one("div#jobDescriptionText"))
    except Exception:
        job_description = "Not available"

    data = {
        "type": "indeed_job",
        "job_title": job_title,
        "company_name": company_name,
        "location": location,
        "salary": salary,
        "job_type": job_type,
        "date_posted": "Not available", # This info wasn't in the provided HTML
        "applicants_count": "Not available", # This info isn't on Indeed
        "experience_level": "Not available", # This info isn't in a consistent spot
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