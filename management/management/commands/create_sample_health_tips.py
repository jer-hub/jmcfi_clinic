from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from management.models import HealthTip

User = get_user_model()

class Command(BaseCommand):
    help = 'Create sample health tips for testing'

    def handle(self, *args, **options):
        # Get a staff user (create one if none exists)
        staff_user = User.objects.filter(role='staff').first()
        if not staff_user:
            self.stdout.write(self.style.ERROR('No staff users found. Please create a staff user first.'))
            return

        health_tips_data = [
            {
                'title': 'Stay Hydrated: The Key to Better Health',
                'content': '''Proper hydration is essential for maintaining good health, especially for students who spend long hours studying. Water makes up about 60% of our body weight and plays a crucial role in various bodily functions.

Benefits of staying hydrated:
• Improves brain function and concentration
• Helps maintain body temperature
• Aids in digestion and nutrient absorption
• Keeps skin healthy and glowing
• Prevents headaches and fatigue

How much water should you drink?
Aim for 8-10 glasses (2-2.5 liters) of water daily. Increase this amount if you're physically active or in hot weather.

Tips to stay hydrated:
• Carry a water bottle with you
• Set reminders on your phone
• Eat water-rich fruits and vegetables
• Start your day with a glass of water
• Drink water before, during, and after exercise

Remember: If your urine is dark yellow, you need to drink more water!''',
                'category': 'nutrition',
                'is_active': True
            },
            {
                'title': '5-Minute Stress-Relief Techniques for Students',
                'content': '''Student life can be overwhelming with exams, assignments, and social pressures. Here are quick stress-relief techniques you can use anywhere:

Deep Breathing (2 minutes):
• Breathe in through your nose for 4 counts
• Hold your breath for 4 counts
• Exhale through your mouth for 6 counts
• Repeat 5-10 times

Progressive Muscle Relaxation (3 minutes):
• Tense your shoulders for 5 seconds, then release
• Clench your fists for 5 seconds, then release
• Scrunch your face muscles, then relax
• Notice the difference between tension and relaxation

Quick Mindfulness Exercise (2 minutes):
• Name 5 things you can see
• Name 4 things you can touch
• Name 3 things you can hear
• Name 2 things you can smell
• Name 1 thing you can taste

These techniques activate your body's relaxation response and can be done between classes or during study breaks.''',
                'category': 'mental_health',
                'is_active': True
            },
            {
                'title': 'Proper Hand Washing: Your First Line of Defense',
                'content': '''Hand washing is one of the most effective ways to prevent the spread of infections. Here's how to do it properly:

When to wash your hands:
• Before eating or preparing food
• After using the restroom
• After coughing, sneezing, or blowing your nose
• After touching public surfaces
• Before and after caring for someone who is sick

Proper hand washing technique:
1. Wet your hands with clean, running water
2. Apply soap and lather by rubbing hands together
3. Scrub all surfaces: palms, backs, between fingers, under nails
4. Continue scrubbing for at least 20 seconds (sing "Happy Birthday" twice)
5. Rinse thoroughly under clean, running water
6. Dry with a clean towel or air dry

When soap and water aren't available:
Use hand sanitizer with at least 60% alcohol content. Apply to palm and rub all surfaces until hands are dry.

Remember: Clean hands save lives!''',
                'category': 'hygiene',
                'is_active': True
            },
            {
                'title': 'Desk Exercises to Combat Student Fatigue',
                'content': '''Sitting for long periods while studying can cause muscle tension, poor circulation, and fatigue. These simple exercises can be done right at your desk:

Neck and Shoulder Stretches (repeat 5 times each):
• Slowly roll your shoulders backward and forward
• Gently tilt your head to each side
• Look up at the ceiling, then down at your desk

Spinal Twists:
• Sit tall and place your right hand on your left knee
• Gently twist your torso to the left and hold for 15 seconds
• Repeat on the other side

Leg Exercises:
• Lift your knees toward your chest (seated marching)
• Extend one leg straight and flex your foot
• Circle your ankles clockwise and counterclockwise

Eye Exercises:
• Look at something 20 feet away for 20 seconds every 20 minutes
• Blink slowly and deliberately 10 times
• Cover your eyes with palms for 30 seconds

Aim to do these exercises every hour during long study sessions. Your body will thank you!''',
                'category': 'exercise',
                'is_active': True
            },
            {
                'title': 'Building Immunity: Foods That Fight Infections',
                'content': '''A strong immune system is your best defense against common illnesses. What you eat plays a crucial role in immune function:

Vitamin C Rich Foods:
• Citrus fruits (oranges, lemons, grapefruits)
• Bell peppers and broccoli
• Strawberries and kiwi
• Tomatoes

Vitamin D Sources:
• Fatty fish (salmon, mackerel, sardines)
• Fortified milk and cereals
• Egg yolks
• Sunlight exposure (15-20 minutes daily)

Zinc-Rich Foods:
• Nuts and seeds
• Legumes and beans
• Whole grains
• Lean meats

Immune-Boosting Habits:
• Eat a variety of colorful fruits and vegetables
• Include probiotic foods like yogurt and fermented vegetables
• Get adequate sleep (7-9 hours nightly)
• Exercise regularly but don't overdo it
• Manage stress levels
• Avoid excessive sugar and processed foods

Remember: A balanced diet is more effective than taking supplements alone.''',
                'category': 'prevention',
                'is_active': True
            },
            {
                'title': 'Basic First Aid: Treating Minor Cuts and Scrapes',
                'content': '''Knowing basic first aid can help you treat minor injuries effectively and prevent complications:

For Minor Cuts and Scrapes:

Step 1: Clean Your Hands
• Wash hands with soap and water or use hand sanitizer

Step 2: Stop the Bleeding
• Apply gentle pressure with a clean cloth or bandage
• Elevate the injured area above heart level if possible

Step 3: Clean the Wound
• Rinse with clean water to remove dirt and debris
• Don't use hydrogen peroxide or alcohol directly on the wound

Step 4: Apply Antibiotic Ointment
• Use a thin layer to prevent infection (if not allergic)

Step 5: Protect the Wound
• Cover with a sterile bandage or adhesive bandage
• Change the bandage daily or when it becomes wet

When to Seek Medical Attention:
• Deep cuts that won't stop bleeding
• Wounds with embedded objects
• Signs of infection (redness, warmth, pus, red streaks)
• If you haven't had a tetanus shot in 10 years

Keep a basic first aid kit in your dorm or apartment with bandages, antiseptic wipes, and pain relievers.''',
                'category': 'first_aid',
                'is_active': True
            }
        ]

        created_count = 0
        for tip_data in health_tips_data:
            # Check if tip already exists
            if not HealthTip.objects.filter(title=tip_data['title']).exists():
                HealthTip.objects.create(
                    created_by=staff_user,
                    **tip_data
                )
                created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created {created_count} health tip(s) by {staff_user.get_full_name()}'
            )
        )
