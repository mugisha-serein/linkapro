from django.contrib import admin
from .models import User, OAuthToken

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ["email", "first_name", "last_name", "role", "is_active", "is_verified", "created_at"]
    list_filter = ["role", "is_active", "is_verified"]
    search_fields = ["email", "first_name", "last_name"]

@admin.register(OAuthToken)
class OAuthTokenAdmin(admin.ModelAdmin):
    list_display = ["user", "provider", "provider_user_id", "expires_at"]
    list_filter = ["provider"]