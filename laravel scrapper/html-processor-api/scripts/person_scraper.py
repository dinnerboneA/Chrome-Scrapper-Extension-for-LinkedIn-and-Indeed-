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





# --- NEW: Function to determine highest education level ---
def get_highest_education_level(education_list):
    """
    Analyzes a list of education entries and returns the slug for the highest level.
    e.g., 'bachelor', 'master', 'phd'
    """
    if not education_list:
        return "Not available"

    # Define the hierarchy and keywords for each level.
    # The key is the value your <SelectItem> expects in React.
    hierarchy = {
        'phd': {'rank': 5, 'keywords': ['phd', 'doctorate', 'd.phil']},
        'master': {'rank': 4, 'keywords': ['master', 'm.sc', 'm.a.', 'mba', 'meng']},
        'bachelor': {'rank': 3, 'keywords': ["bachelor", "b.sc", "b.a.", "beng", "llb", "bachelor of science"]},
        'associate': {'rank': 2, 'keywords': ['associate', 'diploma']},
        'high_school': {'rank': 1, 'keywords': ['high school', 'a-level', 'foundation']}
    }

    highest_rank = 0
    highest_level_slug = "Not available"

    for edu_item in education_list:
        degree_text = edu_item.get('degree', '').lower()
        if not degree_text:
            continue
        
        for slug, data in hierarchy.items():
            if any(keyword in degree_text for keyword in data['keywords']):
                if data['rank'] > highest_rank:
                    highest_rank = data['rank']
                    highest_level_slug = slug
    
    return highest_level_slug
# --- END OF NEW FUNCTION ---

# Utility functions (Unchanged)
def clean(content):
    if not content:
        return "Not available"
    text = ""
    if hasattr(content, 'find_all'):
        for br in content.find_all("br"):
            br.replace_with("\n")
        # --- MODIFICATION: Added <li> and <p> to preserve formatting ---
        for tag in content.find_all(["p", "li"]):
            tag.replace_with(f"\n{tag.get_text(strip=True)}")
        text = content.get_text(separator="\n", strip=True)
        # --- END OF MODIFICATION ---
    else:
        text = str(content)
    cleaned_content = text.encode('utf-8', 'replace').decode('utf-8')
    text = re.sub(r'[ \t]+', ' ', cleaned_content)
    text = re.sub(r'\n{3,}', '\n\n', text.strip())
    junk_phrases = ["Skip to main content", "See more", "...see more"]
    for phrase in junk_phrases:
        text = re.sub(r'\b' + re.escape(phrase) + r'\b', '', text, flags=re.IGNORECASE)
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

# Extraction functions (Unchanged)
def extract_basic_info(soup):
    name = clean(soup.select_one("h1, .pv-text-details__left-panel h1"))
    headline = clean(soup.select_one(".text-body-medium, .pv-text-details__left-panel div"))
    location = clean(soup.select_one(".text-body-small.inline, .pv-top-card--list-panel li"))
    profile_pic_element = soup.select_one("img[class*='pv-top-card-profile-picture__image']")
    profile_pic_url = profile_pic_element['src'] if profile_pic_element else "Not available"
    cover_pic_element = soup.select_one("img.profile-background-image__image")
    cover_pic_url = cover_pic_element['src'] if cover_pic_element else "Not available"
    return name, headline, location, profile_pic_url, cover_pic_url

def extract_about(soup):
    about_anchor = soup.find("div", id="about")
    if not about_anchor:
        return "Not available"
    about_section = about_anchor.find_parent("section")
    if not about_section:
        return "Not available"
    text_container = about_section.select_one("div.inline-show-more-text span[aria-hidden='true']")
    if text_container:
        text = text_container.get_text(separator=" ", strip=True)
        if len(text) > 20:
            return clean(text_container)
    alt_container = about_section.select_one("div.display-flex.ph5.pv3 span[aria-hidden='true']")
    if alt_container:
        text = alt_container.get_text(separator=" ", strip=True)
        if len(text) > 20:
            return clean(alt_container)
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
        details = "Not available"
        details_element = item.select_one("div[class*='inline-show-more-text'] span[aria-hidden='true']")
        if details_element:
            details = clean(details_element)
        else:
            sub_components = item.select_one("div.pvs-entity__sub-components")
            if sub_components:
                potential_details = sub_components.find_all("span", {"aria-hidden": "true"})
                longest_text = ""
                for span in potential_details:
                    text = clean(span)
                    if len(text) > len(longest_text) and "skills" not in text.lower():
                        longest_text = text
                if longest_text:
                    details = longest_text
        identifier = (role, company_name, date_from)
        if role == "Not available" or company_name == "Not available" or identifier in seen:
            continue
        seen.add(identifier)
        experiences.append({ "company_name": company_name, "company_location": location, "job_type": job_type, "role": role, "date_from": date_from, "date_to": date_to, "details": details, "is_current": is_current })
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

# --- NEW FUNCTION: Extract Skills ---
def extract_skills(soup):
    """
    Extracts the list of skills from the profile.
    """
    skills = []
    try:
        skills_anchor = soup.find("div", id="skills")
        if not skills_anchor:
            return []
        
        skills_section = skills_anchor.find_parent("section")
        if not skills_section:
            return []
            
        skill_elements = skills_section.select("a[data-field='skill_card_skill_topic'] span[aria-hidden='true']")
        for el in skill_elements:
            skill_name = clean(el)
            if skill_name != "Not available":
                skills.append(skill_name)
    except Exception:
        pass # Return empty list if any error occurs
    return skills
# --- END OF NEW FUNCTION ---

# --- NEW FUNCTION: Extract Languages ---
def extract_languages(soup):
    """
    Extracts the list of languages and their proficiency.
    """
    languages = []
    try:
        languages_anchor = soup.find("div", id="languages")
        if not languages_anchor:
            return []

        languages_section = languages_anchor.find_parent("section")
        if not languages_section:
            return []

        lang_items = languages_section.select("ul > li")
        for item in lang_items:
            name_el = item.select_one("div.t-bold span[aria-hidden='true']")
            prof_el = item.select_one("span.pvs-entity__caption-wrapper[aria-hidden='true']")
            
            name = clean(name_el)
            proficiency = clean(prof_el)
            
            if name != "Not available":
                languages.append({"language": name, "proficiency": proficiency})
    except Exception:
        pass
    return languages
# --- END OF NEW FUNCTION ---

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
    
    # --- MODIFICATION: Call new functions ---
    skills = extract_skills(soup)
    languages = extract_languages(soup)
    
    if is_about_duplicate(about, experience, education, threshold=SIMILARITY_THRESHOLD):
        about = "Not available"

    highest_education = get_highest_education_level(education)

    data = {
        "type": "person", 
        "name": name,
        "headline": headline,
        "location": location,
        "profile_pic_url": profile_pic_url,
        "cover_pic_url": cover_pic_url,
        "about": about,
        "experience": experience,
        "education": education,
        "highest_education_level": highest_education,
        # --- MODIFICATION: Add new data to the final JSON ---
        "skills": skills,
        "languages": languages
    }
    
    print("Python script finished. Returning JSON data.", file=sys.stderr)
    return data

# Script Entry Point (Unchanged)
if __name__ == "__main__":
    if len(sys.argv) > 1:
        html_file_path = sys.argv[1]
        profile_data = extract_profile(html_file_path)
        print(json.dumps(profile_data, indent=2, ensure_ascii=False))
    else:
        error_data = {"error": "No file path provided to the Python script."}
        print(json.dumps(error_data, indent=2))