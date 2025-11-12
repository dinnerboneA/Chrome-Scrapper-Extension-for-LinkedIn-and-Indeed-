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
        for br in content.find_all("br"):
            br.replace_with("\n")
        for p in content.find_all("p"):
            p.replace_with(f"\n\n{p.get_text(strip=True)}")
        text = content.get_text(separator="\n", strip=True)
    else:
        text = str(content)

    # Fix any potential encoding errors
    cleaned_content = text.encode('utf-8', 'replace').decode('utf-8')

    # Replace multiple spaces/tabs, but keep the newlines
    text = re.sub(r'[ \t]+', ' ', cleaned_content)
    # Condense multiple newlines into a maximum of two
    text = re.sub(r'\n{3,}', '\n\n', text.strip())
    
    junk_phrases = ["Skip to main content", "See more", "...see more", "Show more"]
    for phrase in junk_phrases:
        # Use a case-insensitive replace to catch variations
        text = re.sub(r'\b' + re.escape(phrase) + r'\b', '', text, flags=re.IGNORECASE)
        
    return text.strip() if text.strip() else "Not available"

def _extract_detail_with_testid(soup, test_id):
    """Helper to find an element by its data-testid and get its value."""
    try:
        item = soup.select_one(f"li[data-testid='{test_id}']")
        if item:
            # The value is usually in the last div or span inside the list item
            value_element = item.find_all(["div", "span"])[-1]
            return clean(value_element)
    except Exception:
        return "Not available"
    return "Not available"

def extract_company_data(input_html_path):
    """Main function to orchestrate Indeed company page extraction from a local HTML file."""
    if not os.path.exists(input_html_path):
        return {"type": "indeed_company", "error": f"File not found at {input_html_path}"}

    with open(input_html_path, "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "lxml")

    # --- Extract all fields safely ---
    try:
        company_name = clean(soup.select_one('div[itemprop="name"]'))
    except Exception:
        company_name = "Not available"

    try:
        logo_url = soup.select_one('div[data-testid="cmp-HeaderLayout-sticky"] img, div.css-9wofke img')['src']
    except Exception:
        logo_url = "Not available"

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
        if details_section:
            website_element = details_section.find('a', attrs={'data-testid': 'companyLink[]'})
            website = website_element['href'] if website_element else "Not available"
        else:
            website = "Not available"
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