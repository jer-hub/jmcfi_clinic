from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.db.models.functions import TruncMonth, TruncWeek
from django.utils import timezone
from datetime import timedelta

from .models import Feedback
from appointments.models import Appointment


@login_required
def feedback_list(request):
    """Display list of feedback."""
    if request.user.role == 'student':
        feedbacks_qs = Feedback.objects.filter(student=request.user).select_related('appointment')
    else:
        feedbacks_qs = Feedback.objects.all().select_related('student', 'appointment')

    paginator = Paginator(feedbacks_qs.order_by('-created_at'), 10)
    page = request.GET.get('page')
    feedbacks = paginator.get_page(page)
    
    return render(request, 'feedback/feedback_list.html', {'feedbacks': feedbacks})


@login_required
def submit_feedback(request, appointment_id=None):
    """Submit new feedback with enhanced form."""
    if request.user.role != 'student':
        messages.error(request, 'Only students can submit feedback.')
        return redirect('core:dashboard')
    
    appointment = None
    if appointment_id:
        appointment = get_object_or_404(Appointment, id=appointment_id, student=request.user)
    
    # Get recent completed appointments for selection
    recent_appointments = Appointment.objects.filter(
        student=request.user,
        status='completed'
    ).order_by('-date')[:10]
    
    if request.method == 'POST':
        feedback_type = request.POST.get('feedback_type', 'general')
        rating = request.POST.get('rating')
        staff_rating = request.POST.get('staff_rating')
        cleanliness_rating = request.POST.get('cleanliness_rating')
        wait_time_rating = request.POST.get('wait_time_rating')
        comments = request.POST.get('comments', '').strip()
        suggestions = request.POST.get('suggestions', '').strip()
        would_recommend = request.POST.get('would_recommend') == 'yes'
        is_anonymous = request.POST.get('is_anonymous') == 'on'
        selected_appointment_id = request.POST.get('appointment_id')
        
        # Validation
        errors = []
        if not rating:
            errors.append('Please provide an overall rating.')
        if not comments or len(comments) < 10:
            errors.append('Please provide comments (minimum 10 characters).')
        
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            # Get appointment if selected
            selected_appointment = appointment
            if selected_appointment_id and not appointment:
                try:
                    selected_appointment = Appointment.objects.get(
                        id=selected_appointment_id, 
                        student=request.user
                    )
                except Appointment.DoesNotExist:
                    selected_appointment = None
            
            Feedback.objects.create(
                student=request.user,
                appointment=selected_appointment,
                feedback_type=feedback_type,
                rating=int(rating),
                staff_rating=int(staff_rating) if staff_rating else None,
                cleanliness_rating=int(cleanliness_rating) if cleanliness_rating else None,
                wait_time_rating=int(wait_time_rating) if wait_time_rating else None,
                comments=comments,
                suggestions=suggestions,
                would_recommend=would_recommend,
                is_anonymous=is_anonymous
            )
            messages.success(request, 'Thank you for your valuable feedback! We appreciate you taking the time to help us improve.')
            return redirect('feedback:feedback_list')
    
    context = {
        'appointment': appointment,
        'recent_appointments': recent_appointments,
        'feedback_types': Feedback.FEEDBACK_TYPE_CHOICES,
    }
    return render(request, 'feedback/submit_feedback.html', context)


