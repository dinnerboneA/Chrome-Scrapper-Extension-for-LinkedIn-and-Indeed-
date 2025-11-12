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

# --- NEW: Helper function to find a section by its <h2> title ---
def find_section(soup, title_text):
    """Finds a section card by its <h2> title."""
    try:
        heading = soup.find("h2", string=lambda t: t and title_text.lower() in t.lower())
        if heading:
            # Find the closest parent <section> tag
            return heading.find_parent("section")
    except Exception:
        return None
    return None

# --- NEW: Function to determine highest education level ---
def get_highest_education_level(education_list):
    """
    Analyzes a list of education entries and returns the slug for the highest level.
    e.g., 'bachelor', 'master', 'phd'
    """
    if not education_list:
        return "Not available"
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

# --- Utility functions (Your existing versions) ---
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
    # --- THIS IS THE FIX ---
    junk_phrases = ["Skip to main content", "See more", "...see more", "… more"]
    for phrase in junk_phrases:
        # Use simple replace instead of regex for junk phrases
        text = text.replace(phrase, "") 
    # --- END OF FIX ---
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
            # --- THIS IS THE FIX ---
            if key in ed and check_field(ed.get(key)):
            # --- END OF FIX ---
                return True
    return False

# --- Extraction functions (Your existing versions) ---
def extract_basic_info(soup):
    """Extracts basic info from the new top-card layout."""
    name, headline, location, profile_pic_url, cover_pic_url = ("Not available",) * 5
    try:
        top_card = soup.find("section", class_="_140ad967")
        if top_card:
            name = clean(top_card.select_one('p._9cd462e2._58b9cc0a'))
            headline = clean(top_card.select_one('p.a256db30.ba57d3d2'))
            
            # --- FIX 2: Location ---
            # Find all <p> tags with this class and take the first one
            # that is NOT "Contact info".
            all_locations = top_card.select('p[class*="d89f4058"]')
            for loc in all_locations:
                if "Contact info" not in loc.get_text():
                    location = clean(loc)
                    break # Found it
            # --- END FIX 2 ---
            
            # --- FIX 1: Images ---
            # Find ALL images in the top card
            all_images = top_card.find_all("img", class_="_5d57a262")
            for img in all_images:
                if 'src' in img.attrs:
                    if "profile-displaybackgroundimage" in img['src']:
                        # This is the Cover Picture
                        cover_pic_url = img['src']
                    elif "profile-displayphoto" in img['src']:
                        # This is the Profile Picture
                        profile_pic_url = img['src']
            # --- END FIX 1 ---
    except Exception:
        pass
    return name, headline, location, profile_pic_url, cover_pic_url

def extract_about(soup):
    """Extracts about section using the new data-testid selector."""
    try:
        about_section = find_section(soup, "About")
        if about_section:
            about_span = about_section.find("span", {"data-testid": "expandable-text-box"})
            if about_span:
                
                # --- THIS IS THE FIX ---
                # Find the "… more" button within the span
                button = about_span.find("button", {"data-testid": "expandable-text-button"})
                if button:
                    button.decompose() # This removes the button and all its text
                # --- END OF FIX ---

                return clean(about_span) # Now we clean the span *without* the button
    except Exception:
        return "Not available"
    return "Not available"

def extract_experience(soup):
    """Extracts experience using the new component-based structure."""
    experiences = []
    seen = set()
    try:
        experience_section = find_section(soup, "Experience")
        if not experience_section:
            return []
        
        job_items = experience_section.select("div[componentkey*='entity-collection-item']")
        
        for item in job_items:
            texts = item.find_all("p", class_="_9cd462e2")
            if not texts or len(texts) < 4:
                continue

            role = clean(texts[0])
            company_type = clean(texts[1])
            date_text = clean(texts[2])
            location = clean(texts[3])
            
            company_parts = company_type.split('·')
            company_name = company_parts[0].strip()
            job_type = company_parts[1].strip() if len(company_parts) > 1 else "Not available"

            date_from, date_to, is_current = parse_date_range(date_text)

            details = "Not available"
            details_span = item.find("span", {"data-testid": "expandable-text-box"})
            if details_span:
                
                # --- THIS IS THE FIX ---
                # Find the "… more" button within the span
                button = details_span.find("button", {"data-testid": "expandable-text-button"})
                if button:
                    button.decompose() # This removes the button and all its text
                # --- END OF FIX ---

                details = clean(details_span) # Now we clean the span *without* the button

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
    except Exception:
        pass
    return experiences

def extract_education(soup):
    """Extracts education using the new component-based structure."""
    educations = []
    seen = set()
    try:
        education_section = find_section(soup, "Education")
        if not education_section:
            return []

        edu_items = education_section.find_all("div", class_="_0a9a31e1")

        for item in edu_items:
            texts = item.find_all("p", class_="_9cd462e2")
            if not texts or len(texts) < 3:
                continue

            institution = clean(texts[0])
            degree = clean(texts[1])
            date_text = clean(texts[2])

            date_from, date_to, is_current = parse_date_range(date_text)

# --- FIX 3: Education Details ---
            details = "Not available"
            # Find all <p> tags inside the item
            all_p_tags = item.find_all("p", class_="_9cd462e2")
            
            # The details are in the 4th <p> tag (if it exists)
            if len(all_p_tags) > 3:
                # Check that it's not the skills link
                if not all_p_tags[3].find_parent(attrs={"role": "button"}):
                    details = clean(all_p_tags[3])
# --- END FIX 3 ---

            identifier = (institution, degree, date_from)
            if institution == "Not available" or identifier in seen:
                continue
            seen.add(identifier)
            educations.append({
                "institution_name": institution,
                "degree": degree,
                "date_from": date_from,
                "date_to": date_to,
                "details": details,
                "is_current": is_current
            })
    except Exception:
        pass
    return educations

def extract_skills(soup):
    """Extracts skills using the new component-based structure."""
    skills = []
    try:
        skills_section = find_section(soup, "Skills")
        if not skills_section:
            return []
            
        skill_elements = skills_section.select("div[componentkey*='com.linkedin.sdui.profile.skill'] p[class*='a256db30']")
        for el in skill_elements:
            skill_name = clean(el)
            if skill_name != "Not available":
                skills.append(skill_name)
    except Exception:
        pass
    return skills

def extract_languages(soup):
    """Extracts languages using the new component-based structure."""
    languages = []
    try:
        languages_section = find_section(soup, "Languages")
        if not languages_section:
            return []

        lang_items = languages_section.find_all("div", class_="_0a9a31e1")
        for item in lang_items:
            texts = item.find_all("p", class_="_9cd462e2")
            if len(texts) < 2:
                continue
                
            name = clean(texts[0])
            proficiency = clean(texts[1])
            
            if name != "Not available":
                languages.append({"language": name, "proficiency": proficiency})
    except Exception:
        pass
    return languages

# --- Main Orchestration (Unchanged) ---
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