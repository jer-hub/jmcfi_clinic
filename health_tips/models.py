from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class HealthTip(models.Model):
    CATEGORY_CHOICES = [
        ('nutrition', 'Nutrition'),
        ('exercise', 'Exercise'),
        ('mental_health', 'Mental Health'),
        ('hygiene', 'Hygiene'),
        ('prevention', 'Disease Prevention'),
        ('first_aid', 'First Aid'),
    ]

    title = models.CharField(max_length=200)
    content = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='health_tips_created')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Health Tip'
        verbose_name_plural = 'Health Tips'
        # Mark as managed=False to prevent migrations from creating a new table

    def __str__(self):
        return self.title
