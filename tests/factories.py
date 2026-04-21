from django.utils import timezone
from datetime import date
import uuid

from django_app.identity.models import User
from django_app.events.models import Event, Checklist, ChecklistItem, BudgetLine, GuestEntry, TimelineBlock
from django_app.vendors.models import VendorProfile, PortfolioImage, ServicePackage, Inquiry
from django_app.documents.models import ExportJob


def create_user(**kwargs):
    defaults = {
        "email": f"user{uuid.uuid4().hex[:6]}@example.com",
        "first_name": "Test",
        "last_name": "User",
        "role": "planner",
        "is_active": True,
        "is_verified": True,
    }
    defaults.update(kwargs)
    return User.objects.create(**defaults)


def create_event(**kwargs):
    if "planner" not in kwargs:
        kwargs["planner"] = create_user()
    defaults = {
        "name": "Test Event",
        "event_type": "wedding",
        "event_date": date.today() + timezone.timedelta(days=30),
        "venue": "Test Venue",
        "expected_guests": 100,
        "total_budget": 5000.00,
    }
    defaults.update(kwargs)
    return Event.objects.create(**defaults)


def create_checklist(**kwargs):
    if "event" not in kwargs:
        kwargs["event"] = create_event()
    defaults = {"name": "Test Checklist"}
    defaults.update(kwargs)
    return Checklist.objects.create(**defaults)


def create_checklist_item(**kwargs):
    if "checklist" not in kwargs:
        kwargs["checklist"] = create_checklist()
    defaults = {
        "description": "Test item",
        "status": "pending",
        "order": 0,
    }
    defaults.update(kwargs)
    return ChecklistItem.objects.create(**defaults)


def create_budget_line(**kwargs):
    if "event" not in kwargs:
        kwargs["event"] = create_event()
    defaults = {
        "category": "catering",
        "description": "Food",
        "estimated_cost": 1000.00,
    }
    defaults.update(kwargs)
    return BudgetLine.objects.create(**defaults)


def create_guest(**kwargs):
    if "event" not in kwargs:
        kwargs["event"] = create_event()
    defaults = {
        "full_name": "John Doe",
        "email": "john@example.com",
        "rsvp_status": "pending",
        "dietary_restrictions": [],
    }
    defaults.update(kwargs)
    return GuestEntry.objects.create(**defaults)


def create_timeline_block(**kwargs):
    if "event" not in kwargs:
        kwargs["event"] = create_event()
    defaults = {
        "title": "Ceremony",
        "start_time": timezone.now(),
        "end_time": timezone.now() + timezone.timedelta(hours=1),
        "order": 0,
    }
    defaults.update(kwargs)
    return TimelineBlock.objects.create(**defaults)


def create_vendor_profile(**kwargs):
    if "user" not in kwargs:
        kwargs["user"] = create_user(role="vendor")
    defaults = {
        "business_name": "Test Vendor",
        "category": "photography",
        "description": "Description",
        "service_area": "Kigali",
        "contact_email": "vendor@example.com",
        "contact_phone": "123456789",
        "status": "draft",
    }
    defaults.update(kwargs)
    return VendorProfile.objects.create(**defaults)


def create_portfolio_image(**kwargs):
    if "vendor" not in kwargs:
        kwargs["vendor"] = create_vendor_profile()
    defaults = {
        "public_id": str(uuid.uuid4()),
        "secure_url": "https://example.com/image.jpg",
        "order": 0,
    }
    defaults.update(kwargs)
    return PortfolioImage.objects.create(**defaults)


def create_service_package(**kwargs):
    if "vendor" not in kwargs:
        kwargs["vendor"] = create_vendor_profile()
    defaults = {
        "name": "Basic Package",
        "description": "Description",
        "price": 1000.00,
        "currency": "RWF",
        "is_active": True,
    }
    defaults.update(kwargs)
    return ServicePackage.objects.create(**defaults)


def create_inquiry(**kwargs):
    if "vendor" not in kwargs:
        kwargs["vendor"] = create_vendor_profile()
    defaults = {
        "client_name": "Client Name",
        "client_email": "client@example.com",
        "message": "Inquiry message",
    }
    defaults.update(kwargs)
    return Inquiry.objects.create(**defaults)


def create_export_job(**kwargs):
    if "event" not in kwargs:
        kwargs["event"] = create_event()
    if "requested_by" not in kwargs:
        kwargs["requested_by"] = kwargs["event"].planner
    defaults = {
        "export_type": "event_brief",
        "status": "pending",
    }
    defaults.update(kwargs)
    return ExportJob.objects.create(**defaults)