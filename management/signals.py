# management/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from allauth.socialaccount.signals import social_account_added, pre_social_login
from .models import StudentProfile, StaffProfile
import requests
from django.core.files.base import ContentFile
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


def download_google_profile_picture(picture_url, user_id):
    """Download Google profile picture and return file"""
    try:
        logger.info(f"Downloading profile picture for user {user_id} from {picture_url}")
        response = requests.get(picture_url, timeout=10)
        if response.status_code == 200:
            filename = f'google_profile_{user_id}.jpg'
            logger.info(f"Successfully downloaded profile picture: {filename}")
            return ContentFile(response.content), filename
        else:
            logger.warning(f"Failed to download profile picture: HTTP {response.status_code}")
    except Exception as e:
        logger.error(f"Failed to download Google profile picture: {e}")
    return None, None


@receiver(pre_social_login)
def populate_user_from_google(sender, request, sociallogin, **kwargs):
    """
    Populate user data from Google before login/signup.
    This runs BEFORE the user is created or logged in.
    """
    if sociallogin.account.provider == 'google':
        user = sociallogin.user
        google_data = sociallogin.account.extra_data
        
        # Populate user model fields from Google data
        user.email = google_data.get('email', '')
        user.first_name = google_data.get('given_name', '')
        user.last_name = google_data.get('family_name', '')
        
        logger.info(f"Google OAuth data captured for {user.email}: "
                   f"Name: {user.first_name} {user.last_name}")


@receiver(social_account_added)
def create_profile_from_google(sender, request, sociallogin, **kwargs):
    """
    Create and populate profile after social account is added.
    This runs AFTER the user is created and saved.
    """
    if sociallogin.account.provider == 'google':
        user = sociallogin.user
        google_data = sociallogin.account.extra_data
        
        logger.info(f"Creating profile for user {user.id} ({user.email}) with role: {user.role}")
        
        # Extract data from Google
        email = google_data.get('email', '')
        email_username = email.split('@')[0] if '@' in email else ''
        picture_url = google_data.get('picture', '')
        
        # Generate better ID from email username
        generated_id = email_username.upper().replace('.', '_') if email_username else f'TEMP_{user.id}'
        
        # Create profile based on user role
        if user.role == 'student':
            try:
                profile, created = StudentProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        'student_id': generated_id,
                        'date_of_birth': None,
                        'phone': '',
                        'emergency_contact': '',
                        'emergency_phone': '',
                        'blood_type': None,
                        'allergies': '',
                        'medical_conditions': '',
                    }
                )
                
                if created:
                    logger.info(f"Created StudentProfile with ID: {profile.student_id}")
                    
                    # Download and save profile picture
                    if picture_url:
                        image_content, filename = download_google_profile_picture(picture_url, user.id)
                        if image_content and filename:
                            profile.profile_image.save(filename, image_content, save=True)
                            logger.info(f"Saved profile picture for student {user.email}")
                        
            except Exception as e:
                logger.error(f"Error creating StudentProfile for {user.email}: {e}")
                
        elif user.role in ['staff', 'doctor']:
            try:
                profile, created = StaffProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        'staff_id': generated_id,
                        'date_of_birth': None,
                        'phone': '',
                        'emergency_contact': '',
                        'emergency_phone': '',
                        'blood_type': None,
                        'allergies': '',
                        'medical_conditions': '',
                        'department': '',
                        'specialization': '',
                        'license_number': '',
                    }
                )
                
                if created:
                    logger.info(f"Created StaffProfile with ID: {profile.staff_id}")
                    
                    # Download and save profile picture
                    if picture_url:
                        image_content, filename = download_google_profile_picture(picture_url, user.id)
                        if image_content and filename:
                            profile.profile_image.save(filename, image_content, save=True)
                            logger.info(f"Saved profile picture for staff {user.email}")
                        
            except Exception as e:
                logger.error(f"Error creating StaffProfile for {user.email}: {e}")


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Fallback: Create profile when user is created (for non-Google signups).
    This ensures profiles are created even if social_account_added doesn't fire.
    """
    if created and instance.role in ['student', 'staff', 'doctor']:
        if instance.role == 'student':
            if not hasattr(instance, 'student_profile'):
                StudentProfile.objects.get_or_create(
                    user=instance,
                    defaults={
                        'student_id': f'TEMP_{instance.id}',
                        'date_of_birth': None,
                        'phone': '',
                        'emergency_contact': '',
                        'emergency_phone': '',
                        'blood_type': None,
                    }
                )
        elif instance.role in ['staff', 'doctor']:
            if not hasattr(instance, 'staff_profile'):
                StaffProfile.objects.get_or_create(
                    user=instance,
                    defaults={
                        'staff_id': f'TEMP_{instance.id}',
                        'department': '',
                        'phone': '',
                    }
                )


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save profile when user is saved"""
    if instance.role == 'student' and hasattr(instance, 'student_profile'):
        instance.student_profile.save()
    elif instance.role in ['staff', 'doctor'] and hasattr(instance, 'staff_profile'):
        instance.staff_profile.save()
