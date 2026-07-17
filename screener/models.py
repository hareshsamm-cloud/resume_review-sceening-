from django.db import models

class Candidate(models.Model):
    name = models.CharField(max_length=255, default="Unknown")
    email = models.CharField(max_length=255, default="No email found")
    phone = models.CharField(max_length=50, default="No phone found")
    skills = models.TextField(blank=True, default="")  # comma separated
    experience_years = models.FloatField(default=0.0)
    resume_text = models.TextField(blank=True, default="")
    
    # Recruiter screening specifics
    match_score = models.IntegerField(default=0)
    fit_assessment = models.CharField(max_length=50, default="Poor Match")
    impressive_summary = models.TextField(blank=True, default="")  # double pipes "||" separated
    requirements_needed = models.TextField(blank=True, default="")  # double pipes "||" separated
    
    scanned_at = models.DateTimeField(auto_now_add=True)
    decision = models.CharField(max_length=50, default="Pending")  # Pending, Accepted, Rejected

    def __str__(self):
        return self.name

    def get_skills_list(self):
        if not self.skills:
            return []
        return [s.strip() for s in self.skills.split(",") if s.strip()]

    def get_impressive_list(self):
        if not self.impressive_summary:
            return []
        return [i.strip() for i in self.impressive_summary.split("||") if i.strip()]

    def get_gaps_list(self):
        if not self.requirements_needed:
            return []
        return [g.strip() for g in self.requirements_needed.split("||") if g.strip()]

class EmailLog(models.Model):
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name="emails")
    recipient_email = models.CharField(max_length=255)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    status = models.CharField(max_length=50)  # Accepted or Rejected
    sent_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.status} email to {self.recipient_email} at {self.sent_at}"
