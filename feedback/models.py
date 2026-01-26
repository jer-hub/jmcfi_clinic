from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator

User = get_user_model()


class Feedback(models.Model):
    """Model for patient/student feedback about clinic services."""
    
    RATING_CHOICES = [
        (1, '1 - Poor'),
        (2, '2 - Fair'),
        (3, '3 - Good'),
        (4, '4 - Very Good'),
        (5, '5 - Excellent'),
    ]
    
    FEEDBACK_TYPE_CHOICES = [
        ('general', 'General Feedback'),
        ('appointment', 'Appointment Experience'),
        ('staff', 'Staff Service'),
        ('facility', 'Facility & Cleanliness'),
        ('wait_time', 'Wait Time'),
        ('treatment', 'Treatment Quality'),
        ('other', 'Other'),
    ]

    student = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='feedback_submissions'
    )
    appointment = models.ForeignKey(
        'appointments.Appointment', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='feedback_entries'
    )
    feedback_type = models.CharField(
        max_length=20,
        choices=FEEDBACK_TYPE_CHOICES,
        default='general'
    )
    rating = models.IntegerField(
        choices=RATING_CHOICES, 
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    # Specific ratings
    staff_rating = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rate staff friendliness and professionalism"
    )
    cleanliness_rating = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rate facility cleanliness"
    )
    wait_time_rating = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rate wait time satisfaction"
    )
    comments = models.TextField()
    suggestions = models.TextField(blank=True)
    would_recommend = models.BooleanField(default=True, help_text="Would you recommend our clinic?")
    is_anonymous = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Feedback'
        verbose_name_plural = 'Feedbacks'

    def __str__(self):
        name = f"{self.student.first_name} {self.student.last_name}".strip()
        if not name:
            name = self.student.email or self.student.username
        return f"Feedback from {name} - {self.rating}/5"
    
    @property
    def average_rating(self):
        """Calculate average of all ratings."""
        ratings = [self.rating]
        if self.staff_rating:
            ratings.append(self.staff_rating)
        if self.cleanliness_rating:
            ratings.append(self.cleanliness_rating)
        if self.wait_time_rating:
            ratings.append(self.wait_time_rating)
        return sum(ratings) / len(ratings)
