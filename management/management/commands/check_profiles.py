# management/commands/check_profiles.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from management.utils import is_profile_complete, get_missing_profile_fields

User = get_user_model()

class Command(BaseCommand):
    help = 'Check for users with incomplete profiles'

    def add_arguments(self, parser):
        parser.add_argument(
            '--role',
            type=str,
            choices=['student', 'staff'],
            help='Check profiles for specific role only',
        )
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Create empty profiles for users without profiles',
        )

    def handle(self, *args, **options):
        role_filter = options.get('role')
        fix_profiles = options.get('fix', False)
        
        # Filter users by role if specified
        users = User.objects.exclude(role='admin')
        if role_filter:
            users = users.filter(role=role_filter)
        
        incomplete_users = []
        users_without_profiles = []
        
        for user in users:
            if not is_profile_complete(user):
                missing_fields = get_missing_profile_fields(user)
                
                if len(missing_fields) == (6 if user.role == 'student' else 3):
                    # User has no profile at all (student needs 6 fields, staff/doctor needs 3)
                    users_without_profiles.append(user)
                else:
                    # User has incomplete profile
                    incomplete_users.append((user, missing_fields))
        
        # Report findings
        self.stdout.write(
            self.style.SUCCESS(f'Profile Completeness Report')
        )
        self.stdout.write('-' * 40)
        
        if users_without_profiles:
            self.stdout.write(
                self.style.WARNING(f'Users without profiles ({len(users_without_profiles)}):')
            )
            for user in users_without_profiles:
                self.stdout.write(f'  - {user.get_full_name()} ({user.email}) - {user.role}')
            
            if fix_profiles:
                self.create_empty_profiles(users_without_profiles)
        else:
            self.stdout.write(
                self.style.SUCCESS('All users have profiles created')
            )
        
        if incomplete_users:
            self.stdout.write(
                self.style.WARNING(f'Users with incomplete profiles ({len(incomplete_users)}):')
            )
            for user, missing_fields in incomplete_users:
                self.stdout.write(
                    f'  - {user.get_full_name()} ({user.email}) - Missing: {", ".join(missing_fields)}'
                )
        else:
            self.stdout.write(
                self.style.SUCCESS('All existing profiles are complete')
            )
        
        total_users = users.count()
        complete_users = total_users - len(incomplete_users) - len(users_without_profiles)
        completion_rate = (complete_users / total_users * 100) if total_users > 0 else 0
        
        self.stdout.write('-' * 40)
        self.stdout.write(
            f'Completion Rate: {completion_rate:.1f}% ({complete_users}/{total_users})'
        )

    def create_empty_profiles(self, users):
        """Create empty profiles for users without profiles"""
        from management.models import StudentProfile, StaffProfile
        
        created_count = 0
        for user in users:
            try:
                if user.role == 'student':
                    StudentProfile.objects.get_or_create(
                        user=user,
                        defaults={
                            'student_id': f'TEMP_{user.id}',
                            'date_of_birth': None,
                            'phone': '',
                            'emergency_contact': '',
                            'emergency_phone': '',
                            'blood_type': '',
                        }
                    )
                elif user.role in ['staff', 'doctor']:
                    StaffProfile.objects.get_or_create(
                        user=user,
                        defaults={
                            'staff_id': f'TEMP_{user.id}',
                            'department': '',
                            'phone': '',
                        }
                    )
                created_count += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Failed to create profile for {user.email}: {e}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'Created {created_count} empty profiles')
        )
