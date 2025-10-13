import sys
import io
import os
import json
import re
from bs4 import BeautifulSoup

# Reconfigure stdout to ensure UTF-8 output
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def clean(content):
    """Clean text by stripping whitespace and fixing encoding errors."""
    if not content:
        return "Not available"
    if not isinstance(content, str):
        content = str(content.get_text(separator=" ", strip=True)) if hasattr(content, "get_text") else str(content)
    
    # This finds any bad characters and replaces them, ensuring valid UTF-8
    cleaned_content = content.encode('utf-8', 'replace').decode('utf-8')
    
    text = re.sub(r'[ \t]+', ' ', cleaned_content)
    text = re.sub(r'\n{3,}', '\n\n', text.strip())
    
    junk_phrases = ["Skip to main content", "See more", "...see more"]
    for phrase in junk_phrases:
        text = text.replace(phrase, "")
        
    return text.strip() if text.strip() else "Not available"

def _extract_detail_with_testid(soup, test_id):
    """Helper to find an element by its data-testid and get its value."""
    try:
        item = soup.select_one(f"li[data-testid='{test_id}']")
        if item:
            value_element = item.find_all(["div", "span"])[-1]
            return clean(value_element)
    except Exception:
        return "Not available"
    return "Not available"

def extract_company_data(input_html_path):
    """Main function to orchestrate Indeed company page extraction."""
    if not os.path.exists(input_html_path):
        return {"type": "indeed_company", "error": f"File not found at {input_html_path}"}

    with open(input_html_path, "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "lxml")

    try: company_name = clean(soup.select_one('div[itemprop="name"]'))
    except Exception: company_name = "Not available"

    try: logo_url = soup.select_one('div.css-19l789z img[itemprop="image"]')["src"]
    except Exception: logo_url = "Not available"

    about = "Not available"
    try:
        about_section = soup.select_one('section[data-testid="AboutSection-section"]')
        if about_section:
            description_container = about_section.select_one('div[data-testid="less-text"], div.css-1qewhxk')
            if description_container:
                about = clean(description_container)
    except Exception:
        pass

    details_section = soup.select_one('section[data-testid="AboutSection-section"]')
    if details_section:
        industry = _extract_detail_with_testid(details_section, "companyInfo-industry")
        company_size = _extract_detail_with_testid(details_section, "companyInfo-employee")
        headquarters = _extract_detail_with_testid(details_section, "companyInfo-headquartersLocation")
        founded = _extract_detail_with_testid(details_section, "companyInfo-founded")
    else:
        industry, company_size, headquarters, founded = ("Not available",) * 4

    try:
        website_element = soup.find('a', attrs={'data-testid': 'companyLink[]'})
        website = website_element['href'] if website_element else "Not available"
    except Exception:
        website = "Not available"
        
    data = {
        "type": "indeed_company",
        "company_name": company_name,
        "tagline": "Not available",
        "logo_url": logo_url,
        "follower_count": "Not available",
        "about": about,
        "website": website,
        "industry": industry,
        "company_size": company_size,
        "headquarters": headquarters,
        "founded": founded,
        "specialties": "Not available"
    }
    return data

if __name__ == "__main__":
    if len(sys.argv) > 1:
        html_file_path = sys.argv[1]
        company_data = extract_company_data(html_file_path)
        print(json.dumps(company_data, indent=2, ensure_ascii=False))
    else:
        error_data = {"error": "No URL provided to the Python script."}
        print(json.dumps(error_data, indent=2))