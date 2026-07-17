import re
from pypdf import PdfReader

SKILLS_LIBRARY = [
    # Frontend
    "React", "Angular", "Vue", "Svelte", "HTML", "CSS", "JavaScript", "TypeScript", "Next.js", "Nuxt.js",
    "TailwindCSS", "Bootstrap", "Redux", "Webpack", "Vite", "jQuery", "GraphQL", "APIs", "UI Design",
    # Backend
    "Python", "Django", "Flask", "FastAPI", "Node.js", "Express", "Ruby", "Rails", "Java", "Spring", "Spring Boot",
    "PHP", "Laravel", "Go", "Golang", "C++", "C#", ".NET", "ASP.NET", "Rust", "Scala",
    # Database
    "SQL", "MySQL", "PostgreSQL", "SQLite", "MongoDB", "Redis", "Firebase", "Cassandra", "Oracle",
    # DevOps / Cloud
    "AWS", "Azure", "GCP", "Docker", "Kubernetes", "CI/CD", "Git", "GitHub", "Jenkins", "Terraform", "Ansible",
    # Mobile
    "React Native", "Flutter", "iOS", "Swift", "Kotlin", "Android",
    # ML / Data Science
    "Machine Learning", "Deep Learning", "TensorFlow", "PyTorch", "NLP", "Pandas", "NumPy", "Scikit-Learn",
    # Soft skills & Methodologies
    "Agile", "Scrum", "Project Management", "Leadership", "System Design", "Microservices", "Data Structures",
    "Algorithms"
]

def extract_text_from_pdf(file_path_or_file):
    """
    Extracts text from a PDF file or an uploaded django file object.
    """
    text = ""
    try:
        reader = PdfReader(file_path_or_file)
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
    except Exception as e:
        print(f"Error reading PDF: {e}")
    return text

def parse_name(text):
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    for line in lines[:8]:  # look in the top 8 non-empty lines
        # clean punctuation
        clean = re.sub(r'[^\w\s-]', '', line).strip()
        words = clean.split()
        if 1 <= len(words) <= 3:
            lower_clean = clean.lower()
            if '@' not in line and not any(kw in lower_clean for kw in ['resume', 'curriculum', 'cv', 'email', 'phone', 'contact', 'profile', 'address', 'portfolio', 'developer', 'engineer']):
                if re.search(r'[a-zA-Z]', clean):
                    return clean
    return "Unknown Candidate"

def parse_email(text):
    match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    return match.group(0) if match else "No email found"

def parse_phone(text):
    # matches standard phone number formats
    match = re.search(r'\+?\d[\d\-\s\(\)]{8,}\d', text)
    return match.group(0).strip() if match else "No phone found"

def estimate_experience(text):
    patterns = [
        r'(\d+(?:\.\d+)?)\+?\s*years?\s+(?:of\s+)?experience',
        r'experience[:\s]+(\d+(?:\.\d+)?)\+?\s*years?',
        r'(\d+(?:\.\d+)?)\+?\s*yrs?\s+(?:of\s+)?experience',
        r'worked\s+for\s+(\d+(?:\.\d+)?)\+?\s*years?',
        r'(\d+(?:\.\d+)?)\+?\s*years?\s+in',
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            try:
                years = max(float(m) for m in matches)
                if 0.5 <= years <= 35:
                    return years
            except ValueError:
                pass
    
    # Secondary check for experience keywords
    matches = re.findall(r'(\d+)\+?\s*years?', text, re.IGNORECASE)
    if matches:
        try:
            years = max(float(m) for m in matches)
            if 1 <= years <= 25:
                return years
        except ValueError:
            pass
            
    return 1.0  # default fallback

def extract_skills(text):
    skills_found = []
    # search case-insensitively but retain the capitalization from the library
    for skill in SKILLS_LIBRARY:
        # use word boundaries to avoid matching "Go" inside "Google" or "Django"
        pattern = r'\b' + re.escape(skill) + r'\b'
        # Special check for skills with special characters like C++ or C# or .NET
        if skill in ["C++", "C#", ".NET"]:
            pattern = re.escape(skill)
            
        if re.search(pattern, text, re.IGNORECASE):
            skills_found.append(skill)
    return skills_found

def parse_resume_full(text):
    """
    Combines parsing functions to return candidate profile dictionary
    """
    name = parse_name(text)
    email = parse_email(text)
    phone = parse_phone(text)
    experience = estimate_experience(text)
    skills = extract_skills(text)
    
    return {
        "name": name,
        "email": email,
        "phone": phone,
        "experience_years": experience,
        "skills": skills,
        "resume_text": text
    }
