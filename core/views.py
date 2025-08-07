from django.shortcuts import render

# Create your views here.
# competition_app/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import *
from .forms import ContestantForm, ParticipationForm, TeamForm
from .utils import get_grade, POINTS_FOR_RANK, POINTS_FOR_GRADE
from django.db.models import Count, Sum
from django.contrib.auth import logout
# views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test

User = get_user_model()

def is_admin(user):
    return user.is_superuser  # or use your custom check

# @login_required
# def dashboard_admin(request):
#     if request.user.role != 'admin': return redirect('dashboard_team')
#     programs = Program.objects.all()
#     teams = Team.objects.all()
#     return render(request, 'dashboard_admin.html', {'programs': programs, 'teams': teams})

@login_required
def dashboard_admin(request):
    programs = Program.objects.all()
    teams = Team.objects.all()
    pending_users = User.objects.filter(is_approved=False, is_superuser=False)
    context = {
        'programs': programs,
        'teams': teams,
        'pending_users': pending_users,
    }
    return render(request, 'dashboard_admin.html', context)


@login_required
def dashboard_team(request):
    if request.user.role != 'team': return redirect('dashboard_admin')
    team = request.user.team
    # In your view
    contestants = Contestant.objects.filter(team=team).order_by('category', 'name')
    return render(request, 'dashboard_team.html', {
        'contestants': contestants,
        'team': team
        })

@login_required
def add_contestant(request):
    if request.method == 'POST':
        form = ContestantForm(request.POST)
        if form.is_valid():
            contestant = form.save(commit=False)
            contestant.team = request.user.team
            contestant.save()
            return redirect('dashboard_team')
    else:
        form = ContestantForm()
    return render(request, 'add_contestant.html', {'form': form})

@login_required
def enter_marks_summary(request):
    if request.user.role != 'admin':
        return redirect('dashboard_team')
    
    # Get filter parameter
    program_id = request.GET.get('program')
    
    # Get all programs for the filter dropdown
    programs = Program.objects.all().order_by('name')
    
    # Filter participations based on program selection
    if program_id:
        participations = Participation.objects.filter(
            marks__isnull=False, 
            program_id=program_id
        ).order_by('-marks')
        selected_program = Program.objects.get(id=program_id)
    else:
        participations = Participation.objects.filter(
            marks__isnull=False
        ).order_by('program__name', '-marks')
        selected_program = None
    
    # Calculate ranks and grades for all programs (or selected program)
    if program_id:
        # Calculate for selected program only
        program_participations = Participation.objects.filter(
            program_id=program_id, 
            marks__isnull=False
        ).order_by('-marks')
        
        for i, p in enumerate(program_participations, 1):
            p.rank = i
            p.grade = get_grade(p.marks)
            
            if not p.points_awarded and p.grade:
                rank_points = POINTS_FOR_RANK.get(p.rank, 0)
                grade_points = POINTS_FOR_GRADE.get(p.grade, 0)
                total_points = rank_points + grade_points
                
                tp, created = TeamPoints.objects.get_or_create(team=p.contestant.team)
                tp.points += total_points
                tp.save()
                p.points_awarded = True
            
            p.save()
    else:
        # Calculate for all programs
        for program in Program.objects.all():
            program_participations = Participation.objects.filter(
                program=program, 
                marks__isnull=False
            ).order_by('-marks')
            
            for i, p in enumerate(program_participations, 1):
                p.rank = i
                p.grade = get_grade(p.marks)
                
                if not p.points_awarded and p.grade:
                    rank_points = POINTS_FOR_RANK.get(p.rank, 0)
                    grade_points = POINTS_FOR_GRADE.get(p.grade, 0)
                    total_points = rank_points + grade_points
                    
                    tp, created = TeamPoints.objects.get_or_create(team=p.contestant.team)
                    tp.points += total_points
                    tp.save()
                    p.points_awarded = True
                
                p.save()
    
    # Add calculated points to each participation for template display
    for p in participations:
        if p.points_awarded and p.grade:
            rank_points = POINTS_FOR_RANK.get(p.rank, 0)
            grade_points = POINTS_FOR_GRADE.get(p.grade, 0)
            p.total_points = rank_points + grade_points
            p.rank_points = rank_points
            p.grade_points = grade_points
        else:
            p.total_points = 0
            p.rank_points = 0
            p.grade_points = 0
    
    return render(request, 'enter_marks.html', {
        'participations': participations,
        'programs': programs,
        'selected_program': selected_program,
        'program_id': program_id,
    })

