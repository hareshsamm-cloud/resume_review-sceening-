import os
import re
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.contrib import messages
from django.core.mail import send_mail
from django.contrib.auth.hashers import make_password, check_password
from .models import Candidate, EmailLog, RecruiterAccount, StudentAccount, CollegeAccount, PlacementConfig
from .parser import extract_text_from_pdf, parse_resume_full
from .recommender import get_company_recommendations_by_role
from .companies_data import COMPANIES_DATABASE

from .roles_data import ROLES_DATABASE

sorted_roles = sorted(ROLES_DATABASE.items(), key=lambda item: item[1]["title"])

JOB_ROLES = {}
for key, val in sorted_roles:
    JOB_ROLES[key] = {
        "title": val["title"],
        "skills": ", ".join(val["skills"]),
        "experience": str(val["experience"])
    }

def landing_view(request):
    """
    Renders the portal entrance page.
    """
    return render(request, 'screener/landing.html')

def recruiter_dashboard(request):
    """
    Recruiter workspace dashboard.
    """
    if request.session.get('user_role') != 'recruiter':
        messages.error(request, "Please log in as a Recruiter to access the Recruiter Cockpit.")
        return redirect('/login/?role=recruiter')

    candidates = Candidate.objects.filter(decision="Pending").order_by('-match_score')
    accepted_candidates = Candidate.objects.filter(decision="Accepted").order_by('-match_score')
    rejected_candidates = Candidate.objects.filter(decision="Rejected").order_by('-match_score')
    
    email_logs = EmailLog.objects.all().order_by('-sent_at')
    
    # Selected filters / inputs
    # Load filters / inputs from session, falling back to frontend defaults
    selected_role_key = request.session.get('job_role', 'frontend')
    req_skills_str = request.session.get('skills_required', 'React, TypeScript, HTML, CSS, Next.js')
    min_exp_str = request.session.get('min_experience', '2.0')
    target_count_str = request.session.get('target_count', '3')
    
    if request.method == 'POST':
        selected_role_key = request.POST.get('job_role', selected_role_key)
        req_skills_str = request.POST.get('skills_required', req_skills_str)
        min_exp_str = request.POST.get('min_experience', min_exp_str)
        target_count_str = request.POST.get('target_count', target_count_str)
        
        # Save updated variables in the session
        request.session['job_role'] = selected_role_key
        request.session['skills_required'] = req_skills_str
        request.session['min_experience'] = min_exp_str
        request.session['target_count'] = target_count_str
        
    try:
        min_exp = float(min_exp_str)
    except ValueError:
        min_exp = 2.0
        
    try:
        target_count = int(target_count_str)
    except ValueError:
        target_count = 3

    if request.method == 'POST' and 'resumes' in request.FILES:
        # Delete previous candidates for a fresh scan
        Candidate.objects.all().delete()
        EmailLog.objects.all().delete()
        
        files = request.FILES.getlist('resumes')
        req_skills = [s.strip().lower() for s in req_skills_str.split(',') if s.strip()]
        
        for file in files:
            text = ""
            if file.name.endswith('.pdf'):
                text = extract_text_from_pdf(file)
            elif file.name.endswith('.txt'):
                text = file.read().decode('utf-8', errors='ignore')
            else:
                continue
                
            if not text.strip():
                continue
                
            parsed = parse_resume_full(text)
            candidate_skills = parsed["skills"]
            candidate_exp = parsed["experience_years"]
            
            # Skills score
            candidate_skills_lower = [s.lower() for s in candidate_skills]
            matched_reqs = [r for r in req_skills if r in candidate_skills_lower]
            skills_score = (len(matched_reqs) / len(req_skills)) * 100 if req_skills else 100
            
            # Experience score
            if candidate_exp >= min_exp:
                exp_score = 100
            else:
                exp_score = (candidate_exp / min_exp) * 100 if min_exp > 0 else 100
                
            overall_score = round(0.7 * skills_score + 0.3 * exp_score)
            
            if overall_score >= 80:
                fit = "Strong Match"
            elif overall_score >= 60:
                fit = "Good Match"
            elif overall_score >= 40:
                fit = "Partial Match"
            else:
                fit = "Poor Match"
                
            # Impressive points
            impressive = []
            if len(matched_reqs) > 0:
                skills_caps = [s.capitalize() for s in matched_reqs]
                impressive.append(f"Matches required skills: {', '.join(skills_caps[:4])}")
            if candidate_exp >= min_exp:
                impressive.append(f"Exceeds experience requirement with {candidate_exp} years (required {min_exp} years)")
            else:
                impressive.append(f"Possesses {candidate_exp} years of relevant experience")
                
            extra_skills = [s for s in candidate_skills if s.lower() not in req_skills]
            if extra_skills:
                impressive.append(f"Brings auxiliary expertise in: {', '.join(extra_skills[:3])}")
                
            gaps = []
            missing_reqs = [r.capitalize() for r in req_skills if r not in candidate_skills_lower]
            if missing_reqs:
                gaps.append(f"Lacks core technologies: {', '.join(missing_reqs[:4])}")
            if candidate_exp < min_exp:
                gaps.append(f"Experience deficit: {round(min_exp - candidate_exp, 1)} years short of requested {min_exp} years")
                
            name_to_save = parsed["name"]
            if name_to_save == "Unknown Candidate":
                name_to_save = os.path.splitext(file.name)[0].replace('_', ' ').replace('-', ' ').title()
                
            Candidate.objects.create(
                name=name_to_save,
                email=parsed["email"] if parsed["email"] != "No email found" else f"{name_to_save.lower().replace(' ', '')}@example.com",
                phone=parsed["phone"],
                skills=",".join(candidate_skills),
                experience_years=candidate_exp,
                resume_text=text,
                match_score=overall_score,
                fit_assessment=fit,
                impressive_summary="||".join(impressive),
                requirements_needed="||".join(gaps)
            )
            
        return redirect('recruiter_dashboard')

    elif request.method == 'POST' and 'unload_demo' in request.POST:
        Candidate.objects.all().delete()
        EmailLog.objects.all().delete()
        return redirect('recruiter_dashboard')

    elif request.method == 'POST' and 'load_demo' in request.POST:
        # Load preset demo resumes for immediate mock previewing
        Candidate.objects.all().delete()
        EmailLog.objects.all().delete()
        
        # Lists for generating 40 mock profiles dynamically
        first_names = ["Jane", "Arjun", "David", "Emily", "Sarah", "Carlos", "Yuki", "Chloe", "Kwame", "Sofia", 
                       "Liam", "Anya", "Wei", "Fatima", "Marcus", "Aisha", "Hans", "Priya", "Mateo", "Olivia",
                       "Jamal", "Elena", "Kenji", "Isabella", "Tariq", "Grace", "Alan", "Ada", "Linus", "Tim",
                       "John", "Claude", "Donald", "Barbara", "Guido", "Margaret", "Dennis", "Bjarne", "James", "Richard"]
        last_names = ["Connor", "Sharma", "Miller", "Watson", "Jenkins", "Mendez", "Tanaka", "Dubois", "Mensah", "Rossi",
                      "O'Connor", "Petrova", "Chen", "Al-Sayed", "Vance", "Diop", "Schmidt", "Patel", "Silva", "Bennett",
                      "Jackson", "Rostova", "Sato", "Santos", "Mahmood", "Hopper", "Turing", "Lovelace", "Torvalds", "Berners",
                      "McCarthy", "Shannon", "Knuth", "Liskov", "Rossum", "Hamilton", "Ritchie", "Stroustrup", "Gosling", "Feynman"]
                      
        domains = [
            ["React", "TypeScript", "HTML", "CSS", "Next.js", "TailwindCSS", "Redux", "Vite", "JavaScript"],
            ["Python", "Django", "SQL", "PostgreSQL", "Node.js", "Express", "APIs", "MongoDB", "SQLite"],
            ["React", "TypeScript", "Node.js", "Python", "SQL", "Django", "Git", "APIs", "HTML", "CSS"],
            ["AWS", "Docker", "Kubernetes", "CI/CD", "Git", "Terraform", "Linux", "Ansible"],
            ["Python", "Machine Learning", "Deep Learning", "TensorFlow", "PyTorch", "Pandas", "Algorithms"],
            ["Python", "SQL", "Pandas", "NumPy", "Scikit-Learn", "Data Visualization", "Excel"],
            ["React Native", "Flutter", "TypeScript", "Dart", "iOS", "Android", "APIs", "Git"],
            ["Selenium", "Python", "Java", "Playwright", "Git", "Testing", "Jira"],
            ["Security", "Linux", "Network Security", "Firewalls", "SIEM", "Cryptography", "VPN"],
            ["Product Strategy", "Roadmapping", "Agile", "Scrum", "Jira", "Leadership", "Communication"]
        ]
        
        req_skills = [s.strip().lower() for s in req_skills_str.split(',') if s.strip()]
        
        import random
        random.seed(42) # Consistent random generation
        
        for i in range(40):
            fn = first_names[i % len(first_names)]
            ln = last_names[i % len(last_names)]
            name = f"{fn} {ln}"
            email = f"{fn.lower()}.{ln.lower()}@example.com"
            phone = f"+1 (555) 019-{2000 + i * 13}"
            
            # Select random domain and slice random amount of skills
            domain_skills = domains[i % len(domains)]
            num_skills = random.randint(4, min(len(domain_skills), 8))
            skills_sample = random.sample(domain_skills, num_skills)
            
            # Experience years between 0.5 to 9.5
            candidate_exp = round(random.uniform(0.5, 9.5), 1)
            
            skills_lower = [s.lower() for s in skills_sample]
            
            matched_reqs = [r for r in req_skills if r in skills_lower]
            skills_score = (len(matched_reqs) / len(req_skills)) * 100 if req_skills else 100
            
            if candidate_exp >= min_exp:
                exp_score = 100
            else:
                exp_score = (candidate_exp / min_exp) * 100 if min_exp > 0 else 100
                
            overall_score = round(0.7 * skills_score + 0.3 * exp_score)
            
            if overall_score >= 80:
                fit = "Strong Match"
            elif overall_score >= 60:
                fit = "Good Match"
            elif overall_score >= 40:
                fit = "Partial Match"
            else:
                fit = "Poor Match"
                
            impressive = []
            if len(matched_reqs) > 0:
                skills_caps = [s.capitalize() for s in matched_reqs]
                impressive.append(f"Matches required skills: {', '.join(skills_caps[:4])}")
            if candidate_exp >= min_exp:
                impressive.append(f"Exceeds experience requirement with {candidate_exp} years (required {min_exp} years)")
            else:
                impressive.append(f"Possesses {candidate_exp} years of relevant experience")
            
            extra_skills = [s for s in skills_sample if s.lower() not in req_skills]
            if extra_skills:
                impressive.append(f"Brings auxiliary expertise in: {', '.join(extra_skills[:3])}")
                
            gaps = []
            missing_reqs = [r.capitalize() for r in req_skills if r not in skills_lower]
            if missing_reqs:
                gaps.append(f"Lacks core technologies: {', '.join(missing_reqs[:4])}")
            if candidate_exp < min_exp:
                gaps.append(f"Experience deficit: {round(min_exp - candidate_exp, 1)} years short of requested {min_exp} years")
                
            Candidate.objects.create(
                name=name,
                email=email,
                phone=phone,
                skills=",".join(skills_sample),
                experience_years=candidate_exp,
                resume_text=f"Resume of {name}. Standout technical expertise includes: {', '.join(skills_sample)}.",
                match_score=overall_score,
                fit_assessment=fit,
                impressive_summary="||".join(impressive),
                requirements_needed="||".join(gaps)
            )
            
        # Create 3 custom mock candidates explicitly triggering different anomaly detection rules for live demo audits
        fake_candidates = [
            {
                "name": "Lucas Vance",
                "email": "lucas.vance@outlook.com",
                "phone": "+1 (555) 901-1234",
                "skills": "React,TypeScript,HTML,CSS,Node.js,Django,PostgreSQL,AWS,Docker,Kubernetes,PyTorch,Solidity,Unity,C#,Terraform,Git,Redux,Next.js,Vue,Angular,Flutter,GraphQL",
                "experience_years": 3.2,
                "resume_text": "Resume of Lucas Vance. Claims expert mastery in React, TypeScript, HTML, CSS, Node.js, Django, PostgreSQL, AWS, Docker, Kubernetes, PyTorch, Solidity, Unity, C#, Terraform, Git, Redux, Next.js, Vue, Angular, Flutter, GraphQL."
            },
            {
                "name": "Sophia Chen",
                "email": "sophia.chen@example.com",
                "phone": "+1 (555) 302-5678",
                "skills": "Python,PyTorch,ChatGPT,LangChain",
                "experience_years": 6.5,
                "resume_text": "Resume of Sophia Chen. Sophia has 6 years of experience in ChatGPT prompt engineering and LangChain pipeline developments."
            },
            {
                "name": "Alex Rivera",
                "email": "alex.rivera@yopmail.com",
                "phone": "+1 (555) 403-7890",
                "skills": "React,TailwindCSS,PyTorch,TensorFlow,Solidity,Web3,Unity",
                "experience_years": 1.8,
                "resume_text": "Resume of Alex Rivera. Professional front-end React developer, AI researcher in PyTorch and TensorFlow, Solidity smart contract designer, and Unity game developer."
            }
        ]
        
        for fc in fake_candidates:
            skills_list = fc["skills"].split(",")
            skills_lower = [s.lower() for s in skills_list]
            matched_reqs = [r for r in req_skills if r in skills_lower]
            skills_score = (len(matched_reqs) / len(req_skills)) * 100 if req_skills else 100
            
            candidate_exp = fc["experience_years"]
            if candidate_exp >= min_exp:
                exp_score = 100
            else:
                exp_score = (candidate_exp / min_exp) * 100 if min_exp > 0 else 100
                
            overall_score = round(0.7 * skills_score + 0.3 * exp_score)
            
            if overall_score >= 80:
                fit = "Strong Match"
            elif overall_score >= 60:
                fit = "Good Match"
            elif overall_score >= 40:
                fit = "Partial Match"
            else:
                fit = "Poor Match"
                
            impressive = []
            if len(matched_reqs) > 0:
                skills_caps = [s.capitalize() for s in matched_reqs]
                impressive.append(f"Matches required skills: {', '.join(skills_caps[:4])}")
            if candidate_exp >= min_exp:
                impressive.append(f"Exceeds experience requirement with {candidate_exp} years (required {min_exp} years)")
            else:
                impressive.append(f"Possesses {candidate_exp} years of relevant experience")
            
            extra_skills = [s for s in skills_list if s.lower() not in req_skills]
            if extra_skills:
                impressive.append(f"Brings auxiliary expertise in: {', '.join(extra_skills[:3])}")
                
            gaps = []
            missing_reqs = [r.capitalize() for r in req_skills if r not in skills_lower]
            if missing_reqs:
                gaps.append(f"Lacks core technologies: {', '.join(missing_reqs[:4])}")
            if candidate_exp < min_exp:
                gaps.append(f"Experience deficit: {round(min_exp - candidate_exp, 1)} years short of requested {min_exp} years")
                
            Candidate.objects.create(
                name=fc["name"],
                email=fc["email"],
                phone=fc["phone"],
                skills=fc["skills"],
                experience_years=candidate_exp,
                resume_text=fc["resume_text"],
                match_score=overall_score,
                fit_assessment=fit,
                impressive_summary="||".join(impressive),
                requirements_needed="||".join(gaps)
            )
            
        return redirect('recruiter_dashboard')

    # Evaluate all candidates in-memory to preserve attached python properties in templates
    all_candidates = list(Candidate.objects.all())
    req_skills = [s.strip().lower() for s in req_skills_str.split(',') if s.strip()]
    
    for cand in all_candidates:
        candidate_skills = [s.strip() for s in cand.skills.split(',') if s.strip()]
        candidate_skills_lower = [s.lower() for s in candidate_skills]
        candidate_exp = cand.experience_years
        
        # Skills score matching
        matched_reqs = [r for r in req_skills if r in candidate_skills_lower]
        skills_score = (len(matched_reqs) / len(req_skills)) * 100 if req_skills else 100
        
        # Experience score matching
        if candidate_exp >= min_exp:
            exp_score = 100
        else:
            exp_score = (candidate_exp / min_exp) * 100 if min_exp > 0 else 100
            
        overall_score = round(0.7 * skills_score + 0.3 * exp_score)
        
        if overall_score >= 80:
            fit = "Strong Match"
        elif overall_score >= 60:
            fit = "Good Match"
        elif overall_score >= 40:
            fit = "Partial Match"
        else:
            fit = "Poor Match"
            
        # Impressive highlights
        impressive = []
        if len(matched_reqs) > 0:
            skills_caps = [s.capitalize() for s in matched_reqs]
            impressive.append(f"Matches required skills: {', '.join(skills_caps[:4])}")
        if candidate_exp >= min_exp:
            impressive.append(f"Exceeds experience requirement with {candidate_exp} years (required {min_exp} years)")
        else:
            impressive.append(f"Possesses {candidate_exp} years of relevant experience")
            
        extra_skills = [s for s in candidate_skills if s.lower() not in req_skills]
        if extra_skills:
            impressive.append(f"Brings auxiliary expertise in: {', '.join(extra_skills[:3])}")
            
        # Gaps / Needs
        gaps = []
        missing_reqs = [r.capitalize() for r in req_skills if r not in candidate_skills_lower]
        if missing_reqs:
            gaps.append(f"Lacks core technologies: {', '.join(missing_reqs[:4])}")
        if candidate_exp < min_exp:
            gaps.append(f"Experience deficit: {round(min_exp - candidate_exp, 1)} years short of requested {min_exp} years")
            
        # Save calculations to DB
        cand.match_score = overall_score
        cand.fit_assessment = fit
        cand.impressive_summary = "||".join(impressive)
        cand.requirements_needed = "||".join(gaps)
        cand.save()

        # Run Anomaly / Authenticity Audits in-memory
        cand.is_suspicious = False
        cand.suspicious_reasons = []
        
        # 1. Personal Information Validation Rules (Rules 1, 3, 4, 5, 6)
        if cand.name.strip() == "":
            cand.is_suspicious = True
            cand.suspicious_reasons.append("Personal Info Anomaly: Candidate name field is empty.")
        elif not re.match(r'^[a-zA-Z\s\.]+$', cand.name):
            cand.is_suspicious = True
            cand.suspicious_reasons.append("Personal Info Anomaly: Candidate name contains invalid special characters.")

        if cand.email != "No email found":
            if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', cand.email):
                cand.is_suspicious = True
                cand.suspicious_reasons.append(f"Personal Info Anomaly: Invalid email formatting syntax ('{cand.email}').")
        else:
            cand.is_suspicious = True
            cand.suspicious_reasons.append("Missing primary contact details (No email address found).")

        if cand.phone != "No phone found":
            if any(c.isalpha() for c in cand.phone):
                cand.is_suspicious = True
                cand.suspicious_reasons.append("Personal Info Anomaly: Phone number contains invalid letters.")
            phone_digits = "".join(c for c in cand.phone if c.isdigit())
            if len(phone_digits) < 10 or len(phone_digits) > 15:
                cand.is_suspicious = True
                cand.suspicious_reasons.append(f"Personal Info Anomaly: Phone digit length is invalid (must be 10-15 digits, parsed {len(phone_digits)}).")
        else:
            cand.is_suspicious = True
            cand.suspicious_reasons.append("Missing primary contact details (No phone number found).")

        # Heuristic 4: Suspicious/Disposable Email Domain
        suspicious_domains = ["example.com", "test.com", "temp.com", "mailinator.com", "yopmail.com", "tempmail.com"]
        email_domain = cand.email.split('@')[-1].lower() if '@' in cand.email else ""
        if any(sd in email_domain for sd in suspicious_domains):
            cand.is_suspicious = True
            cand.suspicious_reasons.append(f"Suspicious email domain: @{email_domain} (disposable/test provider).")

        # 3. Keyword Stuffing / Spam Validation (Rules 21, 28, 30, 35)
        if len(candidate_skills) > 20:
            cand.is_suspicious = True
            cand.suspicious_reasons.append(f"Keyword Stuffing Anomaly: Abnormally high skill density ({len(candidate_skills)} unique frameworks; limit is 20).")

        # Check for 3+ consecutive repeating identical words (e.g. "Google Google Google")
        if re.search(r'\b(\w+)\s+\1\s+\1\b', cand.resume_text.lower()):
            cand.is_suspicious = True
            cand.suspicious_reasons.append("Keyword Stuffing Anomaly: Found 3+ consecutive repeating identical words (Stuffer pattern).")

        # Buzzword abuse checker
        buzzwords = ["guru", "rockstar", "ninja", "legend", "visionary"]
        resume_lower = cand.resume_text.lower()
        matched_buzz = [b for b in buzzwords if re.search(rf"\b{b}\b", resume_lower)]
        if matched_buzz:
            cand.is_suspicious = True
            cand.suspicious_reasons.append(f"Buzzword Anomaly: Resume contains clickbait/abuse buzzwords ({', '.join(matched_buzz)}).")

        # 4. Certification Timeline & Plausibility Validation (Rule 73)
        tech_release_years = {
            "React": 2013,
            "Docker": 2013,
            "Kubernetes": 2014,
            "TensorFlow": 2015,
            "PyTorch": 2016,
            "Flutter": 2017,
            "LangChain": 2022,
            "ChatGPT": 2022
        }
        for tech, release_year in tech_release_years.items():
            # Check for patterns like "React certification in 2008"
            pattern = rf"{tech.lower()}[^.\n]*?\b(19\d{{2}}|200\d|201[0-2])\b"
            if re.search(pattern, resume_lower):
                cand.is_suspicious = True
                cand.suspicious_reasons.append(f"Certification Timeline Anomaly: Claims certification or expertise in {tech} before its release year ({release_year}).")

        # Heuristic: Timeline Plausibility Anomaly (ChatGPT/GenAI years check)
        if any(buzz in resume_lower for buzz in ["chatgpt", "gpt-4", "prompt engineering", "langchain", "llama"]) and cand.experience_years > 4.0:
            regex_genai = r'(?:4|5|6|7|8|9|\d{2,})\+?\s*(?:years?|yrs?)[^.\n]*(?:chatgpt|gpt-4|prompt engineering|langchain|llama|generative ai)'
            if re.search(regex_genai, resume_lower):
                cand.is_suspicious = True
                cand.suspicious_reasons.append("Certification Timeline Anomaly: Claims >4 years of experience in post-2022 Generative AI/LLMs.")

        # Heuristic: Cross-Domain Tech Conflict (Rule 36)
        web_skills = {"react", "typescript", "html", "css", "vue", "angular"}
        ai_skills = {"pytorch", "tensorflow", "deep learning", "machine learning", "nlp"}
        blockchain_skills = {"solidity", "ethereum", "smart contracts", "web3"}
        game_skills = {"unity", "unreal engine", "c#"}
        
        active_domains = 0
        if any(s in candidate_skills_lower for s in web_skills): active_domains += 1
        if any(s in candidate_skills_lower for s in ai_skills): active_domains += 1
        if any(s in candidate_skills_lower for s in blockchain_skills): active_domains += 1
        if any(s in candidate_skills_lower for s in game_skills): active_domains += 1
        
        if active_domains >= 3:
            cand.is_suspicious = True
            cand.suspicious_reasons.append(f"Multi-Stack Anomaly: Claims expert proficiency in {active_domains} unrelated tech domains (Web, AI, Blockchain, Game Dev).")

        # Heuristic: Senior target role experience mismatch (Rule 40/63)
        current_role_title = JOB_ROLES.get(selected_role_key, {}).get("title", "")
        if ("Architect" in current_role_title or "Lead" in current_role_title or "Senior" in current_role_title) and cand.experience_years < 2.0:
            cand.is_suspicious = True
            cand.suspicious_reasons.append(f"Seniority Mismatch Anomaly: Targeting a senior/architect role with only {cand.experience_years} years of experience.")

    # In-memory partitioning to preserve properties
    scanned_candidates = [c for c in all_candidates if c.decision == "Pending"]
    scanned_candidates.sort(key=lambda c: c.match_score, reverse=True)
    
    top_candidates = scanned_candidates[:target_count]
    other_candidates = scanned_candidates[target_count:]
    
    accepted_candidates = [c for c in all_candidates if c.decision == "Accepted"]
    accepted_candidates.sort(key=lambda c: c.match_score, reverse=True)
    
    rejected_candidates = [c for c in all_candidates if c.decision == "Rejected"]
    rejected_candidates.sort(key=lambda c: c.match_score, reverse=True)
    
    total_count = len(all_candidates)
    avg_score = round(sum(c.match_score for c in all_candidates) / total_count) if total_count > 0 else 0
    strong_count = sum(1 for c in all_candidates if c.match_score >= 80)

    context = {
        'candidates': top_candidates,
        'other_candidates': other_candidates,
        'accepted_candidates': accepted_candidates,
        'rejected_candidates': rejected_candidates,
        'email_logs': email_logs,
        'total_count': total_count,
        'avg_score': avg_score,
        'strong_count': strong_count,
        'skills_required': req_skills_str,
        'min_experience': min_exp_str,
        'target_count': target_count_str,
        'job_roles': JOB_ROLES,
        'selected_role': selected_role_key,
        'all_candidates': all_candidates
    }
    return render(request, 'screener/recruiter.html', context)

