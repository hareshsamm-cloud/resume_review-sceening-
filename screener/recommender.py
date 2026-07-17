from .roles_data import ROLES_DATABASE

COMPANIES_BASE = [
    {
        "name": "Stripe",
        "logo_url": "https://cdn.brandfolder.io/5H442UZP/at/px78t7-2487t8-6zcf92/Stripe_Logo_-_Glyph_Blue.png",
        "description": "Financial infrastructure for the internet. Stripe values clean code, product craftsmanship, and attention to detail.",
        "difficulty": "Hard"
    },
    {
        "name": "Google",
        "logo_url": "https://img.icons8.com/color/512/google-logo.png",
        "description": "Organizing the world's information. Google heavily prioritizes core computer science fundamentals, scalability, and algorithms.",
        "difficulty": "Elite"
    },
    {
        "name": "Netflix",
        "logo_url": "https://img.icons8.com/color/512/netflix.png",
        "description": "Leading global streaming service. Netflix hires top talent with emphasis on distributed systems, high operational efficiency, and freedom.",
        "difficulty": "Elite"
    },
    {
        "name": "Microsoft",
        "logo_url": "https://img.icons8.com/color/512/microsoft.png",
        "description": "Empowering every person on the planet. Microsoft offers diverse technical paths spanning developer tools, systems, and global cloud networks.",
        "difficulty": "Medium"
    },
    {
        "name": "Airbnb",
        "logo_url": "https://img.icons8.com/color/512/airbnb.png",
        "description": "Belong anywhere. Airbnb focuses heavily on creative UI designs, graphic excellence, and highly reliable consumer systems.",
        "difficulty": "Hard"
    },
    {
        "name": "Amazon",
        "logo_url": "https://img.icons8.com/color/512/amazon.png",
        "description": "Earth's most customer-centric company. Amazon prioritizes operational excellence, system scalability, and distributed database models.",
        "difficulty": "Medium"
    }
]

def get_company_recommendations_by_role(candidate_skills, candidate_exp, role_name):
    """
    Evaluates candidate's alignment against top companies for a specific role.
    """
    eligible = []
    aspirational = []
    
    # Normalize candidate skills
    candidate_skills_lower = [s.lower() for s in candidate_skills]
    
    # Get base role data
    role_info = ROLES_DATABASE.get(role_name)
    if not role_info:
        role_info = ROLES_DATABASE["frontend"]
        role_name = "frontend"
        
    for comp in COMPANIES_BASE:
        difficulty = comp["difficulty"]
        name = comp["name"]
        
        # Adjust experience requirement based on company tier
        base_exp = role_info["experience"]
        if difficulty == "Elite":
            min_exp = base_exp + 2.0
        elif difficulty == "Hard":
            min_exp = base_exp + 1.0
        else: # Medium
            min_exp = base_exp
            
        # Select required skills for this role: top 5 skills of the role
        req_skills = list(role_info["skills"][:5])
        
        # Inject company-specific technology constraints to make it highly realistic
        if name in ["Netflix", "Amazon", "Airbnb"]:
            # AWS cloud
            if "AWS" not in req_skills and len(req_skills) < 6:
                req_skills.append("AWS")
        elif name == "Microsoft":
            # Azure cloud
            if "Azure" not in req_skills and len(req_skills) < 6:
                req_skills.append("Azure")
        elif name == "Google":
            # GCP cloud
            if "GCP" not in req_skills and len(req_skills) < 6:
                req_skills.append("GCP")
                
        # Skill Alignment
        skills_matched = [s for s in req_skills if s.lower() in candidate_skills_lower]
        skills_missing = [s for s in req_skills if s.lower() not in candidate_skills_lower]
        
        skill_score = (len(skills_matched) / len(req_skills)) * 100 if req_skills else 100
        
        # Experience Alignment
        if candidate_exp >= min_exp:
            exp_score = 100
        else:
            exp_score = (candidate_exp / min_exp) * 100 if min_exp > 0 else 100
            
        # Overall Score: 70% skills + 30% experience
        overall_score = round(0.7 * skill_score + 0.3 * exp_score)
        
        # Experience Gap
        exp_gap = max(0.0, round(min_exp - candidate_exp, 1))
        
        comp_result = {
            "name": name,
            "logo_url": comp["logo_url"],
            "description": comp["description"],
            "difficulty": difficulty,
            "min_experience": min_exp,
            "required_skills": req_skills,
            "matched_skills": skills_matched,
            "missing_skills": skills_missing,
            "match_score": overall_score,
            "exp_gap": exp_gap,
            "is_exp_aligned": candidate_exp >= min_exp
        }
        
        # Threshold: 75% for eligibility
        if overall_score >= 75:
            eligible.append(comp_result)
        else:
            aspirational.append(comp_result)
            
    # Sort both lists by score descending
    eligible.sort(key=lambda x: x["match_score"], reverse=True)
    aspirational.sort(key=lambda x: x["match_score"], reverse=True)
    
    return eligible, aspirational