@login_required
def team_marks_summary(request):
    # Only allow team users
    if request.user.role != 'team':
        return redirect('dashboard_admin')

    # Get the team of the logged-in user
    team = request.user.team

    # Get all participations of this team where marks are given
    participations = Participation.objects.filter(
        contestant__team=team,
        marks__isnull=False
    ).select_related('program', 'contestant').order_by('program__name', '-marks')

    # Calculate ranks and grades within each program
    for program in Program.objects.all():
        program_participations = Participation.objects.filter(
            program=program,
            marks__isnull=False
        ).order_by('-marks')

        for i, p in enumerate(program_participations, 1):
            if p.contestant.team == team:
                p.rank = i
                p.grade = get_grade(p.marks)
                if p.points_awarded and p.grade:
                    rank_points = POINTS_FOR_RANK.get(p.rank, 0)
                    grade_points = POINTS_FOR_GRADE.get(p.grade, 0)
                    p.total_points = rank_points + grade_points
                else:
                    p.total_points = 0

    # Add display points
    for p in participations:
        if p.points_awarded and p.grade:
            rank_points = POINTS_FOR_RANK.get(p.rank, 0)
            grade_points = POINTS_FOR_GRADE.get(p.grade, 0)
            p.total_points = rank_points + grade_points
            p.rank_points = rank_points
            p.grade_points = grade_points
        else:
            p.total_points = 0
            p.rank_points = 0
            p.grade_points = 0

    return render(request, 'team_marks_summary.html', {
        'team': team,
        'participations': participations,
    })


import xlwt
from django.http import HttpResponse

@login_required
def results_view(request):
    participations = Participation.objects.filter(marks__isnull=False).select_related('program', 'contestant', 'contestant__team')
    return render(request, 'results.html', {'participations': participations})

@login_required
def export_excel(request):
    response = HttpResponse(content_type='application/ms-excel')
    response['Content-Disposition'] = 'attachment; filename="competition_results.xls"'

    wb = xlwt.Workbook(encoding='utf-8')
    ws = wb.add_sheet('Results')

    columns = ['Program', 'Contestant', 'Team', 'Marks', 'Grade', 'Rank']
    for col_num in range(len(columns)):
        ws.write(0, col_num, columns[col_num])

    rows = Participation.objects.filter(marks__isnull=False).values_list(
        'program__name', 'contestant__name', 'contestant__team__name',
        'marks', 'grade', 'rank'
    )
    for row_num, row in enumerate(rows, start=1):
        for col_num, value in enumerate(row):
            ws.write(row_num, col_num, value)

    wb.save(response)
    return response

@login_required
def leaderboard(request):
    teams = TeamPoints.objects.select_related('team').order_by('-points')
    return render(request, 'leaderboard.html', {'teams': teams})


from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required


def landing_view(request):
    return render(request, 'landing.html')

from django.contrib.auth import authenticate, login
from django.shortcuts import redirect, render
from django.contrib import messages

def custom_login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            if not user.is_approved:
                messages.error(request, 'Account pending approval by admin.')
                return redirect('login')

            login(request, user)

            # role-based redirect
            if user.is_superuser or user.role == 'admin':
                return redirect('dashboard_admin')
            elif user.role == 'team':
                return redirect('dashboard_team')
            else:
                messages.error(request, 'Unknown role.')
                return redirect('login')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'login.html')

from django.contrib.auth import get_user_model
User = get_user_model()

def signup_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        role = request.POST.get('role')

        user = User.objects.create_user(
            username=username,
            password=password,
            role=role,
            is_active=True,  # still needed to be True for Django auth
            is_approved=False  # requires admin approval
        )
        messages.success(request, "Account created! Wait for admin approval.")
        return redirect('login')

    return render(request, 'signup.html')


def custom_logout_view(request):
    logout(request)
    return redirect('landing') 



@login_required
@user_passes_test(is_admin)
def pending_users(request):
    users = User.objects.filter(is_approved=False, is_superuser=False)
    return render(request, 'pending_users.html', {'users': users})

