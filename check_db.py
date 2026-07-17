import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'resume_screener.settings')
django.setup()

from screener.models import Candidate

candidates = Candidate.objects.all().order_by('-match_score')
print(f"Total Candidates: {len(candidates)}")
print(f"{'Name':<20} | {'Exp':<5} | {'Score':<5} | {'Fit':<12} | {'Skills'}")
print("-" * 80)
for c in candidates[:10]:
    print(f"{c.name:<20} | {c.experience_years:<5} | {c.match_score:<5} | {c.fit_assessment:<12} | {c.skills[:40]}")