def student_dashboard(request):
    """
    Student workspace dashboard.
    """
    if request.session.get('user_role') != 'student':
        messages.error(request, "Please log in as a Student to access the Student Career Space.")
        return redirect('/login/?role=student')

    username = request.session.get('username')
    student = StudentAccount.objects.filter(username=username).first()

    config = PlacementConfig.objects.first() or PlacementConfig.objects.create(max_fake_limit=3)
    max_fake_limit = config.max_fake_limit

    candidate_profile = None
    eligible = []
    aspirational = []
    summary_highlight = ""
    target_role = request.POST.get('target_role', '') if request.method == 'POST' else request.GET.get('target_role', '')
    
    # Store temporary session profile info to allow dynamic target role toggling
    session_profile = request.session.get('student_profile')

    if request.method == 'POST' and 'resume' in request.FILES:
        if student and student.is_blacklisted:
            messages.error(request, f"Your account has been BLACKLISTED. You cannot submit resumes.")
            return redirect('student_dashboard')

        file = request.FILES['resume']
        text = ""
        
        if file.name.endswith('.pdf'):
            text = extract_text_from_pdf(file)
        elif file.name.endswith('.txt'):
            text = file.read().decode('utf-8', errors='ignore')
            
        if text.strip():
            parsed = parse_resume_full(text)
            
            # Student-side Authenticity Checks
            is_suspicious = False
            reasons = []
            
            cand_name = parsed["name"] if parsed["name"] != "Unknown Candidate" else os.path.splitext(file.name)[0].replace('_', ' ').replace('-', ' ').title()
            cand_email = parsed["email"]
            cand_phone = parsed["phone"]
            candidate_skills = parsed["skills"]
            candidate_skills_lower = [s.lower() for s in candidate_skills]
            candidate_exp = parsed["experience_years"]
            resume_lower = text.lower()
            
            if not cand_name.strip():
                is_suspicious = True
                reasons.append("Personal Info Anomaly: Candidate name field is empty.")
            elif not re.match(r'^[a-zA-Z\s\.]+$', cand_name):
                is_suspicious = True
                reasons.append("Personal Info Anomaly: Candidate name contains invalid special characters.")

            if cand_email != "No email found":
                if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', cand_email):
                    is_suspicious = True
                    reasons.append(f"Personal Info Anomaly: Invalid email formatting syntax ('{cand_email}').")
            else:
                is_suspicious = True
                reasons.append("Missing primary contact details (No email address found).")

            if cand_phone != "No phone found":
                if any(c.isalpha() for c in cand_phone):
                    is_suspicious = True
                    reasons.append("Personal Info Anomaly: Phone number contains invalid letters.")
                phone_digits = "".join(c for c in cand_phone if c.isdigit())
                if len(phone_digits) < 10 or len(phone_digits) > 15:
                    is_suspicious = True
                    reasons.append("Personal Info Anomaly: Phone digit length is invalid.")
            else:
                is_suspicious = True
                reasons.append("Missing primary contact details (No phone number found).")

            suspicious_domains = ["example.com", "test.com", "temp.com", "mailinator.com", "yopmail.com", "tempmail.com"]
            email_domain = cand_email.split('@')[-1].lower() if '@' in cand_email else ""
            if any(sd in email_domain for sd in suspicious_domains):
                is_suspicious = True
                reasons.append(f"Suspicious email domain: @{email_domain} (disposable provider).")

            if len(candidate_skills) > 20:
                is_suspicious = True
                reasons.append(f"Keyword Stuffing Anomaly: Abnormally high skill density ({len(candidate_skills)} unique frameworks; limit is 20).")

            if re.search(r'\b(\w+)\s+\1\s+\1\b', resume_lower):
                is_suspicious = True
                reasons.append("Keyword Stuffing Anomaly: Found 3+ consecutive repeating identical words.")

            buzzwords = ["guru", "rockstar", "ninja", "legend", "visionary"]
            matched_buzz = [b for b in buzzwords if re.search(rf"\b{b}\b", resume_lower)]
            if matched_buzz:
                is_suspicious = True
                reasons.append(f"Buzzword Anomaly: Resume contains clickbait buzzwords ({', '.join(matched_buzz)}).")

            tech_release_years = {
                "React": 2013, "Docker": 2013, "Kubernetes": 2014, "TensorFlow": 2015,
                "PyTorch": 2016, "Flutter": 2017, "LangChain": 2022, "ChatGPT": 2022
            }
            for tech, release_year in tech_release_years.items():
                pattern = rf"{tech.lower()}[^.\n]*?\b(19\d{{2}}|200\d|201[0-2])\b"
                if re.search(pattern, resume_lower):
                    is_suspicious = True
                    reasons.append(f"Certification Timeline Anomaly: Claims expertise in {tech} before release ({release_year}).")

            if any(buzz in resume_lower for buzz in ["chatgpt", "gpt-4", "prompt engineering", "langchain", "llama"]) and candidate_exp > 4.0:
                regex_genai = r'(?:4|5|6|7|8|9|\d{2,})\+?\s*(?:years?|yrs?)[^.\n]*(?:chatgpt|gpt-4|prompt engineering|langchain|llama|generative ai)'
                if re.search(regex_genai, resume_lower):
                    is_suspicious = True
                    reasons.append("Certification Timeline Anomaly: Claims >4 years of experience in post-2022 Generative AI.")

            web_skills = {"react", "typescript", "html", "css", "vue", "angular"}
            ai_skills = {"pytorch", "tensorflow", "deep learning", "machine learning", "nlp"}
            blockchain_skills = {"solidity", "ethereum", "smart contracts", "web3"}
            game_skills = {"unity", "unreal engine", "c#"}
            active_domains = 0
            if any(s in candidate_skills_lower for s in web_skills): active_domains += 1
            if any(s in candidate_skills_lower for s in ai_skills): active_domains += 1
            if any(s in candidate_skills_lower for s in blockchain_skills): active_domains += 1
            if any(s in candidate_skills_lower for s in game_skills): active_domains += 1
            if active_domains >= 3:
                is_suspicious = True
                reasons.append(f"Multi-Stack Anomaly: Claims expert proficiency in {active_domains} unrelated domains.")

            # Apply Anti-gaming Warnings & Block Blacklist
            if is_suspicious:
                if student:
                    student.fake_upload_count += 1
                    if student.fake_upload_count >= max_fake_limit:
                        student.is_blacklisted = True
                        student.save()
                        messages.error(request, f"Your account has been BLACKLISTED. You have uploaded {student.fake_upload_count} fake resumes (limit: {max_fake_limit}).")
                        return redirect('student_dashboard')
                    else:
                        student.save()
                        messages.warning(request, f"Resume authenticity verification FAILED! Warning #{student.fake_upload_count} of {max_fake_limit} issued: {reasons[0]}")
            else:
                if student:
                    messages.success(request, "Resume authenticity verified! No anomalies detected.")

            # Load into parsed layout
            # Determine default role based on skills
            skills_lower = [s.lower() for s in parsed["skills"]]
            detected_role = "frontend"
            if any(s in skills_lower for s in ["django", "flask", "node.js", "java", "ruby", "go"]):
                detected_role = "backend"
            elif any(s in skills_lower for s in ["machine learning", "tensorflow", "deep learning", "pandas"]):
                detected_role = "data_science"
            elif any(s in skills_lower for s in ["docker", "kubernetes", "aws", "terraform"]):
                detected_role = "devops"
            elif any(s in skills_lower for s in ["react native", "flutter", "ios", "android", "swift"]):
                detected_role = "mobile"
                
            if not target_role:
                target_role = detected_role
                
            session_profile = {
                "name": cand_name,
                "email": cand_email,
                "phone": cand_phone,
                "experience": candidate_exp,
                "skills": candidate_skills
            }
            request.session['student_profile'] = session_profile
            
    elif request.method == 'POST' and 'load_student_demo' in request.POST:
        if student and student.is_blacklisted:
            messages.error(request, "Your account has been BLACKLISTED. You cannot submit resumes.")
            return redirect('student_dashboard')

        session_profile = {
            "name": "Sarah Jenkins",
            "email": "sarah.jenkins@stanford.edu",
            "phone": "+1 (650) 499-1029",
            "experience": 2.5,
            "skills": ["React", "TypeScript", "HTML", "CSS", "APIs", "Git", "SQL"]
        }
        request.session['student_profile'] = session_profile
        if not target_role:
            target_role = "frontend"

    if session_profile:
        candidate_profile = session_profile
        if not target_role:
            target_role = "frontend"
            
        # evaluate company matching for the selected target role
        eligible, aspirational = get_company_recommendations_by_role(
            candidate_profile["skills"], 
            candidate_profile["experience"], 
            target_role
        )
        
        # Generate automated professional bio highlight
        primary_skill = candidate_profile["skills"][0] if candidate_profile["skills"] else "Software"
        exp_text = f"{candidate_profile['experience']} years" if candidate_profile['experience'] > 1 else "1 year"
        skills_badges_str = ", ".join(candidate_profile["skills"][:5])
        
        matched_companies_names = [e["name"] for e in eligible]
        role_title = JOB_ROLES.get(target_role, {"title": "Software Engineer"})["title"]
        
        if len(eligible) > 0:
            eligibility_status = f"You are currently eligible for {len(eligible)} companies as a {role_title} ({', '.join(matched_companies_names[:3])})."
        else:
            eligibility_status = f"You are currently close to matching several top tech companies for {role_title} roles."
            
        summary_highlight = (
            f"Based on our analysis, {candidate_profile['name']} is a competent {primary_skill} Engineer "
            f"with an estimated {exp_text} of experience. Your profile reflects key strengths in {skills_badges_str}. "
            f"{eligibility_status} To boost your eligibility for premier targets (like "
            f"{', '.join([a['name'] for a in aspirational[:2]]) if aspirational else 'Google or Stripe'}), focus on building "
            f"skills in {', '.join([s for a in aspirational[:2] for s in a['missing_skills'][:2]]) if aspirational else 'System Design and Algorithms'}."
        )

    context = {
        'candidate_profile': candidate_profile,
        'eligible': eligible,
        'aspirational': aspirational,
        'summary_highlight': summary_highlight,
        'job_roles': JOB_ROLES,
        'target_role': target_role,
        'companies': COMPANIES_DATABASE,
        'student': student,
        'max_fake_limit': max_fake_limit
    }
    return render(request, 'screener/student.html', context)