@login_required
@user_passes_test(is_admin)
def approve_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    user.is_approved = True
    user.save()
    return redirect('pending_users')

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.core.paginator import Paginator


User = get_user_model()

@staff_member_required
def view_users(request):
    query = request.GET.get('q')
    role = request.GET.get('role')

    users = User.objects.all()

    if query:
        users = users.filter(Q(username__icontains=query) | Q(email__icontains=query))
    if role:
        users = users.filter(role=role)

    paginator = Paginator(users, 4)  # 10 per page
    page = request.GET.get('page')
    users = paginator.get_page(page)

    return render(request, 'view_users.html', {
        'users': users,
        'search_term': query or '',
        'selected_role': role or '',
    })

@staff_member_required
def delete_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    user.delete()
    return redirect('view_users')


from django.contrib import messages

@staff_member_required
def edit_user(request, user_id):
    user = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        user.username = request.POST.get('username')
        user.email = request.POST.get('email')
        user.role = request.POST.get('role')
        user.is_active = 'is_active' in request.POST
        user.save()
        messages.success(request, 'User updated successfully.')
        return redirect('view_users')

    return render(request, 'edit_user.html', {'user': user})


from .models import Program, Category


# add categroy by admin
from .models import Category

@login_required
def add_category(request):
    if request.user.role != 'admin':
        return redirect('dashboard_team')  # or wherever non-admins should go

    if request.method == 'POST':
        name = request.POST.get('name').strip()
        if name:
            if Category.objects.filter(name__iexact=name).exists():
                messages.warning(request, f"Category '{name}' already exists.")
            else:
                Category.objects.create(name=name)
                messages.success(request, f"Category '{name}' added successfully.")
                return redirect('add_category')
        else:
            messages.error(request, "Category name cannot be empty.")

    categories = Category.objects.all().order_by('name')
    return render(request, 'add_category.html', {'categories': categories})


@login_required
def edit_category(request, category_id):
    if request.user.role != 'admin':
        return redirect('dashboard_team')
    
    category = get_object_or_404(Category, id=category_id)

    if request.method == 'POST':
        new_name = request.POST.get('name').strip()
        if new_name:
            category.name = new_name
            category.save()
            messages.success(request, "Category updated successfully.")
            return redirect('add_category')
        else:
            messages.error(request, "Name can't be empty.")

    return render(request, 'edit_category.html', {'category': category})


@login_required
def delete_category(request, category_id):
    if request.user.role != 'admin':
        return redirect('dashboard_team')
    
    category = get_object_or_404(Category, id=category_id)
    category.delete()
    messages.success(request, "Category deleted.")
    return redirect('add_category')

from .models import Program

@login_required
def add_program(request):
    if request.user.role != 'admin':
        return redirect('dashboard_team')

    categories = Category.objects.all()
    programs = Program.objects.all().order_by('-id')

    if request.method == 'POST':
        name = request.POST.get('name')
        category_id = request.POST.get('category')

        if name and category_id:
            category = Category.objects.get(id=category_id)
            Program.objects.create(name=name, category=category)
            messages.success(request, f"Program '{name}' added successfully under {category.name}.")
            return redirect('add_program')
        else:
            messages.error(request, "All fields are required.")

    return render(request, 'add_program.html', {'categories': categories, 'programs': programs})

@login_required
def edit_program(request, program_id):
    if request.user.role != 'admin':
        return redirect('dashboard_team')

    program = get_object_or_404(Program, id=program_id)
    categories = Category.objects.all()

    if request.method == 'POST':
        name = request.POST.get('name').strip()
        category_id = request.POST.get('category')

        if name and category_id:
            category = get_object_or_404(Category, id=category_id)
            program.name = name
            program.category = category
            program.save()
            messages.success(request, "Program updated successfully.")
            return redirect('add_program')
        else:
            messages.error(request, "All fields are required.")

    return render(request, 'edit_program.html', {
        'program': program,
        'categories': categories
    })

@login_required
def delete_program(request, program_id):
    if request.user.role != 'admin':
        return redirect('dashboard_team')

    program = get_object_or_404(Program, id=program_id)
    program.delete()
    messages.success(request, "Program deleted successfully.")
    return redirect('add_program')

