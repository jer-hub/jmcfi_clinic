from django.contrib import admin
from django.contrib.auth import get_user_model
# Register your models here.

User = get_user_model()

@admin.register(User)  # Replace CoreModel with your actual model
class UserAdmin(admin.ModelAdmin):
    list_display = ('id', 'first_name', 'last_name', 'email')
    search_fields = ('first_name', 'last_name', 'email')
