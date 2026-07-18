import re
import hashlib
from collections import Counter
from datetime import datetime
from pypdf import PdfReader
from .models import Candidate

def run_authenticity_audit(name, email, phone, skills, experience_years, resume_text, file_obj=None):
    """
    Executes a comprehensive suite of authenticity and anomaly audits on candidate data.
    Returns: is_suspicious, reasons, scores_dict
    """
    is_suspicious = False
    reasons = []
    
    # Normalize inputs
    name = name.strip()
    email = email.strip()
    phone = phone.strip()
    resume_lower = resume_text.lower()
    
    # Base scores initialization
    quality_score = 100
    authenticity_score = 100
    communication_score = 80
    tech_depth_score = 40
    learning_score = 60
    
    # 1. Personal Information Validation
    # Rule 6: Empty name check
    if not name or name == "Unknown Candidate":
        is_suspicious = True
        reasons.append("Personal Info Anomaly: Candidate name field is empty or unknown (Rule 6).")
        authenticity_score -= 20
        quality_score -= 15
    # Rule 5: Name check (only alphabets, spaces, and '.')
    elif not re.match(r'^[a-zA-Z\s\.]+$', name):
        is_suspicious = True
        reasons.append("Personal Info Anomaly: Candidate name contains invalid special characters (Rule 5).")
        authenticity_score -= 15
        quality_score -= 10
        
    # Rule 1: Email regex validation
    if email != "No email found" and email:
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            is_suspicious = True
            reasons.append(f"Personal Info Anomaly: Invalid email formatting syntax ('{email}') (Rule 1).")
            authenticity_score -= 20
    else:
        is_suspicious = True
        reasons.append("Missing primary contact details: No email address found (Rule 6).")
        authenticity_score -= 25
        quality_score -= 10

    # Rule 2: Disposable Email check
    suspicious_domains = ["example.com", "test.com", "temp.com", "mailinator.com", "yopmail.com", "tempmail.com", "10minutemail.com", "sharklasers.com", "guerrillamail.com"]
    email_domain = email.split('@')[-1].lower() if '@' in email else ""
    if any(sd in email_domain for sd in suspicious_domains):
        is_suspicious = True
        reasons.append(f"Suspicious email domain: @{email_domain} (disposable/test provider) (Rule 2).")
        authenticity_score -= 25

    # Rule 3 & 4: Phone checks
    if phone != "No phone found" and phone:
        if any(c.isalpha() for c in phone):
            is_suspicious = True
            reasons.append("Personal Info Anomaly: Phone number contains invalid letters (Rule 4).")
            authenticity_score -= 15
        phone_digits = "".join(c for c in phone if c.isdigit())
        if len(phone_digits) < 10 or len(phone_digits) > 15:
            is_suspicious = True
            reasons.append(f"Personal Info Anomaly: Phone digit length is invalid (must be 10-15 digits, parsed {len(phone_digits)}) (Rule 3).")
            authenticity_score -= 15
        if re.search(r'(\d)\1{7,}', phone_digits) or "12345678" in phone_digits or "98765432" in phone_digits:
            is_suspicious = True
            reasons.append("Personal Info Anomaly: Phone number contains suspicious repeating or sequential digits (Rule 4).")
            authenticity_score -= 20
    else:
        is_suspicious = True
        reasons.append("Missing primary contact details: No phone number found (Rule 6).")
        authenticity_score -= 25
        quality_score -= 10

    # Rule 9: Compare email & phone with existing database candidates
    if email and email != "No email found":
        if Candidate.objects.filter(email=email).exclude(name=name).exists():
            is_suspicious = True
            reasons.append("Duplicate Profile Anomaly: Email matches another registered candidate (Rule 9).")
            authenticity_score -= 30
    if phone and phone != "No phone found":
        phone_digits = "".join(c for c in phone if c.isdigit())
        for other in Candidate.objects.exclude(name=name):
            other_digits = "".join(c for c in other.phone if c.isdigit())
            if other_digits == phone_digits and len(phone_digits) >= 10:
                is_suspicious = True
                reasons.append("Duplicate Profile Anomaly: Phone number matches another registered candidate (Rule 9).")
                authenticity_score -= 30
                break

    # 11-20 Resume Format
    # Rule 11: Resume < 100 words
    words = [w for w in re.findall(r'\b\w+\b', resume_lower)]
    if 0 < len(words) < 100:
        is_suspicious = True
        reasons.append(f"Format Anomaly: Resume contains less than 100 words ({len(words)} parsed) (Rule 11).")
        quality_score -= 20
        communication_score -= 15

    # Deep Integrity Audits (Rule 16: Hidden font & Metadata mismatch)
    if file_obj:
        try:
            reader = PdfReader(file_obj)
            metadata = reader.metadata
            author = metadata.get('/Author', '')
            if author and len(name) > 3:
                clean_author = re.sub(r'[^\w]', '', author.lower())
                clean_name = re.sub(r'[^\w]', '', name.lower())
                if clean_author and clean_name and clean_author not in clean_name and clean_name not in clean_author:
                    is_suspicious = True
                    reasons.append(f"Integrity Alert: PDF metadata author ('{author}') does not match candidate name ('{name}') (Rule 16).")
                    authenticity_score -= 20
            
            # Check for hidden text/keyword stuffing at the end of the text
            last_lines = [l.strip() for l in resume_lower.split('\n') if l.strip()][-3:]
            last_text = " ".join(last_lines)
            from .parser import SKILLS_LIBRARY
            skills_at_end = [s for s in SKILLS_LIBRARY if s.lower() in last_text]
            if len(skills_at_end) >= 8 and len(last_text.split()) < 30:
                is_suspicious = True
                reasons.append("Integrity Alert: Hidden SEO keyword stuffing detected in PDF background (Rule 16).")
                authenticity_score -= 25
                quality_score -= 20
        except Exception:
            pass

    if file_obj:
        try:
            reader = PdfReader(file_obj)
            # Rule 12: Resume > 10 pages
            page_count = len(reader.pages)
            if page_count > 10:
                is_suspicious = True
                reasons.append(f"Format Anomaly: Resume exceeds 10 pages ({page_count} pages) (Rule 12).")
                quality_score -= 15
            
            # Rule 20: Blank pages count
            blank_pages = 0
            for page in reader.pages:
                p_text = page.extract_text() or ""
                if len(p_text.strip()) < 10:
                    blank_pages += 1
            if blank_pages > 2:
                is_suspicious = True
                reasons.append(f"Format Anomaly: Too many blank pages detected ({blank_pages} blank/empty pages) (Rule 20).")
                quality_score -= 10
        except Exception:
            # Rule 19: Corrupted PDF check
            if hasattr(file_obj, 'name') and file_obj.name.endswith('.pdf'):
                is_suspicious = True
                reasons.append("Format Anomaly: Uploaded PDF is corrupted or unreadable (Rule 19).")
                authenticity_score -= 20

    # 21-30 Keyword Stuffing
    # Rule 21: High word frequency (> 15 times, excluding common stopwords)
    stopwords = {"the", "and", "a", "of", "to", "in", "i", "is", "that", "it", "on", "for", "with", "as", "at", "by", "an", "this", "my", "our", "us", "we", "project", "experience", "skills"}
    meaningful_words = [w for w in words if w not in stopwords and len(w) > 3]
    word_counts = Counter(meaningful_words)
    most_common_word, count = word_counts.most_common(1)[0] if word_counts else ("", 0)
    if count > 15:
        is_suspicious = True
        reasons.append(f"Keyword Stuffing: Word '{most_common_word}' repeated excessively ({count} times) (Rule 21).")
        quality_score -= 15
        communication_score -= 10

    # Rule 22: Repeated sentence check
    sentences = [s.strip() for s in re.split(r'[.!?]', resume_lower) if len(s.strip()) > 15]
    sentence_counts = Counter(sentences)
    if sentence_counts and sentence_counts.most_common(1)[0][1] >= 3:
        is_suspicious = True
        reasons.append("Keyword Stuffing: Found repeated identical sentences (Rule 22).")
        quality_score -= 15
        communication_score -= 10

    # Rule 23: Repeated paragraph check
    paragraphs = [p.strip() for p in resume_text.split('\n\n') if len(p.strip()) > 30]
    hashes = [hashlib.sha256(p.encode('utf-8')).hexdigest() for p in paragraphs]
    hash_counts = Counter(hashes)
    if hash_counts and hash_counts.most_common(1)[0][1] >= 2:
        is_suspicious = True
        reasons.append("Keyword Stuffing: Duplicate/copied paragraphs detected (Rule 23).")
        quality_score -= 15
        communication_score -= 15

    # Rule 28: Buzzword detection
    buzzwords = ["guru", "rockstar", "ninja", "legend", "visionary", "disruptor", "catalyst"]
    matched_buzz = [b for b in buzzwords if re.search(rf"\b{b}\b", resume_lower)]
    if matched_buzz:
        is_suspicious = True
        reasons.append(f"Buzzword Anomaly: Resume contains clickbait buzzwords ({', '.join(matched_buzz)}) (Rule 28).")
        quality_score -= 10
        communication_score -= 15

    # Rule 30: Repeated company names
    company_stuffer = re.search(r'\b(google|microsoft|amazon|apple|facebook|netflix|stripe)\s+\1\s+\1\b', resume_lower)
    if company_stuffer:
        is_suspicious = True
        reasons.append(f"Keyword Stuffing: Found repeating company name patterns ({company_stuffer.group(1)}) (Rule 30).")
        quality_score -= 15

    # 31-40 Skill Authenticity
    # Rule 35: Skills limit (> 20)
    if len(skills) > 20:
        is_suspicious = True
        reasons.append(f"Skill Authenticity: Abnormally high skill density ({len(skills)} unique frameworks; limit is 20) (Rule 35).")
        authenticity_score -= 20
        quality_score -= 10

    # Rule 36: Impossible combination
    sap_found = any(s in [sk.lower() for sk in skills] for s in ["sap", "abap"])
    tf_found = any(s in [sk.lower() for sk in skills] for s in ["tensorflow", "pytorch", "keras", "deep learning"])
    unity_found = any(s in [sk.lower() for sk in skills] for s in ["unity", "unreal engine", "game development"])
    blockchain_found = any(s in [sk.lower() for sk in skills] for s in ["solidity", "blockchain", "ethereum", "web3"])
    conflict_count = sum([sap_found, tf_found, unity_found, blockchain_found])
    if conflict_count >= 3:
        is_suspicious = True
        reasons.append("Skill Authenticity: Impossible skill combinations across distinct, non-overlapping domains (Rule 36).")
        authenticity_score -= 20
        tech_depth_score -= 15

    # Rule 37: Claims Machine Learning but no core libraries
    has_ml_keyword = any(k in resume_lower for k in ["machine learning", "artificial intelligence", "ml engineer", "deep learning"])
    has_ml_libs = any(s in [sk.lower() for sk in skills] for s in ["tensorflow", "pytorch", "scikit-learn", "sklearn", "keras", "pandas", "numpy"])
    if has_ml_keyword and not has_ml_libs:
        is_suspicious = True
        reasons.append("Skill Authenticity: Claims ML/AI expertise but lists no core scientific libraries (Rule 37).")
        authenticity_score -= 15
        tech_depth_score -= 15

    # 41-50 Experience & Timelines
    # Rule 46: Internship too long
    internship_years = re.findall(r'internship[^.\n]*?\b([5-9]|\d{2,})\+?\s*(?:years?|yrs?)\b', resume_lower)
    if internship_years:
        is_suspicious = True
        reasons.append(f"Experience Anomaly: Claims an abnormally long internship ({internship_years[0]} years) (Rule 46).")
        authenticity_score -= 15

    # Rule 49: Future dates check
    current_year = datetime.now().year
    future_years = re.findall(r'\b(20[3-9]\d|2[1-9]\d{2})\b', resume_lower)
    if future_years:
        valid_future = [fy for fy in future_years if int(fy) > current_year]
        if valid_future:
            is_suspicious = True
            reasons.append(f"Timeline Anomaly: Contains invalid future date ({valid_future[0]}) (Rule 49).")
            authenticity_score -= 15

    # 73-75 Certifications
    # Rule 73: Technology release dates (e.g. React in 2005)
    tech_release_years = {
        "React": 2013, "Docker": 2013, "Kubernetes": 2014, "TensorFlow": 2015,
        "PyTorch": 2016, "Flutter": 2017, "LangChain": 2022, "ChatGPT": 2022
    }
    for tech, release_year in tech_release_years.items():
        pattern = rf"{tech.lower()}[^.\n]*?\b(19\d{{2}}|200\d|201[0-2])\b"
        if re.search(pattern, resume_lower):
            is_suspicious = True
            reasons.append(f"Timeline Anomaly: Claims expertise or certification in {tech} before release year ({release_year}) (Rule 73).")
            authenticity_score -= 15

    # Rule 75: Duplicate certifications
    certs = re.findall(r'(?:certificat|certif)[^.\n]*', resume_lower)
    cleaned_certs = [re.sub(r'[^a-z0-9]', '', c) for c in certs if len(c) > 10]
    cert_counts = Counter(cleaned_certs)
    if cert_counts and cert_counts.most_common(1)[0][1] >= 2:
        is_suspicious = True
        reasons.append("Certification Anomaly: Duplicate identical certification entries (Rule 75).")
        authenticity_score -= 15
        learning_score -= 10

    # Score adjustments & bounds scaling
    quality_score = max(20, min(100, quality_score))
    authenticity_score = max(10, min(100, authenticity_score))
    fraud_score = 100 - authenticity_score

    # Communication score adjustment based on verbs
    active_verbs = ["implemented", "scaled", "designed", "developed", "built", "managed", "created", "led", "architected"]
    verb_count = sum(1 for v in active_verbs if v in resume_lower)
    communication_score += min(15, verb_count * 2)
    communication_score = max(30, min(98, communication_score))

    # Technical depth adjustments based on skills density & experience
    tech_depth_score += min(50, len(skills) * 3)
    if experience_years >= 5.0:
        tech_depth_score += 15
    elif experience_years >= 3.0:
        tech_depth_score += 10
    tech_depth_score = max(20, min(99, tech_depth_score))

    # Learning ability based on certifications & portfolio mentions
    has_cert = any(c in resume_lower for c in ["certification", "certified", "course", "bootcamp"])
    if has_cert:
        learning_score += 10
    has_portfolio = any(p in resume_lower for p in ["github.com", "gitlab.com", "portfolio", "behance", "linkedin"])
    if has_portfolio:
        learning_score += 10
    learning_score += min(15, len(skills) * 1.5)
    learning_score = max(30, min(98, learning_score))

    scores = {
        "quality_score": int(quality_score),
        "authenticity_score": int(authenticity_score),
        "fraud_score": int(fraud_score),
        "communication_score": int(communication_score),
        "tech_depth_score": int(tech_depth_score),
        "learning_score": int(learning_score)
    }

    return is_suspicious, reasons, scores