from django.contrib.auth.decorators import login_required

@login_required
def participant_list(request):
    user = request.user
    team_id = request.GET.get('team_id')
    category_id = request.GET.get('category_id')

    teams = Team.objects.all()
    categories = Category.objects.all()
    participants = Contestant.objects.select_related('team', 'category').order_by('chest_no')

    # 👇 If the logged-in user is a team user, filter to only their team participants
    if hasattr(user, 'team'):
        participants = participants.filter(team=user.team)
        team_id = user.team.id  # Fix context
    else:
        # For admin users, allow filtering
        if team_id:
            participants = participants.filter(team_id=team_id)
        if category_id:
            participants = participants.filter(category_id=category_id)

    return render(request, 'participants_list.html', {
        'teams': teams,
        'categories': categories,
        'participants': participants,
        'selected_team_id': int(team_id) if team_id else None,
        'selected_category_id': int(category_id) if category_id else None
    })


from .forms import ContestantForm
def add_participant(request):
    if request.method == 'POST':
        form = ContestantForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('participant_list')
    else:
        form = ContestantForm()
    return render(request, 'participant_form.html', {'form': form})

def edit_participant(request, id):
    participant = get_object_or_404(Contestant, id=id)
    if request.method == 'POST':
        form = ContestantForm(request.POST, instance=participant)
        if form.is_valid():
            form.save()
            return redirect('participant_list')
    else:
        form = ContestantForm(instance=participant)
    return render(request, 'participant_form.html', {'form': form})

def delete_participant(request, id):
    participant = get_object_or_404(Contestant, id=id)
    participant.delete()
    return redirect('participant_list')

def participants_list(request):
    participants = Contestant.objects.select_related('team', 'category').order_by('chest_no')
    return render(request, 'participants_list.html', {'participants': participants})


def add_team(request):
    form = TeamForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect('add_team')
    teams = Team.objects.all()
    return render(request, 'add_team_modal.html', {'form': form, 'teams': teams})

def edit_team(request, team_id):
    team = get_object_or_404(Team, id=team_id)
    form = TeamForm(request.POST or None, instance=team)
    if form.is_valid():
        form.save()
        return redirect('add_team')
    return render(request, 'edit_team.html', {'form': form, 'team': team})

def delete_team(request, team_id):
    team = get_object_or_404(Team, id=team_id)
    team.delete()
    return redirect('add_team')


# views.py
from django.shortcuts import render, redirect
from .forms import ParticipationForm
from django.contrib.auth.decorators import login_required

@login_required
def assign_competition(request):
    user = request.user

    if request.method == 'POST':
        form = ParticipationForm(request.POST, user=user)
        if form.is_valid():
            participation = form.save(commit=False)
            if user.role == 'team':
                participation.team = user.team  # Enforce team from user
            participation.save()
            return redirect('assign_competition')
    else:
        form = ParticipationForm(user=request.user)

    return render(request, 'assign_competition.html', {'form': form})


from django.shortcuts import render
from .models import Participation
from django.shortcuts import render
from .models import Participation, Team, Category

def view_assigned_programs(request):
    team_id = request.GET.get('team')
    category_id = request.GET.get('category')

    participations = Participation.objects.select_related(
        'contestant__team', 'contestant__category', 'program'
    )

    # 👇 Force filter by team if user is a team user
    if hasattr(request.user, 'team'):
        team_id = request.user.team.id
        participations = participations.filter(contestant__team_id=team_id)
    elif team_id:
        participations = participations.filter(contestant__team_id=team_id)

    if category_id:
        participations = participations.filter(contestant__category_id=category_id)

    context = {
        'participations': participations.order_by('contestant__team__name'),
        'teams': Team.objects.all(),
        'categories': Category.objects.all(),
        'selected_team': int(team_id) if team_id else '',
        'selected_category': int(category_id) if category_id else '',
    }

    return render(request, 'assigned_programs.html', context)



def view_results(request):
    results = Participation.objects.exclude(marks__isnull=True).order_by('rank')
    return render(request, 'view_results.html', {'results': results})




from django.shortcuts import render, redirect
from django.forms import modelformset_factory
from django.contrib.auth.decorators import login_required
from .models import Category, Program, Participation, TeamPoints
from .forms import MarkEntryForm