@login_required
def feedback_stats(request):
    """Display feedback statistics for staff, admin, and doctors."""
    # Only allow staff, admin, and doctors to view stats
    if request.user.role == 'student':
        messages.error(request, 'You do not have permission to view feedback statistics.')
        return redirect('feedback:feedback_list')
    
    # Date ranges
    today = timezone.now().date()
    last_7_days = today - timedelta(days=7)
    last_30_days = today - timedelta(days=30)
    last_90_days = today - timedelta(days=90)
    
    # Base queryset
    all_feedback = Feedback.objects.all()
    
    # Overall statistics
    total_feedback = all_feedback.count()
    
    # Average ratings
    avg_ratings = all_feedback.aggregate(
        overall=Avg('rating'),
        staff=Avg('staff_rating'),
        cleanliness=Avg('cleanliness_rating'),
        wait_time=Avg('wait_time_rating'),
    )
    
    # Rating distribution
    rating_distribution = []
    for i in range(1, 6):
        count = all_feedback.filter(rating=i).count()
        percentage = (count / total_feedback * 100) if total_feedback > 0 else 0
        rating_distribution.append({
            'rating': i,
            'count': count,
            'percentage': round(percentage, 1)
        })
    
    # Feedback by type
    feedback_by_type = all_feedback.values('feedback_type').annotate(
        count=Count('id'),
        avg_rating=Avg('rating')
    ).order_by('-count')
    
    # Add labels to feedback types
    type_labels = dict(Feedback.FEEDBACK_TYPE_CHOICES)
    for item in feedback_by_type:
        item['label'] = type_labels.get(item['feedback_type'], item['feedback_type'])
    
    # Recommendation stats
    recommend_yes = all_feedback.filter(would_recommend=True).count()
    recommend_no = all_feedback.filter(would_recommend=False).count()
    recommend_percentage = (recommend_yes / total_feedback * 100) if total_feedback > 0 else 0
    
    # Recent trends (last 30 days vs previous 30 days)
    recent_feedback = all_feedback.filter(created_at__date__gte=last_30_days)
    previous_feedback = all_feedback.filter(
        created_at__date__gte=last_90_days,
        created_at__date__lt=last_30_days
    )
    
    recent_avg = recent_feedback.aggregate(avg=Avg('rating'))['avg'] or 0
    previous_avg = previous_feedback.aggregate(avg=Avg('rating'))['avg'] or 0
    rating_trend = recent_avg - previous_avg
    
    recent_count = recent_feedback.count()
    previous_count = previous_feedback.count()
    # Normalize to same period (30 days)
    previous_count_normalized = previous_count / 2 if previous_count > 0 else 0
    count_trend_pct = ((recent_count - previous_count_normalized) / previous_count_normalized * 100) if previous_count_normalized > 0 else 0
    
    # Monthly trend data for chart (last 6 months)
    six_months_ago = today - timedelta(days=180)
    monthly_data = all_feedback.filter(
        created_at__date__gte=six_months_ago
    ).annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        count=Count('id'),
        avg_rating=Avg('rating')
    ).order_by('month')
    
    # Recent feedback (last 5)
    recent_feedbacks = all_feedback.select_related('student', 'appointment').order_by('-created_at')[:5]
    
    # Feedback needing attention (low ratings)
    low_rated_feedback = all_feedback.filter(rating__lte=2).select_related('student', 'appointment').order_by('-created_at')[:10]
    
    # Weekly summary
    this_week = all_feedback.filter(created_at__date__gte=last_7_days)
    weekly_stats = {
        'count': this_week.count(),
        'avg_rating': this_week.aggregate(avg=Avg('rating'))['avg'] or 0,
        'positive': this_week.filter(rating__gte=4).count(),
        'neutral': this_week.filter(rating=3).count(),
        'negative': this_week.filter(rating__lte=2).count(),
    }
    
    context = {
        'total_feedback': total_feedback,
        'avg_ratings': avg_ratings,
        'rating_distribution': rating_distribution,
        'feedback_by_type': feedback_by_type,
        'recommend_yes': recommend_yes,
        'recommend_no': recommend_no,
        'recommend_percentage': round(recommend_percentage, 1),
        'rating_trend': round(rating_trend, 2),
        'count_trend_pct': round(count_trend_pct, 1),
        'recent_count': recent_count,
        'monthly_data': list(monthly_data),
        'recent_feedbacks': recent_feedbacks,
        'low_rated_feedback': low_rated_feedback,
        'weekly_stats': weekly_stats,
    }
    
    return render(request, 'feedback/feedback_stats.html', context)
