from django.db import models
from django.contrib.auth.models import AbstractUser

# ----------------- Custom User -----------------
class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('team', 'Team'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    is_approved = models.BooleanField(default=False)

# ----------------- Admin Profile -----------------
class AdminProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    designation = models.CharField(max_length=100, default='Coordinator')

# ----------------- Team -----------------
class Team(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    total_points = models.IntegerField(default=0)
    # Add fields: college, district etc.
    def __str__(self): return self.name

# ----------------- Category -----------------
class Category(models.Model):
    name = models.CharField(max_length=100)
    def __str__(self): return self.name

# ----------------- Program -----------------
class Program(models.Model):
    name = models.CharField(max_length=100)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    
    def __str__(self): return f"{self.name} - {self.category.name}"

# ----------------- Contestant -----------------
class Contestant(models.Model):
    chest_no = models.PositiveIntegerField(unique=True, null=True)
    name = models.CharField(max_length=100)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, null=True)
    total_points = models.IntegerField(default=0)

    def __str__(self): return self.name

    def save(self, *args, **kwargs):
        if not self.chest_no:
            last = Contestant.objects.all().order_by('-chest_no').first()
            self.chest_no = 1020 if not last else last.chest_no + 1
        super().save(*args, **kwargs)

# ----------------- Participation -----------------
class Participation(models.Model):
    contestant = models.ForeignKey(Contestant, on_delete=models.CASCADE)
    program = models.ForeignKey(Program, on_delete=models.CASCADE)
    marks = models.IntegerField(null=True, blank=True)
    rank = models.PositiveIntegerField(null=True, blank=True)
    grade = models.CharField(max_length=1, null=True, blank=True)
    points_awarded = models.IntegerField(default=False)

# ----------------- Team Points -----------------
class TeamPoints(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    points = models.IntegerField(default=0)
