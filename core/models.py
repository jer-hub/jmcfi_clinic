from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.
class User(AbstractUser):
    # Override username to make it optional
    username = models.CharField(
        max_length=150,
        unique=True,
        blank=True,
        null=True,
        default=None,
        help_text='Optional. 150 characters or fewer. Letters, digits and @/./+/-/_ only.',
    )
    
    # Use email as the primary identifier
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []  # Remove username from required fields
    
    # Make email required and unique
    email = models.EmailField(unique=True)
    
    class ROLE(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        DOCTOR = 'doctor', 'Doctor'
        STAFF = 'staff', 'Staff'
        STUDENT = 'student', 'Student'
        # Add any additional fields you want for your user model
    
    role = models.CharField(
        max_length=10,
        choices=ROLE.choices,
        default=ROLE.STUDENT,)
    
    def is_admin(self):
        return self.role == self.ROLE.ADMIN
    
    def is_doctor(self):
        return self.role == self.ROLE.DOCTOR
    
    def is_staff(self):
        return self.role == self.ROLE.STAFF
    
    def is_student(self):
        return self.role == self.ROLE.STUDENT
    
    def __str__(self):
        if self.first_name or self.last_name:
            return f"{self.first_name} {self.last_name}".strip()
        return self.email or self.username or f"User {self.id}"
    
    def save(self, *args, **kwargs):
        # If is_staff is being set and role is not explicitly set, 
        # update role accordingly
        if hasattr(self, '_state') and self._state.adding and self.is_staff:
            if self.role == self.ROLE.STUDENT:
                self.role = self.ROLE.STAFF
        super().save(*args, **kwargs)
    