def send_decision_email(request, candidate_id, decision_type):
    """
    Sends acceptance or rejection email and logs decision to db.
    """
    if request.method == 'POST':
        candidate = Candidate.objects.get(id=candidate_id)
        candidate.decision = decision_type
        candidate.save()
        
        impressive_points = candidate.get_impressive_list()
        gap_points = candidate.get_gaps_list()
        
        recipient = candidate.email
        subject = ""
        body = ""
        
        if decision_type == "Accepted":
            subject = f"Congratulations! Next Steps at ResumeSphere AI"
            body = (
                f"Dear {candidate.name},\n\n"
                f"We are pleased to inform you that you have been selected for the next round of interviews based on your resume. "
                f"Our screening system evaluated your profile with a high match score of {candidate.match_score}%.\n\n"
                f"What stood out most about your profile was:\n"
                + "\n".join([f"- {item}" for item in impressive_points]) + "\n\n"
                f"Our team will reach out within the next 48 hours to coordinate a technical video call. We are excited about the prospect of working together!\n\n"
                f"Warm regards,\n"
                f"Recruitment Team\n"
                f"ResumeSphere AI"
            )
        elif decision_type == "Rejected":
            subject = f"Application Status Update - ResumeSphere AI"
            body = (
                f"Dear {candidate.name},\n\n"
                f"Thank you for your interest in the position. We received a large volume of applications, and unfortunately, we have decided to move forward with other candidates whose profiles more closely align with our current needs.\n\n"
                f"Specifically, we noted gaps in the following areas:\n"
                + "\n".join([f"- {item}" for item in gap_points]) + "\n\n"
                f"We encourage you to expand your skillset in these areas and apply for future openings. We wish you the very best in your search.\n\n"
                f"Sincerely,\n"
                f"Recruitment Team\n"
                f"ResumeSphere AI"
            )
            
        try:
            send_mail(
                subject=subject,
                message=body,
                from_email='recruitment@resumesphere.ai',
                recipient_list=[recipient],
                fail_silently=False,
            )
        except Exception as e:
            print(f"SMTP Send failed (console backend will still mock output): {e}")
            
        # Log to db for visual outbox log
        EmailLog.objects.create(
            candidate=candidate,
            recipient_email=recipient,
            subject=subject,
            body=body,
            status=decision_type
        )
        
        messages.success(request, f"Email notification sent to {candidate.name} ({decision_type})!")
        
    return redirect('recruiter_dashboard')

