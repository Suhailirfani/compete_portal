from django.db import models

# Create your models here.
from datetime import timezone
from django.db import models
from django.contrib.auth.models import AbstractUser
from core.models import User, AbstractUser

# ----------------- Team -----------------
class GirlsTeam(models.Model):
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
    is_group = models.BooleanField(default=False, null=True)

    def __str__(self): return f"{self.name} - {self.category.name}"

# ----------------- Contestant -----------------
class Contestant(models.Model):
    chest_no = models.PositiveIntegerField(unique=True, null=True)
    name = models.CharField(max_length=100)
    team = models.ForeignKey(GirlsTeam, on_delete=models.CASCADE, null=True, blank=True)
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
    points_awarded = models.BooleanField(default=False)
   
    def __str__(self):
        return f"{self.contestant.name} ({self.program.name})"    

# ----------------- Group Participation -----------------
class GroupParticipation(models.Model):
    program = models.ForeignKey(Program, on_delete=models.CASCADE)
    contestants = models.ManyToManyField(Contestant)
    team = models.ForeignKey(GirlsTeam, on_delete=models.CASCADE, null=True, blank=True)  # All contestants should be from same team
    group_name = models.CharField(max_length=200, blank=True)  # Optional group name
    marks = models.IntegerField(null=True, blank=True)
    rank = models.PositiveIntegerField(null=True, blank=True)
    grade = models.CharField(max_length=1, null=True, blank=True)
    points_awarded = models.BooleanField(default=False)

    def __str__(self):
        contestant_names = ", ".join([c.name for c in self.contestants.all()])
        return f"{contestant_names} ({self.program.name})"

    def get_contestant_names(self):
        return ", ".join([contestant.name for contestant in self.contestants.all()])

    def save(self, *args, **kwargs):
        # Validate that the program is a group program
        if not self.program.is_group:
            raise ValueError("Cannot create group participation for non-group program")
        super().save(*args, **kwargs)

    def clean(self):
        from django.core.exceptions import ValidationError
        
        # Check if program is group program
        if not self.program.is_group:
            raise ValidationError("This program is not a group program")
        
        # Check participant count (this will be validated in views/forms)
        if hasattr(self, 'contestants'):
            count = self.contestants.count()
            if count < self.program.min_participants or count > self.program.max_participants:
                raise ValidationError(
                    f"Number of participants must be between {self.program.min_participants} "
                    f"and {self.program.max_participants}"
                )

   

# ----------------- Team Points -----------------
class TeamPoints(models.Model):
    team = models.ForeignKey(GirlsTeam, on_delete=models.CASCADE)
    points = models.IntegerField(default=0)

# ----------------- Points Configuration -----------------
class PointsConfig(models.Model):
    """Configuration for points calculation"""
    # Rank-based points
    rank_1_points = models.IntegerField(default=10)
    rank_2_points = models.IntegerField(default=6)
    rank_3_points = models.IntegerField(default=3)
    
    # Grade-based points
    grade_a_points = models.IntegerField(default=10)
    grade_b_points = models.IntegerField(default=6)
    grade_c_points = models.IntegerField(default=3)
    
    # Grade thresholds
    grade_a_threshold = models.IntegerField(default=80)
    grade_b_threshold = models.IntegerField(default=70)
    grade_c_threshold = models.IntegerField(default=60)
    
    class Meta:
        # Ensure only one configuration exists
        verbose_name = "Points Configuration"
        verbose_name_plural = "Points Configuration"

    @classmethod
    def get_config(cls):
        """Get or create the points configuration"""
        config, created = cls.objects.get_or_create(id=1)
        return config
