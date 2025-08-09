from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.
class User(AbstractUser):
    class ROLE(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        STAFF = 'staff', 'Staff'
        STUDENT = 'student', 'Student'
        # Add any additional fields you want for your user model
    
    role = models.CharField(
        max_length=10,
        choices=ROLE.choices,
        default=ROLE.STUDENT,)
    
    def is_admin(self):
        return self.role == self.ROLE.ADMIN
    
    def is_student(self):
        return self.role == self.ROLE.STUDENT
    
    def save(self, *args, **kwargs):
        # If is_staff is being set and role is not explicitly set, 
        # update role accordingly
        if hasattr(self, '_state') and self._state.adding and self.is_staff and self.role == self.ROLE.STUDENT:
            self.role = self.ROLE.STAFF
        super().save(*args, **kwargs)
    