POINTS_FOR_RANK = {1: 6, 2: 3, 3: 1}
POINTS_FOR_GRADE = {'A': 6, 'B': 3, 'C': 1}

def get_grade(marks):
    if marks is None:
        return None
    if marks >= 80:
        return 'A'
    elif marks >= 60:
        return 'B'
    elif marks >= 50:
        return 'C'
    return None

@login_required
def add_marks(request):
    if request.user.role != 'admin':
        return redirect('dashboard_team')

    category_id = request.GET.get('category')
    program_id = request.GET.get('program')

    categories = Category.objects.all()
    programs = Program.objects.all()
    participations = Participation.objects.none()

    if category_id and program_id:
        participations = Participation.objects.filter(
            contestant__category_id=category_id,
            program_id=program_id
        ).order_by('id')

    ParticipationFormSet = modelformset_factory(
        Participation, form=MarkEntryForm, extra=0, can_delete=False
    )

    if request.method == 'POST':
        formset = ParticipationFormSet(request.POST, queryset=participations)

        if formset.is_valid():
            formset.save()

            # Re-fetch and recalculate rankings
            updated_participants = Participation.objects.filter(
                contestant__category_id=category_id,
                program_id=program_id,
                marks__isnull=False
            ).order_by('-marks')

            for i, participant in enumerate(updated_participants, start=1):
                participant.rank = i
                participant.grade = get_grade(participant.marks)

                if not participant.points_awarded and participant.grade:
                    rank_points = POINTS_FOR_RANK.get(i, 0)
                    grade_points = POINTS_FOR_GRADE.get(participant.grade, 0)
                    total_points = rank_points + grade_points
                    
                    team = participant.contestant.team
                    tp, _ = TeamPoints.objects.get_or_create(team=team)
                    tp.points += total_points
                    tp.save()

                    participant.points_awarded = True

                participant.save()

            return redirect(request.path + f"?category={category_id}&program={program_id}")
        else:
            # Add this for debugging
            print("Formset errors:", formset.errors)
    else:
        formset = ParticipationFormSet(queryset=participations)

    return render(request, 'add_marks.html', {
        'categories': categories,
        'programs': programs,
        'formset': formset,
        'selected_category': category_id,
        'selected_program': program_id,
        'participations': participations,  # Add this for template
    })


from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from .models import Team, TeamPoints, Participation


@login_required
def team_leaderboard(request):
    """Display team leaderboard with points breakdown"""
    
    # Get all teams with their points
    teams = Team.objects.all().order_by('name')
    
    # Calculate team statistics
    team_stats = []
    for team in teams:
        # Get participation statistics for this team
        participations = Participation.objects.filter(contestant__team=team)
        
        # Count participations by status
        total_participations = participations.count()
        marked_participations = participations.filter(marks__isnull=False).count()
        awarded_participations = participations.filter(points_awarded=True).count()
        
        # Count winners (top 3 positions) - only those with points awarded
        winners = participations.filter(rank__in=[1, 2, 3], points_awarded=True).count()
        
        # Count by grades - only those with points awarded
        grade_a = participations.filter(grade='A', points_awarded=True).count()
        grade_b = participations.filter(grade='B', points_awarded=True).count()
        grade_c = participations.filter(grade='C', points_awarded=True).count()
        
        # Count by ranks - only those with points awarded
        first_place = participations.filter(rank=1, points_awarded=True).count()
        second_place = participations.filter(rank=2, points_awarded=True).count()
        third_place = participations.filter(rank=3, points_awarded=True).count()
        
        # Calculate points breakdown
        rank_points = (first_place * 6) + (second_place * 3) + (third_place * 1)
        grade_points = (grade_a * 6) + (grade_b * 3) + (grade_c * 1)
        
        # Calculate total points dynamically
        total_calculated_points = rank_points + grade_points
        
        # Update or create TeamPoints object with calculated points
        team_points_obj, created = TeamPoints.objects.get_or_create(team=team)
        if team_points_obj.points != total_calculated_points:
            team_points_obj.points = total_calculated_points
            team_points_obj.save()
        
        team_stats.append({
            'team': team,
            'total_points': total_calculated_points,  # Use calculated points
            'rank_points': rank_points,
            'grade_points': grade_points,
            'total_participations': total_participations,
            'marked_participations': marked_participations,
            'awarded_participations': awarded_participations,
            'winners': winners,
            'first_place': first_place,
            'second_place': second_place,
            'third_place': third_place,
            'grade_a': grade_a,
            'grade_b': grade_b,
            'grade_c': grade_c,
        })
    
    # Sort teams by total points (descending)
    team_stats.sort(key=lambda x: x['total_points'], reverse=True)
    
    # Add ranking to teams
    for i, team_stat in enumerate(team_stats, 1):
        team_stat['position'] = i
    
    # Get top performers for highlights
    top_teams = team_stats[:3] if len(team_stats) >= 3 else team_stats
    
    # Calculate overall statistics
    total_teams = len(team_stats)
    total_points_distributed = sum(ts['total_points'] for ts in team_stats)
    total_participations_all = sum(ts['total_participations'] for ts in team_stats)
    total_winners_all = sum(ts['winners'] for ts in team_stats)
    
    context = {
        'team_stats': team_stats,
        'top_teams': top_teams,
        'total_teams': total_teams,
        'total_points_distributed': total_points_distributed,
        'total_participations_all': total_participations_all,
        'total_winners_all': total_winners_all,
    }
    
    return render(request, 'team_leaderboard.html', context)


