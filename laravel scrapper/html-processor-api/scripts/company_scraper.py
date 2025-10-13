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




def _extract_detail_item(soup, heading_text):
    """Helper to find a heading in the details list and return the next sibling's text."""
    try:
        heading_element = soup.find("h3", string=re.compile(r'\s*' + re.escape(heading_text) + r'\s*', re.I))
        if heading_element:
            return clean(heading_element.find_parent('dt').find_next_sibling('dd'))
    except Exception:
        return "Not available"
    return "Not available"

def extract_company_data(input_html_path):
    """Main function to orchestrate company profile extraction from a local HTML file."""
    if not os.path.exists(input_html_path):
        return {"type": "company", "error": f"File not found at {input_html_path}"}

    with open(input_html_path, "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "lxml")

    # --- Extract all fields safely ---
    try:
        company_name = clean(soup.select_one("h1.org-top-card-summary__title"))
    except Exception:
        company_name = "Not available"
    
    try:
        tagline = clean(soup.select_one("p.org-top-card-summary__tagline"))
    except Exception:
        tagline = "Not available"

    try:
        logo_url = soup.select_one("img.org-top-card-primary-content__logo")['src']
    except Exception:
        logo_url = "Not available"

    try:
        follower_element = soup.find("div", class_="org-top-card-summary-info-list__info-item", string=re.compile(r'followers', re.I))
        follower_count = clean(follower_element)
    except Exception:
        follower_count = "Not available"

    cover_pic_url = "Not available"
    try:
        cover_img_tag = soup.select_one("img.pic-cropper__target-image")
        if cover_img_tag and cover_img_tag.has_attr('src'):
            cover_pic_url = cover_img_tag['src']
        else:
            cover_div_tag = soup.select_one("div.org-cropped-image__cover-image")
            if cover_div_tag and cover_div_tag.has_attr('style'):
                match = re.search(r'url\("?(.+?)"?\)', cover_div_tag['style'])
                if match:
                    cover_pic_url = match.group(1)
    except Exception:
        pass

    overview_section = soup.find("h2", string=re.compile("Overview", re.I))
    about_container = overview_section.find_parent("section") if overview_section else soup
    
    about = clean(about_container.select_one("p.break-words"))
    website = _extract_detail_item(about_container, "Website")
    industry = _extract_detail_item(about_container, "Industry")
    company_size = _extract_detail_item(about_container, "Company size")
    headquarters = _extract_detail_item(about_container, "Headquarters")
    founded = _extract_detail_item(about_container, "Founded")
    specialties = _extract_detail_item(about_container, "Specialties")

    data = {
        "type": "company",
        "company_name": company_name,
        "tagline": tagline,
        "logo_url": logo_url,
        "cover_pic_url": cover_pic_url,
        "follower_count": follower_count,
        "about": about,
        "website": website,
        "industry": industry,
        "company_size": company_size,
        "headquarters": headquarters,
        "founded": founded,
        "specialties": specialties
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