def college_dashboard(request):
    """
    College Placement & Partner Management Dashboard.
    """
    if request.session.get('user_role') != 'college':
        messages.error(request, "Please log in as a College Administrator to access the Placement Portal.")
        return redirect('/login/?role=college')

    config = PlacementConfig.objects.first() or PlacementConfig.objects.create(max_fake_limit=3)

    if request.method == 'POST' and 'update_settings' in request.POST:
        max_fake_limit_str = request.POST.get('max_fake_limit', '3')
        try:
            limit = int(max_fake_limit_str)
            if limit < 1:
                limit = 1
            config.max_fake_limit = limit
            config.save()
            messages.success(request, f"Placement security configuration updated. Blacklist threshold set to {limit} fakes.")
        except ValueError:
            messages.error(request, "Invalid threshold limit.")
        return redirect('college_dashboard')

    elif request.method == 'POST' and 'unban_student' in request.POST:
        student_id = request.POST.get('student_id')
        student_to_unban = StudentAccount.objects.filter(id=student_id).first()
        if student_to_unban:
            student_to_unban.fake_upload_count = 0
            student_to_unban.is_blacklisted = False
            student_to_unban.save()
            messages.success(request, f"Account for Student {student_to_unban.username} restored successfully!")
        return redirect('college_dashboard')

    blacklisted_students = StudentAccount.objects.filter(is_blacklisted=True)
    warned_students = StudentAccount.objects.filter(fake_upload_count__gt=0, is_blacklisted=False)

    context = {
        'companies': COMPANIES_DATABASE,
        'config': config,
        'blacklisted_students': blacklisted_students,
        'warned_students': warned_students
    }
    return render(request, 'screener/college.html', context)