@login_required
def team_detail(request, team_id):
    """Detailed view of a specific team's performance"""
    
    try:
        team = Team.objects.get(id=team_id)
    except Team.DoesNotExist:
        return redirect('team_leaderboard')
    
    # Get all participations for this team
    participations = Participation.objects.filter(
        contestant__team=team,
        marks__isnull=False
    ).select_related('program', 'contestant').order_by('-marks')
    
    # Calculate points for this team dynamically
    awarded_participations = participations.filter(points_awarded=True)
    
    # Count by ranks - only those with points awarded
    first_place = awarded_participations.filter(rank=1).count()
    second_place = awarded_participations.filter(rank=2).count()
    third_place = awarded_participations.filter(rank=3).count()
    
    # Count by grades - only those with points awarded
    grade_a = awarded_participations.filter(grade='A').count()
    grade_b = awarded_participations.filter(grade='B').count()
    grade_c = awarded_participations.filter(grade='C').count()
    
    # Calculate points breakdown
    rank_points = (first_place * 6) + (second_place * 3) + (third_place * 1)
    grade_points = (grade_a * 6) + (grade_b * 3) + (grade_c * 1)
    total_calculated_points = rank_points + grade_points
    
    # Update TeamPoints object
    team_points_obj, created = TeamPoints.objects.get_or_create(team=team)
    if team_points_obj.points != total_calculated_points:
        team_points_obj.points = total_calculated_points
        team_points_obj.save()
    
    # Separate winners and others
    winners = participations.filter(rank__in=[1, 2, 3])
    others = participations.exclude(rank__in=[1, 2, 3])
    
    # Group by programs
    programs_performance = {}
    for participation in participations:
        program_name = participation.program.name
        if program_name not in programs_performance:
            programs_performance[program_name] = []
        programs_performance[program_name].append(participation)
    
    # Additional statistics for detail view
    points_breakdown = {
        'rank_points': rank_points,
        'grade_points': grade_points,
        'total_points': total_calculated_points,
        'first_place_count': first_place,
        'second_place_count': second_place,
        'third_place_count': third_place,
        'grade_a_count': grade_a,
        'grade_b_count': grade_b,
        'grade_c_count': grade_c,
    }
    
    context = {
        'team': team,
        'team_points': total_calculated_points,  # Use calculated points
        'points_breakdown': points_breakdown,
        'participations': participations,
        'winners': winners,
        'others': others,
        'programs_performance': programs_performance,
        'total_participations': participations.count(),
        'total_winners': winners.count(),
        'awarded_participations': awarded_participations.count(),
    }
    
    return render(request, 'team_detail.html', context)


from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from .models import Contestant

def download_participants_pdf(request):
    participants = Contestant.objects.all()
    template_path = 'pdf_template.html'
    context = {'participants': participants}
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="participants.pdf"'
    
    template = get_template(template_path)
    html = template.render(context)
    
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('We had some errors <pre>' + html + '</pre>')
    return response



