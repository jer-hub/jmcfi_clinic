from django.urls import path
from . import views


app_name = 'feedback'

urlpatterns = [
    # Feedback List
    path('', views.feedback_list, name='feedback_list'),
    
    # Feedback Statistics (Staff/Admin/Doctor only)
    path('stats/', views.feedback_stats, name='feedback_stats'),
    
    # Submit Feedback
    path('submit/', views.submit_feedback, name='submit_feedback'),
    path('submit/<int:appointment_id>/', views.submit_feedback, name='submit_feedback_appointment'),
]