def signup_view(request):
    role = request.GET.get('role', 'recruiter')
    if request.method == 'POST':
        role = request.POST.get('role', 'recruiter')
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        
        if not username or not email or not password:
            messages.error(request, "All fields are required.")
            return render(request, 'screener/signup.html', {'role': role})
            
        if not email.endswith('@gmail.com'):
            messages.error(request, "Only Gmail addresses (@gmail.com) are allowed.")
            return render(request, 'screener/signup.html', {'role': role})
            
        hashed_pw = make_password(password)
        
        try:
            if role == 'recruiter':
                if RecruiterAccount.objects.filter(username=username).exists() or RecruiterAccount.objects.filter(email=email).exists():
                    messages.error(request, "Username or Email already exists in Recruiter database.")
                    return render(request, 'screener/signup.html', {'role': role})
                RecruiterAccount.objects.create(username=username, email=email, password=hashed_pw)
            elif role == 'student':
                if StudentAccount.objects.filter(username=username).exists() or StudentAccount.objects.filter(email=email).exists():
                    messages.error(request, "Username or Email already exists in Student database.")
                    return render(request, 'screener/signup.html', {'role': role})
                StudentAccount.objects.create(username=username, email=email, password=hashed_pw)
            elif role == 'college':
                if CollegeAccount.objects.filter(username=username).exists() or CollegeAccount.objects.filter(email=email).exists():
                    messages.error(request, "Username or Email already exists in College database.")
                    return render(request, 'screener/signup.html', {'role': role})
                CollegeAccount.objects.create(username=username, email=email, password=hashed_pw)
            else:
                messages.error(request, "Invalid workspace role selected.")
                return render(request, 'screener/signup.html', {'role': role})
                
            messages.success(request, f"Account created successfully for {username}! Please log in.")
            return redirect(f"/login/?role={role}")
            
        except Exception as e:
            messages.error(request, f"Error creating account: {e}")
            return render(request, 'screener/signup.html', {'role': role})
            
    return render(request, 'screener/signup.html', {'role': role})


