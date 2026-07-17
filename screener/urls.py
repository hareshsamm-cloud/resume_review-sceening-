from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing_view, name='landing'),
    path('recruiter/', views.recruiter_dashboard, name='recruiter_dashboard'),
    path('student/', views.student_dashboard, name='student_dashboard'),
    path('decision/<int:candidate_id>/<str:decision_type>/', views.send_decision_email, name='send_decision_email'),
]
