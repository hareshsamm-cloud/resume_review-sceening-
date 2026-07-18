import os
import re
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.contrib import messages
from django.core.mail import send_mail
from django.contrib.auth.hashers import make_password, check_password
from .models import Candidate, EmailLog, RecruiterAccount, StudentAccount, CollegeAccount, PlacementConfig, ReportedProfile
from .parser import extract_text_from_pdf, parse_resume_full
from .recommender import get_company_recommendations_by_role
from .validator import run_authenticity_audit
from .companies_data import COMPANIES_DATABASE

def get_rejections_after_upgrade(email):
    records = list(Candidate.objects.filter(email=email).order_by('id'))
    rejections_after_upgrade = 0
    prior_rejections = []
    
    for r in records:
        if r.decision == 'Rejected':
            r_skills = r.get_skills_list()
            # Check if this rejection happened after a prior rejection where skills were fewer or different
            for prev_r in prior_rejections:
                prev_skills = prev_r.get_skills_list()
                if len(r_skills) > len(prev_skills) or any(s not in prev_skills for s in r_skills):
                    rejections_after_upgrade += 1
                    break
            prior_rejections.append(r)
            
    return rejections_after_upgrade


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
        # Keep candidates submitted by registered students, delete only transient/recruiter files
        student_emails = list(StudentAccount.objects.values_list('email', flat=True))
        Candidate.objects.exclude(email__in=student_emails).delete()
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
        student_emails = list(StudentAccount.objects.values_list('email', flat=True))
        Candidate.objects.exclude(email__in=student_emails).delete()
        EmailLog.objects.all().delete()
        ReportedProfile.objects.exclude(email__in=student_emails).delete()
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

        # Run Anomaly / Authenticity Audits using our new modular validator
        is_suspicious, reasons, audit_scores = run_authenticity_audit(
            name=cand.name,
            email=cand.email,
            phone=cand.phone,
            skills=candidate_skills,
            experience_years=cand.experience_years,
            resume_text=cand.resume_text
        )
        cand.is_suspicious = is_suspicious
        cand.suspicious_reasons = reasons
        
        # Save assessment results to database
        cand.quality_score = audit_scores["quality_score"]
        cand.authenticity_score = audit_scores["authenticity_score"]
        cand.fraud_score = audit_scores["fraud_score"]
        cand.communication_score = audit_scores["communication_score"]
        cand.tech_depth_score = audit_scores["tech_depth_score"]
        cand.learning_score = audit_scores["learning_score"]

        # Calculate Explainability & Summary
        pos = []
        neg = []
        for s in matched_reqs:
            pos.append(f"+15 Skill matched: {s.capitalize()}")
        for s in candidate_skills:
            if s.lower() not in req_skills:
                pos.append(f"+5 Extra skill: {s}")
        if cand.experience_years >= min_exp:
            pos.append(f"+30 Meets experience requirement ({cand.experience_years} yrs)")
        else:
            neg.append(f"-10 Experience deficit of {round(min_exp - cand.experience_years, 1)} yrs")
        for s in req_skills:
            if s not in candidate_skills_lower:
                neg.append(f"-10 Lacks skill: {s.capitalize()}")
        
        cand.explainability_positive = "||".join(pos)
        cand.explainability_negative = "||".join(neg)

        # AI candidate summary
        skills_badge = ", ".join(candidate_skills[:4])
        rec_status = "highly recommended for technical review" if cand.match_score >= 80 else "recommended with reservations" if cand.match_score >= 50 else "not recommended for this role"
        cand.ai_summary = f"{cand.name} displays competence in {skills_badge or 'Software Engineering'} with {cand.experience_years} years of relevant experience. Their profile scored a {cand.match_score}% job match with a {cand.quality_score}% layout quality index and a low {cand.fraud_score}% fraud risk. They are {rec_status}."

        # Stress Test
        g_skills = ["python", "go", "java", "algorithms", "system design"]
        g_match = sum(1 for s in candidate_skills_lower if s in g_skills)
        g_score = round(0.7 * (g_match / len(g_skills) * 100) + 0.3 * (100 if cand.experience_years >= 4.0 else (cand.experience_years / 4.0 * 100)))
        
        a_skills = ["aws", "sql", "java", "docker", "kubernetes"]
        a_match = sum(1 for s in candidate_skills_lower if s in a_skills)
        a_score = round(0.7 * (a_match / len(a_skills) * 100) + 0.3 * (100 if cand.experience_years >= 3.0 else (cand.experience_years / 3.0 * 100)))

        s_skills = ["ruby", "python", "go", "apis", "react", "sql"]
        s_match = sum(1 for s in candidate_skills_lower if s in s_skills)
        s_score = round(0.7 * (s_match / len(s_skills) * 100) + 0.3 * (100 if cand.experience_years >= 3.0 else (cand.experience_years / 3.0 * 100)))

        m_skills = ["c#", "c++", "java", "azure", "sql", "git"]
        m_match = sum(1 for s in candidate_skills_lower if s in m_skills)
        m_score = round(0.7 * (m_match / len(m_skills) * 100) + 0.3 * (100 if cand.experience_years >= 2.0 else (cand.experience_years / 2.0 * 100)))

        z_skills = ["java", "php", "javascript", "html", "css", "sql"]
        z_match = sum(1 for s in candidate_skills_lower if s in z_skills)
        z_score = round(0.7 * (z_match / len(z_skills) * 100) + 0.3 * (100 if cand.experience_years >= 1.0 else (cand.experience_years / 1.0 * 100)))

        cand.stress_test_scores = f"Google:{max(35, g_score)}||Amazon:{max(35, a_score)}||Stripe:{max(35, s_score)}||Microsoft:{max(35, m_score)}||Zoho:{max(35, z_score)}"

        cand.save()
        
        # Create ReportedProfile if this candidate is suspicious and not already reported
        if cand.is_suspicious:
            if not ReportedProfile.objects.filter(email=cand.email).exists():
                student_acc = StudentAccount.objects.filter(email=cand.email).first()
                ReportedProfile.objects.create(
                    student=student_acc,
                    name=cand.name,
                    email=cand.email,
                    phone=cand.phone,
                    reasons="||".join(cand.suspicious_reasons),
                    resume_text=cand.resume_text
                )


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

    reported_profiles = ReportedProfile.objects.all().order_by('-reported_at')
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
        'all_candidates': all_candidates,
        'reported_profiles': reported_profiles
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
    
    rejections_after_upgrade = 0
    if student:
        rejections_after_upgrade = get_rejections_after_upgrade(student.email)

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
            cand_name = parsed["name"]
            # Use student's email as candidate email if matching to ensure linked account integrity
            cand_email = student.email if student else (parsed["email"] if parsed["email"] != "No email found" else f"{parsed['name'].lower().replace(' ', '')}@example.com")
            cand_phone = parsed["phone"]
            candidate_skills = parsed["skills"]
            candidate_exp = parsed["experience_years"]
            candidate_skills_lower = [s.lower() for s in candidate_skills]
            
            # Student-side Authenticity Checks using our new modular validator
            is_suspicious, reasons, audit_scores = run_authenticity_audit(
                name=cand_name,
                email=cand_email,
                phone=cand_phone,
                skills=candidate_skills,
                experience_years=candidate_exp,
                resume_text=text,
                file_obj=file
            )
            
            # Apply Anti-gaming Warnings & Block Blacklist
            if is_suspicious:
                if student:
                    student.fake_upload_count += 1
                    if student.fake_upload_count >= max_fake_limit:
                        student.is_blacklisted = True
                        student.save()
                        messages.error(request, f"Your account has been BLACKLISTED. You have uploaded {student.fake_upload_count} fake resumes (limit: {max_fake_limit}).")
                    else:
                        student.save()
                        messages.warning(request, f"Resume authenticity verification FAILED! Warning #{student.fake_upload_count} of {max_fake_limit} issued: {', '.join(reasons)}")
                    
                    # Create ReportedProfile record
                    ReportedProfile.objects.create(
                        student=student,
                        name=cand_name,
                        email=cand_email,
                        phone=cand_phone,
                        reasons="||".join(reasons),
                        resume_text=text
                    )
                return redirect('student_dashboard')

            else:
                if student:
                    messages.success(request, "Resume authenticity verified! No anomalies detected.")

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
                    
                selected_role_key = target_role or detected_role
                role_info = ROLES_DATABASE.get(selected_role_key, {})
                req_skills = [s.strip().lower() for s in role_info.get("skills", [])]
                min_exp = float(role_info.get("experience", 1.0))
                
                # Match score calculation
                matched_reqs = [r for r in req_skills if r in candidate_skills_lower]
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
                    impressive.append(f"Exceeds experience requirement with {candidate_exp} years")
                else:
                    impressive.append(f"Possesses {candidate_exp} years of relevant experience")
                    
                gaps = []
                missing_reqs = [r.capitalize() for r in req_skills if r not in candidate_skills_lower]
                if missing_reqs:
                    gaps.append(f"Lacks core technologies: {', '.join(missing_reqs[:4])}")
                if candidate_exp < min_exp:
                    gaps.append(f"Experience deficit: {round(min_exp - candidate_exp, 1)} years short")

                # Generate explainability points
                pos = []
                neg = []
                for s in matched_reqs:
                    pos.append(f"+15 Skill matched: {s.capitalize()}")
                for s in candidate_skills:
                    if s.lower() not in req_skills:
                        pos.append(f"+5 Extra skill: {s}")
                if candidate_exp >= min_exp:
                    pos.append(f"+30 Meets experience requirement ({candidate_exp} yrs)")
                else:
                    neg.append(f"-10 Experience deficit of {round(min_exp - candidate_exp, 1)} yrs")
                for s in req_skills:
                    if s not in candidate_skills_lower:
                        neg.append(f"-10 Lacks skill: {s.capitalize()}")
                
                explainability_positive = "||".join(pos)
                explainability_negative = "||".join(neg)

                # AI candidate summary
                skills_badge = ", ".join(candidate_skills[:4])
                rec_status = "highly recommended for technical review" if overall_score >= 80 else "recommended with reservations" if overall_score >= 50 else "not recommended for this role"
                ai_summary = f"{cand_name} displays competence in {skills_badge or 'Software Engineering'} with {candidate_exp} years of relevant experience. Their profile scored a {overall_score}% job match with a {audit_scores['quality_score']}% layout quality index and a low {audit_scores['fraud_score']}% fraud risk. They are {rec_status}."

                # Stress Test
                g_skills = ["python", "go", "java", "algorithms", "system design"]
                g_match = sum(1 for s in candidate_skills_lower if s in g_skills)
                g_score = round(0.7 * (g_match / len(g_skills) * 100) + 0.3 * (100 if candidate_exp >= 4.0 else (candidate_exp / 4.0 * 100)))
                
                a_skills = ["aws", "sql", "java", "docker", "kubernetes"]
                a_match = sum(1 for s in candidate_skills_lower if s in a_skills)
                a_score = round(0.7 * (a_match / len(a_skills) * 100) + 0.3 * (100 if candidate_exp >= 3.0 else (candidate_exp / 3.0 * 100)))

                s_skills = ["ruby", "python", "go", "apis", "react", "sql"]
                s_match = sum(1 for s in candidate_skills_lower if s in s_skills)
                s_score = round(0.7 * (s_match / len(s_skills) * 100) + 0.3 * (100 if candidate_exp >= 3.0 else (candidate_exp / 3.0 * 100)))

                m_skills = ["c#", "c++", "java", "azure", "sql", "git"]
                m_match = sum(1 for s in candidate_skills_lower if s in m_skills)
                m_score = round(0.7 * (m_match / len(m_skills) * 100) + 0.3 * (100 if candidate_exp >= 2.0 else (candidate_exp / 2.0 * 100)))

                z_skills = ["java", "php", "javascript", "html", "css", "sql"]
                z_match = sum(1 for s in candidate_skills_lower if s in z_skills)
                z_score = round(0.7 * (z_match / len(z_skills) * 100) + 0.3 * (100 if candidate_exp >= 1.0 else (candidate_exp / 1.0 * 100)))

                stress_test_scores = f"Google:{max(35, g_score)}||Amazon:{max(35, a_score)}||Stripe:{max(35, s_score)}||Microsoft:{max(35, m_score)}||Zoho:{max(35, z_score)}"

                # Create or update candidate record in the recruiter database
                existing_pending = Candidate.objects.filter(email=cand_email, decision="Pending").first()
                if existing_pending:
                    existing_pending.name = cand_name
                    existing_pending.phone = cand_phone
                    existing_pending.skills = ",".join(candidate_skills)
                    existing_pending.experience_years = candidate_exp
                    existing_pending.resume_text = text
                    existing_pending.match_score = overall_score
                    existing_pending.fit_assessment = fit
                    existing_pending.impressive_summary = "||".join(impressive)
                    existing_pending.requirements_needed = "||".join(gaps)
                    
                    # Update fingerprinting fields
                    existing_pending.quality_score = audit_scores["quality_score"]
                    existing_pending.authenticity_score = audit_scores["authenticity_score"]
                    existing_pending.fraud_score = audit_scores["fraud_score"]
                    existing_pending.communication_score = audit_scores["communication_score"]
                    existing_pending.tech_depth_score = audit_scores["tech_depth_score"]
                    existing_pending.learning_score = audit_scores["learning_score"]
                    existing_pending.explainability_positive = explainability_positive
                    existing_pending.explainability_negative = explainability_negative
                    existing_pending.ai_summary = ai_summary
                    existing_pending.stress_test_scores = stress_test_scores
                    existing_pending.save()
                else:
                    Candidate.objects.create(
                        name=cand_name,
                        email=cand_email,
                        phone=cand_phone,
                        skills=",".join(candidate_skills),
                        experience_years=candidate_exp,
                        resume_text=text,
                        match_score=overall_score,
                        fit_assessment=fit,
                        impressive_summary="||".join(impressive),
                        requirements_needed="||".join(gaps),
                        decision="Pending",
                        
                        # Set fingerprinting fields
                        quality_score=audit_scores["quality_score"],
                        authenticity_score=audit_scores["authenticity_score"],
                        fraud_score=audit_scores["fraud_score"],
                        communication_score=audit_scores["communication_score"],
                        tech_depth_score=audit_scores["tech_depth_score"],
                        learning_score=audit_scores["learning_score"],
                        explainability_positive=explainability_positive,
                        explainability_negative=explainability_negative,
                        ai_summary=ai_summary,
                        stress_test_scores=stress_test_scores
                    )

            session_profile = {
                "name": cand_name,
                "email": cand_email,
                "phone": cand_phone,
                "experience": candidate_exp,
                "skills": candidate_skills
            }
            request.session['student_profile'] = session_profile
            return redirect('student_dashboard')
            
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
        
        # Pre-create candidate record for Sarah Jenkins
        Candidate.objects.filter(email="sarah.jenkins@stanford.edu", decision="Pending").delete()
        Candidate.objects.create(
            name="Sarah Jenkins",
            email="sarah.jenkins@stanford.edu",
            phone="+1 (650) 499-1029",
            skills="React,TypeScript,HTML,CSS,APIs,Git,SQL",
            experience_years=2.5,
            resume_text="Resume of Sarah Jenkins. Sarah has 2.5 years of experience in front-end developments using React, TypeScript, HTML, CSS and APIs.",
            match_score=85,
            fit_assessment="Strong Match",
            impressive_summary="Matches required skills: React, TypeScript, HTML, CSS||Possesses 2.5 years of experience",
            requirements_needed="",
            decision="Pending",
            quality_score=92,
            authenticity_score=95,
            fraud_score=5,
            communication_score=88,
            tech_depth_score=78,
            learning_score=85,
            explainability_positive="+15 Skill matched: React||+15 Skill matched: TypeScript||+30 Meets experience requirement (2.5 yrs)",
            explainability_negative="",
            ai_summary="Sarah Jenkins displays high competence in React, TypeScript, HTML with 2.5 years of relevant experience. Her profile scored an 85% job match with a 92% layout quality index and a low 5% fraud risk. She is highly recommended.",
            stress_test_scores="Google:60||Amazon:75||Stripe:85||Microsoft:80||Zoho:90"
        )
        
        if not target_role:
            target_role = "frontend"
        return redirect('student_dashboard')

    cand_db = None
    if student:
        # Load from candidate database to sync session
        cand_db = Candidate.objects.filter(email=student.email, decision="Pending").first()
        if cand_db and not session_profile:
            session_profile = {
                "name": cand_db.name,
                "email": cand_db.email,
                "phone": cand_db.phone,
                "experience": cand_db.experience_years,
                "skills": cand_db.get_skills_list()
            }
            candidate_profile = session_profile

    if session_profile:
        candidate_profile = session_profile
        if not target_role:
            target_role = "frontend"
            
        eligible, aspirational = get_company_recommendations_by_role(
            candidate_profile["skills"], 
            candidate_profile["experience"], 
            target_role
        )
        
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

    # If matching database profile is still None but student is registered, see if we have any candidate matching student email
    if student and not cand_db:
        cand_db = Candidate.objects.filter(email=student.email).first()

    context = {
        'candidate_profile': candidate_profile,
        'eligible': eligible,
        'aspirational': aspirational,
        'summary_highlight': summary_highlight,
        'job_roles': JOB_ROLES,
        'target_role': target_role,
        'companies': COMPANIES_DATABASE,
        'student': student,
        'max_fake_limit': max_fake_limit,
        'rejections_after_upgrade': rejections_after_upgrade,
        'candidate': cand_db
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
    reported_profiles = ReportedProfile.objects.all().order_by('-reported_at')

    context = {
        'companies': COMPANIES_DATABASE,
        'config': config,
        'blacklisted_students': blacklisted_students,
        'warned_students': warned_students,
        'reported_profiles': reported_profiles
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
