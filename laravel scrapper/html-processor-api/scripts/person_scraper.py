import sys
import io

# --- ADD THIS BLOCK AT THE VERY TOP ---
# Reconfigure stdout to ensure UTF-8 output, solving encoding errors.
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
# --- END OF NEW BLOCK ---

import os
import json
import re
import difflib
from datetime import datetime
from bs4 import BeautifulSoup

# Utility functions


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

    text = re.sub(r'[ \t]+', ' ', cleaned_content)
    text = re.sub(r'\n{3,}', '\n\n', text.strip())

    # Remove common junk phrases
    junk_phrases = [
        "Skip to main content", "See more", "...see more"
    ]
    for phrase in junk_phrases:
        text = text.replace(phrase, "")
        
    return text.strip() if text.strip() else "Not available"


def parse_date_range(text):
    date_from, date_to, is_current = "Not available", "Not available", False
    full_date_pattern = r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})\s*[-–]\s*(Present|(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4})'
    full_match = re.search(full_date_pattern, text, re.IGNORECASE)
    if full_match:
        date_from = f"{full_match.group(1)} {full_match.group(2)}"
        if "present" in full_match.group(3).lower():
            date_to = "Present"
            is_current = True
        else:
            date_to = full_match.group(3).strip()
    else:
        year_pattern = r'(\d{4})\s*[-–]\s*(\d{4}|Present)'
        year_match = re.search(year_pattern, text, re.IGNORECASE)
        if year_match:
            date_from = year_match.group(1)
            date_to = year_match.group(2)
            if "present" in date_to.lower():
                is_current = True
    if not is_current and date_to != "Not available":
        try:
            date_to_obj = datetime.strptime(date_to, "%b %Y")
            if date_to_obj > datetime.now():
                is_current = True
        except ValueError:
            try:
                date_to_obj = datetime.strptime(date_to, "%Y")
                if date_to_obj.year > datetime.now().year:
                    is_current = True
            except ValueError:
                pass
    return date_from, date_to, is_current

def is_valid_job_entry(text, role):
    skills_indicators = ["skills", "+2 skills", "+3 skills", "+4 skills", "+5 skills", "and more", "show all", "see more"]
    text_lower = text.lower()
    for indicator in skills_indicators:
        if indicator in text_lower and len(text) < 150:
            return False
    has_date = re.search(r'\d{4}', text) or "present" in text_lower
    is_substantial = len(text) > 100
    if role != "Not available" and any(indicator in role.lower() for indicator in skills_indicators):
        return False
    return has_date or is_substantial

SIMILARITY_THRESHOLD = 0.90
def is_about_duplicate(about, experiences, educations, threshold=SIMILARITY_THRESHOLD):
    if not about or about == "Not available":
        return False
    def norm(s):
        return " ".join(str(s).lower().split())
    a = norm(about)
    def check_field(field_text):
        if not field_text or field_text == "Not available":
            return False
        f = norm(field_text)
        if not f:
            return False
        if a == f or a in f or f in a:
            return True
        ratio = difflib.SequenceMatcher(None, a, f).ratio()
        if ratio >= threshold:
            return True
        return False
    for e in experiences or []:
        for key in ("details", "company_name", "role", "company_location"):
            if key in e and check_field(e.get(key)):
                return True
    for ed in educations or []:
        for key in ("details", "degree", "institution_name", "institution_location"):
            if key in ed and check_field(ed.get(key)):
                return True
    return False


# Extraction functions

def extract_basic_info(soup):
    name = clean(soup.select_one("h1, .pv-text-details__left-panel h1"))
    headline = clean(soup.select_one(".text-body-medium, .pv-text-details__left-panel div"))
    location = clean(soup.select_one(".text-body-small.inline, .pv-top-card--list-panel li"))
    
    # This selector tries to find the main profile image.
    profile_pic_element = soup.select_one("img[class*='pv-top-card-profile-picture__image']")
    profile_pic_url = profile_pic_element['src'] if profile_pic_element else "Not available"
    
    cover_pic_element = soup.select_one("img.profile-background-image__image")
    cover_pic_url = cover_pic_element['src'] if cover_pic_element else "Not available"
    
    
    return name, headline, location, profile_pic_url, cover_pic_url






def extract_about(soup):
    """
    Finds the "About" section using its unique ID to avoid confusion
    with other sections like "Activity".
    """
    # 1. Find the unique anchor div with id="about". This is our reliable starting point.
    about_anchor = soup.find("div", id="about")
    if not about_anchor:
        return "Not available" # If this anchor doesn't exist, there is no About section.

    # 2. From the anchor, find the parent <section> tag that contains the entire "About" block.
    # This isolates our search to only this section.
    about_section = about_anchor.find_parent("section")
    if not about_section:
        return "Not available"

    # 3. Within this specific section, find the container with the actual text.
    # The text is typically inside a span with aria-hidden="true" to be visible.
    text_container = about_section.select_one("div.inline-show-more-text span[aria-hidden='true']")
    
    if text_container:
        text = text_container.get_text(separator=" ", strip=True)
        # Check for a reasonable length to ensure it's not just an empty span
        if len(text) > 20:
            return clean(text)

    # Fallback for a slightly different structure sometimes seen
    # (Looks for the text in a more generic div if the specific one isn't found)
    alt_container = about_section.select_one("div.display-flex.ph5.pv3 span[aria-hidden='true']")
    if alt_container:
        text = alt_container.get_text(separator=" ", strip=True)
        if len(text) > 20:
            return clean(text)

    # If neither of the precise methods work, return "Not available"
    return "Not available"






