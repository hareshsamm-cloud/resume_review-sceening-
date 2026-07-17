import os
import re
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.contrib import messages
from django.core.mail import send_mail
from .models import Candidate, EmailLog
from .parser import extract_text_from_pdf, parse_resume_full
from .recommender import get_company_recommendations_by_role

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

    if request.method == 'POST' and 'upload_resumes' in request.FILES:
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
                "skills": "React,TypeScript,HTML,CSS,Node.js,Django,PostgreSQL,AWS,Docker,Kubernetes,PyTorch,Solidity,Unity,C#,Terraform,Git",
                "experience_years": 3.2,
                "resume_text": "Resume of Lucas Vance. Claims expert mastery in React, TypeScript, HTML, CSS, Node.js, Django, PostgreSQL, AWS, Docker, Kubernetes, PyTorch, Solidity, Unity, C#, Terraform, Git."
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
        
        # Heuristic 1: Keyword Stuffing (excessive tech stack keywords)
        if len(candidate_skills) > 9:
            cand.is_suspicious = True
            cand.suspicious_reasons.append(f"Abnormally high skill density ({len(candidate_skills)} unique frameworks). Potential keyword stuffing.")
            
        # Heuristic 2: Senior target role experience mismatch
        current_role_title = JOB_ROLES.get(selected_role_key, {}).get("title", "")
        if ("Architect" in current_role_title or "Lead" in current_role_title or "Senior" in current_role_title) and cand.experience_years < 2.0:
            cand.is_suspicious = True
            cand.suspicious_reasons.append(f"Targeting a senior/architect role with only {cand.experience_years} years of parsed experience.")
            
        # Heuristic 3: Missing primary contact details
        if cand.email == "No email found" or cand.phone == "No phone found":
            cand.is_suspicious = True
            cand.suspicious_reasons.append("Missing primary candidate contact details (Email/Phone).")

        # Heuristic 5: Timeline Plausibility Anomaly (Inflated GenAI experience)
        resume_lower = cand.resume_text.lower()
        genai_buzzwords = ["chatgpt", "gpt-4", "prompt engineering", "langchain", "llama"]
        if any(buzz in resume_lower for buzz in genai_buzzwords) and cand.experience_years > 4.0:
            regex_genai = r'(?:4|5|6|7|8|9|\d{2,})\+?\s*(?:years?|yrs?)[^.\n]*(?:chatgpt|gpt-4|prompt engineering|langchain|llama|generative ai)'
            if re.search(regex_genai, resume_lower):
                cand.is_suspicious = True
                cand.suspicious_reasons.append("Timeline Anomaly: Claims >4 years of experience in post-2022 Generative AI/LLMs.")

        # Heuristic 6: Cross-Domain Tech Conflict (Conflicting profiles)
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
            cand.suspicious_reasons.append(f"Multi-Stack Anomaly: Claims expert proficiency in {active_domains} unrelated domains (Web, AI, Blockchain, Game Dev).")

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
    candidate_profile = None
    eligible = []
    aspirational = []
    summary_highlight = ""
    target_role = request.POST.get('target_role', '') if request.method == 'POST' else request.GET.get('target_role', '')
    
    # Store temporary session profile info to allow dynamic target role toggling
    session_profile = request.session.get('student_profile')

    if request.method == 'POST' and 'upload_resume' in request.FILES:
        file = request.FILES['resume']
        text = ""
        
        if file.name.endswith('.pdf'):
            text = extract_text_from_pdf(file)
        elif file.name.endswith('.txt'):
            text = file.read().decode('utf-8', errors='ignore')
            
        if text.strip():
            parsed = parse_resume_full(text)
            
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
                "name": parsed["name"] if parsed["name"] != "Unknown Candidate" else os.path.splitext(file.name)[0].replace('_', ' ').replace('-', ' ').title(),
                "email": parsed["email"],
                "phone": parsed["phone"],
                "experience": parsed["experience_years"],
                "skills": parsed["skills"]
            }
            request.session['student_profile'] = session_profile
            
    elif request.method == 'POST' and 'load_student_demo' in request.POST:
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
        'target_role': target_role
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