def login_view(request):
    role = request.GET.get('role', 'recruiter')
    if request.method == 'POST':
        role = request.POST.get('role', 'recruiter')
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        
        if not username or not password:
            messages.error(request, "Please enter both username and password.")
            return render(request, 'screener/login.html', {'role': role})
            
        user = None
        if role == 'recruiter':
            user = RecruiterAccount.objects.filter(username=username).first()
        elif role == 'student':
            user = StudentAccount.objects.filter(username=username).first()
        elif role == 'college':
            user = CollegeAccount.objects.filter(username=username).first()
            
        if user and check_password(password, user.password):
            request.session['user_id'] = user.id
            request.session['user_role'] = role
            request.session['username'] = user.username
            messages.success(request, f"Welcome back, {user.username}!")
            
            if role == 'recruiter':
                return redirect('recruiter_dashboard')
            elif role == 'student':
                return redirect('student_dashboard')
            elif role == 'college':
                return redirect('college_dashboard')
        else:
            messages.error(request, f"Invalid username or password in {role.capitalize()} workspace database.")
            return render(request, 'screener/login.html', {'role': role})
            
    return render(request, 'screener/login.html', {'role': role})


def logout_view(request):
    role = request.session.get('user_role', 'recruiter')
    request.session.flush()
    messages.success(request, "Logged out successfully.")
    return redirect(f"/login/?role={role}")