def extract_experience(soup):
    experiences = []
    seen = set()

    experience_anchor = soup.find("div", id="experience")
    if not experience_anchor:
        return []

    experience_section = experience_anchor.find_parent("section")
    if not experience_section:
        return []

    job_items = experience_section.select("ul > li.artdeco-list__item")

    for item in job_items:
        role_element = item.select_one("div.display-flex.mr1 span[aria-hidden='true']")
        role = clean(role_element) if role_element else "Not available"

        company_element = item.select_one("span.t-14.t-normal:not(.t-black--light) span[aria-hidden='true']")
        company_parts = clean(company_element).split('·')
        company_name = company_parts[0].strip() if company_parts else "Not available"
        job_type = company_parts[1].strip() if len(company_parts) > 1 else "Not available"

        sub_captions = item.select("span.t-14.t-normal.t-black--light span[aria-hidden='true']")
        date_text = clean(sub_captions[0]) if sub_captions else ""
        location = clean(sub_captions[1]) if len(sub_captions) > 1 else "Not available"

        date_from, date_to, is_current = parse_date_range(date_text)

        # --- DETAILS EXTRACTION ---
        details = "Not available"
        # First, try the specific selector that works for the "before" (collapsed) state.
        details_element = item.select_one("div[class*='inline-show-more-text'] span[aria-hidden='true']")
        if details_element:
            details = clean(details_element)
        else:
            # If that fails, it's likely the "after" (expanded) state.
            # We'll find all the text blocks in the sub-components and pick the longest one,
            # which is almost always the description.
            sub_components = item.select_one("div.pvs-entity__sub-components")
            if sub_components:
                potential_details = sub_components.find_all("span", {"aria-hidden": "true"})
                longest_text = ""
                for span in potential_details:
                    text = clean(span)
                    # Filter out short text and "skills" text
                    if len(text) > len(longest_text) and "skills" not in text.lower():
                        longest_text = text
                if longest_text:
                    details = longest_text


        identifier = (role, company_name, date_from)
        if role == "Not available" or company_name == "Not available" or identifier in seen:
            continue
        seen.add(identifier)

        experiences.append({
            "company_name": company_name,
            "company_location": location,
            "job_type": job_type,
            "role": role,
            "date_from": date_from,
            "date_to": date_to,
            "details": details,
            "is_current": is_current
        })

    return experiences


def extract_education(soup):
    educations, seen = [], set()
    edu_heading = soup.find(lambda tag: tag.name in ["h2", "h3", "div"] and "education" in tag.get_text(strip=True).lower() and len(tag.get_text(strip=True)) < 50)
    edu_section = edu_heading.find_parent(["section", "div"]) if edu_heading else soup.find("section", id="education")
    if not edu_section: return []
    main_ul = edu_section.find("ul")
    if not main_ul: return []
    edu_items = main_ul.find_all("li", recursive=False)
    for edu in edu_items:
        full_text = edu.get_text(separator=" ", strip=True)
        if len(full_text) < 50: continue
        institution, degree = "Not available", "Not available"
        aria_spans = edu.find_all("span", attrs={"aria-hidden": "true"})
        if aria_spans:
            institution = clean(aria_spans[0].get_text(strip=True))
        if len(aria_spans) > 1:
            degree_text = clean(aria_spans[1].get_text(strip=True))
            if any(keyword in degree_text for keyword in ['Bachelor', 'Master', 'Diploma', 'degree', 'Intermediate']):
                degree = degree_text
        date_from, date_to, is_current = parse_date_range(full_text)
        details_divs = edu.select("div[class*='inline-show-more-text'] span[aria-hidden='true']")
        details_list = [clean(div.get_text(separator=' ', strip=True)) for div in details_divs]
        details = ' '.join(details_list) if details_list else "Not available"
        identifier = (institution, degree, date_from)
        if identifier in seen or institution == "Not available": continue
        seen.add(identifier)
        educations.append({"institution_name": institution, "degree": degree, "date_from": date_from, "date_to": date_to, "details": details, "is_current": is_current})
    return educations


# Main Orchestration

def extract_profile(input_html_path):

    print(f"Python script started. Attempting to process file: {input_html_path}", file=sys.stderr)

    if not os.path.exists(input_html_path):

        print(f"Error: The file path does not exist on the server.", file=sys.stderr)
        return {"error": f"File not found at {input_html_path}"}

    with open(input_html_path, "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "lxml")
    
    name, headline, location, profile_pic_url, cover_pic_url = extract_basic_info(soup)

    about = extract_about(soup)
    experience = extract_experience(soup)
    education = extract_education(soup)

    if is_about_duplicate(about, experience, education, threshold=SIMILARITY_THRESHOLD):
        about = "Not available"

    data = {
        "type": "person", 
        "name": name,
        "headline": headline,
        "location": location,
        "profile_pic_url": profile_pic_url,
        "cover_pic_url": cover_pic_url,
        "about": about,
        "experience": experience,
        "education": education
    }
    
    print("Python script finished. Returning JSON data.", file=sys.stderr)
    return data

# Script Entry Point
if __name__ == "__main__":
    if len(sys.argv) > 1:
        html_file_path = sys.argv[1]
        profile_data = extract_profile(html_file_path)
        # Print the final dictionary as a JSON string to standard output
        print(json.dumps(profile_data, indent=2, ensure_ascii=False))
    else:
        # Print an error message if no file path is provided
        error_data = {"error": "No file path provided to the Python script."}
        print(json.dumps(error_data, indent=2))