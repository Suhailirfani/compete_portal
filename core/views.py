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
    return user.is_superuser or user.role == 'admin' # or use your custom check

def face_page(request):
    programs = Program.objects.all()
    teams = Team.objects.all()
    contestants = Contestant.objects.all()
    context = {
        'programs': programs,
        'teams': teams,
        'contestants' : contestants
    }
    return render(request, 'face.html', context)

@login_required
@user_passes_test(is_admin)
def lock_user(request, user_id):
    user = get_object_or_404(User, id=user_id)

    if user.role == 'team':   # only lock team role users
        user.is_active = False
        user.save()

    return redirect('view_users')

@login_required
@user_passes_test(is_admin)
def unlock_user(request, user_id):
    user = get_object_or_404(User, id=user_id)

    if user.role == 'team':   # only unlock team role users
        user.is_active = True
        user.save()

    return redirect('view_users')


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
    pending_users = User.objects.filter(is_approved=False)
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

    paginator = Paginator(users, 10)  # 10 per page
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
    if not (request.user.is_superuser or request.user.role == 'admin'):
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

import pandas as pd
from django.core.files.storage import FileSystemStorage

@login_required
def add_program(request):
    if not (request.user.is_superuser or request.user.role == 'admin'):
        return redirect('dashboard_team')

    categories = Category.objects.all()
    programs = Program.objects.all().order_by('-id')

    if request.method == 'POST':
        # Check if it's a bulk upload
        if 'excel_file' in request.FILES:
            excel_file = request.FILES['excel_file']

            try:
                # Read Excel file with pandas
                df = pd.read_excel(excel_file)

                # Expecting columns: "name" and "category"
                for _, row in df.iterrows():
                    name = row.get("name")
                    category_name = row.get("category")

                    if name and category_name:
                        try:
                            category = Category.objects.get(name=category_name)
                            Program.objects.create(name=name, category=category)
                        except Category.DoesNotExist:
                            messages.warning(request, f"Category '{category_name}' not found for program '{name}'. Skipped.")
                messages.success(request, "Bulk upload completed successfully.")
            except Exception as e:
                messages.error(request, f"Error processing Excel file: {e}")

            return redirect('add_program')

        else:
            # Single entry form
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

@login_required
def add_group_program(request):
    if not (request.user.is_superuser or request.user.role == 'admin'):
        return redirect('dashboard_team')

    categories = Category.objects.all()
    programs = Program.objects.filter(is_group=True).order_by('-id')

    if request.method == 'POST':
        name = request.POST.get('name')
        category_id = request.POST.get('category')

        if name and category_id:
            category = get_object_or_404(Category, id=category_id)
            Program.objects.create(name=name, category=category, is_group=True)
            messages.success(request, f"Group Program '{name}' added successfully.")
            return redirect('add_group_program')
        else:
            messages.error(request, "All fields are required.")

    return render(request, 'add_group_program.html', {'categories': categories, 'programs': programs})


@login_required
def assign_group_program(request):
    if not (request.user.is_superuser or request.user.role == 'admin'):
        return redirect('dashboard_team')

    categories = Category.objects.all()

    if request.method == 'POST':
        program_id = request.POST.get('program')
        participant_ids = request.POST.getlist('participants')

        if len(participant_ids) > 5:
            messages.error(request, "You can select a maximum of 5 participants.")
            return redirect('assign_group_program')

        program = get_object_or_404(Program, id=program_id)
        for pid in participant_ids:
            contestant = Contestant.objects.get(id=pid)
            Participation.objects.create(contestant=contestant, program=program)

        messages.success(request, "Participants assigned successfully.")
        return redirect('assign_group_program')

    return render(request, 'assign_group_program.html', {'categories': categories})


from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

@login_required
@csrf_exempt
def get_group_programs(request):
    category_id = request.POST.get('category_id')
    programs = Program.objects.filter(category_id=category_id, is_group=True)
    program_list = [{"id": p.id, "name": p.name} for p in programs]
    return JsonResponse({"programs": program_list})

@login_required
@csrf_exempt
def get_participants_by_category(request):
    category_id = request.POST.get('category_id')
    contestants = Contestant.objects.filter(category_id=category_id)
    contestant_list = [{"id": c.id, "name": c.name} for c in contestants]
    return JsonResponse({"contestants": contestant_list})


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

@login_required
def participants_by_category(request):
    user = request.user
    
    # Get all categories and participants
    categories = Category.objects.all().order_by('name')
    participants = Contestant.objects.select_related('team', 'category').order_by('chest_no')
    
    # If the logged-in user is a team user, filter to only their team participants
    if hasattr(user, 'team'):
        participants = participants.filter(team=user.team)
    
    # Group participants by category
    participants_by_category = {}
    for category in categories:
        category_participants = participants.filter(category=category)
        if category_participants.exists():
            participants_by_category[category] = category_participants
    
    return render(request, 'participants_by_category.html', {
        'participants_by_category': participants_by_category,
        'total_participants': participants.count(),
    })


@login_required
def participants_by_team(request):
    user = request.user
    
    # Get all teams and participants
    teams = Team.objects.all().order_by('name')
    participants = Contestant.objects.select_related('team', 'category').order_by('chest_no')
    
    # If the logged-in user is a team user, show only their team
    if hasattr(user, 'team'):
        teams = Team.objects.filter(id=user.team.id)
        participants = participants.filter(team=user.team)
    
    # Group participants by team
    participants_by_team = {}
    for team in teams:
        team_participants = participants.filter(team=team)
        if team_participants.exists():
            participants_by_team[team] = team_participants
    
    return render(request, 'participants_by_team.html', {
        'participants_by_team': participants_by_team,
        'total_participants': participants.count(),
    })


import pandas as pd
from django.contrib import messages
from django.shortcuts import render, redirect
from .forms import ContestantForm
from .models import Contestant, Team, Category

def add_participant(request):
    if request.method == 'POST':
        # --- Bulk Upload Excel ---
        if 'excel_file' in request.FILES:
            excel_file = request.FILES['excel_file']
            try:
                df = pd.read_excel(excel_file)

                # Expect columns: name, team, category
                for _, row in df.iterrows():
                    name = row.get("name")
                    team_name = row.get("team")
                    category_name = row.get("category")

                    if not (name and team_name and category_name):
                        continue  # skip incomplete rows

                    try:
                        team = Team.objects.get(name=team_name)
                        category = Category.objects.get(name=category_name)

                        Contestant.objects.create(
                            name=name,
                            team=team,
                            category=category,
                            # chest_no auto-assigned in save()
                            # total_points default=0
                        )
                    except Team.DoesNotExist:
                        messages.warning(request, f"Team '{team_name}' not found. Skipped {name}.")
                    except Category.DoesNotExist:
                        messages.warning(request, f"Category '{category_name}' not found. Skipped {name}.")

                messages.success(request, "Bulk participant upload successful.")
            except Exception as e:
                messages.error(request, f"Error processing Excel: {e}")

            return redirect('participant_list')

        # --- Single Form Entry ---
        else:
            form = ContestantForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, "Participant added successfully.")
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

# views.py
from django.http import JsonResponse
from .models import Program, Participation

def get_programs_for_contestant(request):
    contestant_id = request.GET.get('contestant_id')
    category_id = request.GET.get('category_id')

    if not contestant_id or not category_id:
        return JsonResponse({'programs': []})

    # Get programs of selected category not already assigned
    assigned_programs = Participation.objects.filter(
        contestant_id=contestant_id
    ).values_list('program_id', flat=True)

    programs = Program.objects.filter(
        category_id=category_id
    ).exclude(id__in=assigned_programs)

    return JsonResponse({
        'programs': list(programs.values('id', 'name'))
    })

from django.http import JsonResponse
from .models import Contestant

def get_contestants(request):
    team_id = request.GET.get('team_id')
    category_id = request.GET.get('category_id')

    contestants = Contestant.objects.filter(
        team_id=team_id, category_id=category_id
    ).values('id', 'name')

    return JsonResponse({'contestants': list(contestants)})


@login_required
def assign_programs(request):
    teams = Team.objects.all()
    categories = Category.objects.all()
    contestants = Contestant.objects.none()  # initially empty

    if request.method == 'POST':
        contestant_id = request.POST.get('contestant')
        selected_programs = request.POST.getlist('programs')

        if len(selected_programs) > 5:
            messages.error(request, "You can only select up to 5 programs.")
        else:
            for prog_id in selected_programs:
                Participation.objects.get_or_create(
                    contestant_id=contestant_id,
                    program_id=prog_id
                )
            messages.success(request, "Programs assigned successfully!")
            return redirect('assign_programs')

    return render(request, 'assign_programs.html', {
        'teams': teams,
        'categories': categories,
        'contestants': contestants,
    })

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



from django.forms import modelformset_factory
from django.db import transaction
from django.http import JsonResponse
from .models import Category, Program, Participation, TeamPoints
from .forms import MarkEntryForm

# Constants for point calculation
POINTS_FOR_RANK = {1: 6, 2: 3, 3: 1}
POINTS_FOR_GRADE = {'A': 6, 'B': 3, 'C': 1}
POINTS_FOR_RANK_GROUP = {1: 15, 2: 10, 3: 5}
POINTS_FOR_GRADE_GROUP = {'A': 15, 'B': 10, 'C': 5}

def get_grade(marks):
    """Convert marks to grade"""
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
    # Check if user is admin
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('dashboard_team')
    
    # Get filter parameters
    category_id = request.GET.get('category')
    program_id = request.GET.get('program')
    
    # Get all categories for dropdown
    categories = Category.objects.all().order_by('name')
    
    # Filter programs based on selected category
    programs = Program.objects.none()
    if category_id:
        try:
            category_id = int(category_id)
            programs = Program.objects.filter(category_id=category_id).order_by('name')
        except (ValueError, TypeError):
            category_id = None
    
    # Get participations based on filters
    participations = Participation.objects.none()
    if category_id and program_id:
        try:
            program_id = int(program_id)
            participations = Participation.objects.filter(
                contestant__category_id=category_id,
                program_id=program_id
            ).select_related(
                'contestant', 
                'contestant__team', 
                'program'
            ).order_by('contestant__chest_no')
        except (ValueError, TypeError):
            program_id = None
    
    # Create formset
    ParticipationFormSet = modelformset_factory(
        Participation,
        form=MarkEntryForm,
        extra=0,
        can_delete=False
    )
    
    # Handle form submission
    if request.method == 'POST':
        formset = ParticipationFormSet(request.POST, queryset=participations)
        
        if formset.is_valid():
            try:
                with transaction.atomic():
                    # Save all forms in the formset
                    instances = formset.save(commit=False)
                    saved_count = 0
                    
                    for instance in instances:
                        if instance.marks is not None:
                            instance.save()
                            saved_count += 1
                    
                    # Calculate rankings and assign points
                    if saved_count > 0:
                        calculate_rankings_and_points(category_id, program_id)
                    
                    messages.success(request, f'Successfully saved marks for {saved_count} participants!')
                    
                    # Redirect to same page with filters to show updated data
                    return redirect(f"{request.path}?category={category_id}&program={program_id}")
                    
            except Exception as e:
                messages.error(request, f'Error saving marks: {str(e)}')
                print(f"Error in add_marks: {e}")
                import traceback
                traceback.print_exc()
        else:
            # Handle form errors
            messages.error(request, 'Please correct the errors below.')
            for i, form in enumerate(formset):
                if form.errors:
                    for field, errors in form.errors.items():
                        for error in errors:
                            messages.error(request, f'Row {i+1} - {field}: {error}')
    else:
        # GET request - initialize empty formset
        formset = ParticipationFormSet(queryset=participations)
    
    # Prepare context
    context = {
        'categories': categories,
        'programs': programs,
        'formset': formset,
        'selected_category': str(category_id) if category_id else '',
        'selected_program': str(program_id) if program_id else '',
        'participations': participations,
    }
    
    return render(request, 'add_marks.html', context)

def award_points_to_team(participant, total_points):
    team = participant.contestant.team
    team_points, _ = TeamPoints.objects.get_or_create(team=team, defaults={'points': 0})
    team_points.points += total_points
    team_points.save()

    team.total_points += total_points
    team.save()

    participant.points_awarded = True


def calculate_rankings_and_points(category_id, program_id):
    """
    Calculate rankings and award points for a specific program in a category.
    Handles both individual and group programs.
    """
    try:
        # Get program instance to check if group or individual
        program = Program.objects.get(id=program_id)
        is_group_program = program.is_group  # <-- Ensure this field exists in Program model

        participants = Participation.objects.filter(
            contestant__category_id=category_id,
            program_id=program_id,
            marks__isnull=False
        ).select_related('contestant', 'contestant__team').order_by('-marks', 'contestant__chest_no')

        # Reset all rankings first
        Participation.objects.filter(
            contestant__category_id=category_id,
            program_id=program_id
        ).update(rank=None, grade=None)

        for rank, participant in enumerate(participants, start=1):
            participant.rank = rank
            participant.grade = get_grade(participant.marks)

            if not participant.points_awarded:
                total_points = calculate_points(rank, participant.grade, is_group_program)
                if total_points > 0:
                    award_points_to_team(participant, total_points)
            participant.save()

    except Exception as e:
        print(f"Error in calculate_rankings_and_points: {e}")
        raise


def calculate_points(rank, grade, is_group=False):
    """
    Calculate points based on whether program is group or individual.
    """
    if is_group:
        rank_points = POINTS_FOR_RANK_GROUP.get(rank, 0)
        grade_points = POINTS_FOR_GRADE_GROUP.get(grade, 0) if grade else 0
    else:
        rank_points = POINTS_FOR_RANK.get(rank, 0)
        grade_points = POINTS_FOR_GRADE.get(grade, 0) if grade else 0
    return rank_points + grade_points


# Optional: AJAX view for dynamic program loading
@login_required
def get_programs_by_category(request):
    """
    AJAX view to get programs filtered by category
    """
    category_id = request.GET.get('category_id')
    programs = []
    
    if category_id:
        try:
            programs_qs = Program.objects.filter(category_id=int(category_id)).order_by('name')
            programs = [{'id': p.id, 'name': p.name} for p in programs_qs]
        except (ValueError, TypeError):
            pass
    
    return JsonResponse({'programs': programs})
    if request.user.role != 'admin':
        return redirect('dashboard_team')

    category_id = request.GET.get('category')
    program_id = request.GET.get('program')

    categories = Category.objects.all()
    
    # Filter programs based on selected category
    if category_id:
        programs = Program.objects.filter(category_id=category_id)
    else:
        programs = Program.objects.all()
    
    participations = Participation.objects.none()

    if category_id and program_id:
        participations = Participation.objects.filter(
            contestant__category_id=category_id,
            program_id=program_id
        ).select_related('contestant', 'contestant__team', 'program').order_by('contestant__chest_no')

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

            messages.success(request, f'Marks saved successfully for {updated_participants.count()} participants!')
            return redirect(request.path + f"?category={category_id}&program={program_id}")
        else:
            # Add error message
            messages.error(request, 'There were errors in the form. Please check and try again.')
            print("Formset errors:", formset.errors)
    else:
        formset = ParticipationFormSet(queryset=participations)

    return render(request, 'add_marks.html', {
        'categories': categories,
        'programs': programs,
        'formset': formset,
        'selected_category': category_id,
        'selected_program': program_id,
        'participations': participations,
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

@login_required
def download_participants_pdf(request):
    user = request.user
    
    # Get participants based on user role
    participants = Contestant.objects.select_related('team', 'category').order_by('chest_no')
    
    # If the logged-in user is a team user, filter to only their team participants
    if hasattr(user, 'team'):
        participants = participants.filter(team=user.team)
        filename = f"{user.team.name}_participants.pdf"
    else:
        # Admin users can download all participants
        filename = "all_participants.pdf"
    
    template_path = 'pdf_template.html'
    context = {
        'participants': participants,
        'user': user,
        'is_team_user': hasattr(user, 'team'),
        'team_name': user.team.name if hasattr(user, 'team') else None
    }
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    template = get_template(template_path)
    html = template.render(context)
    
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('We had some errors <pre>' + html + '</pre>')
    return response


# Optional: Create separate PDF download functions for specific views
@login_required
def download_category_participants_pdf(request):
    user = request.user
    category_id = request.GET.get('category_id')
    
    participants = Contestant.objects.select_related('team', 'category').order_by('chest_no')
    
    # Filter by team if team user
    if hasattr(user, 'team'):
        participants = participants.filter(team=user.team)
    
    # Filter by category if specified
    if category_id:
        participants = participants.filter(category_id=category_id)
        try:
            category = Category.objects.get(id=category_id)
            filename = f"{category.name}_participants.pdf"
        except Category.DoesNotExist:
            filename = "category_participants.pdf"
    else:
        filename = "participants_by_category.pdf"
    
    template_path = 'pdf_template.html'
    context = {
        'participants': participants,
        'user': user,
        'is_team_user': hasattr(user, 'team'),
        'team_name': user.team.name if hasattr(user, 'team') else None,
        'category_filter': category.name if category_id else None
    }
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    template = get_template(template_path)
    html = template.render(context)
    
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('We had some errors <pre>' + html + '</pre>')
    return response


@login_required
def download_team_participants_pdf(request):
    user = request.user
    team_id = request.GET.get('team_id')
    
    participants = Contestant.objects.select_related('team', 'category').order_by('chest_no')
    
    # If team user, they can only download their own team
    if hasattr(user, 'team'):
        participants = participants.filter(team=user.team)
        filename = f"{user.team.name}_participants.pdf"
    else:
        # Admin can download specific team or all teams
        if team_id:
            participants = participants.filter(team_id=team_id)
            try:
                team = Team.objects.get(id=team_id)
                filename = f"{team.name}_participants.pdf"
            except Team.DoesNotExist:
                filename = "team_participants.pdf"
        else:
            filename = "participants_by_team.pdf"
    
    template_path = 'pdf_template.html'
    context = {
        'participants': participants,
        'user': user,
        'is_team_user': hasattr(user, 'team'),
        'team_name': user.team.name if hasattr(user, 'team') else None,
        'team_filter': team.name if team_id else None
    }
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    template = get_template(template_path)
    html = template.render(context)
    
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('We had some errors <pre>' + html + '</pre>')
    return response


@login_required
def program_participants(request):
    """Show participants for a specific program"""
    user = request.user
    program_id = request.GET.get('program_id')
    
    # Get all programs for the dropdown
    programs = Program.objects.all().order_by('name')
    participants = None
    selected_program = None
    
    if program_id:
        try:
            selected_program = Program.objects.get(id=program_id)
            participants = Contestant.objects.filter(
                program=selected_program
            ).select_related('team', 'category').order_by('chest_no')
            
            # If team user, filter to only their team participants
            if hasattr(user, 'team'):
                participants = participants.filter(team=user.team)
                
        except Program.DoesNotExist:
            selected_program = None
            participants = None
    
    return render(request, 'program_participants.html', {
        'programs': programs,
        'participants': participants,
        'selected_program': selected_program,
        'selected_program_id': int(program_id) if program_id else None,
    })


@login_required
def download_green_room_pdf(request, program_id):
    """Download Green Room Sign Sheet PDF"""
    try:
        program = Program.objects.get(id=program_id)
    except Program.DoesNotExist:
        return HttpResponse('Program not found', status=404)

    user = request.user
    participants = Contestant.objects.filter(
        participation__program=program
    ).select_related('team', 'category').order_by('chest_no')

    # Filter by team if team user
    if hasattr(user, 'team'):
        participants = participants.filter(team=user.team)
        filename = f"{program.name}_{user.team.name}_green_room.pdf"
    else:
        filename = f"{program.name}_green_room.pdf"

    template_path = 'green_room_pdf.html'
    context = {
        'program': program,
        'participants': participants,
        'user': user,
        'is_team_user': hasattr(user, 'team'),
        'team_name': user.team.name if hasattr(user, 'team') else None
    }

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    template = get_template(template_path)
    html = template.render(context)

    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('We had some errors <pre>' + html + '</pre>')
    return response


@login_required
def green_room_list(request, program_id):
    """Show Green Room Sign Sheet as normal Django page (HTML table)"""
    try:
        program = Program.objects.get(id=program_id)
    except Program.DoesNotExist:
        return HttpResponse('Program not found', status=404)

    user = request.user
    participants = Contestant.objects.filter(
        participation__program=program
    ).select_related('team', 'category').order_by('chest_no')

    # Filter if team user
    if hasattr(user, 'team'):
        participants = participants.filter(team=user.team)

    context = {
        'program': program,
        'participants': participants,
        'is_team_user': hasattr(user, 'team'),
        'team_name': user.team.name if hasattr(user, 'team') else None
    }
    return render(request, 'green_room_list.html', context)



@login_required
def download_call_list_pdf(request, program_id):
    """Download Call List PDF"""
    try:
        program = Program.objects.get(id=program_id)
    except Program.DoesNotExist:
        return HttpResponse('Program not found', status=404)
    
    user = request.user
    participants = Contestant.objects.filter(
         participation__program=program
    ).select_related('team', 'category').order_by('chest_no')
    
    # Filter by team if team user
    if hasattr(user, 'team'):
        participants = participants.filter(team=user.team)
        filename = f"{program.name}_{user.team.name}_call_list.pdf"
    else:
        filename = f"{program.name}_call_list.pdf"
    
    template_path = 'call_list_pdf.html'
    context = {
        'program': program,
        'participants': participants,
        'user': user,
        'is_team_user': hasattr(user, 'team'),
        'team_name': user.team.name if hasattr(user, 'team') else None
    }
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    template = get_template(template_path)
    html = template.render(context)
    
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('We had some errors <pre>' + html + '</pre>')
    return response


@login_required
def download_valuation_form_pdf(request, program_id):
    """Download Valuation Form PDF"""
    try:
        program = Program.objects.get(id=program_id)
    except Program.DoesNotExist:
        return HttpResponse('Program not found', status=404)
    
    user = request.user
    participants = Contestant.objects.filter(
         participation__program=program
    ).select_related('team', 'category').order_by('chest_no')
    
    # Filter by team if team user
    if hasattr(user, 'team'):
        participants = participants.filter(team=user.team)
        filename = f"{program.name}_{user.team.name}_valuation.pdf"
    else:
        filename = f"{program.name}_valuation.pdf"
    
    template_path = 'valuation_form.html'
    context = {
        'program': program,
        'participants': participants,
        'user': user,
        'is_team_user': hasattr(user, 'team'),
        'team_name': user.team.name if hasattr(user, 'team') else None
    }
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    template = get_template(template_path)
    html = template.render(context)
    
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('We had some errors <pre>' + html + '</pre>')
    return response


def list_page(request):
    return render(request, 'list_page.html')

@login_required
def download_all_call_lists_pdf(request):
    """Download Call List PDF for all programs"""
    user = request.user
    
    # Fetch all programs
    programs = Program.objects.all().order_by('name')

    # Collect participants for each program
    program_participants = []
    for program in programs:
        participants = Contestant.objects.filter(
            participation__program=program
        ).select_related('team', 'category').order_by('chest_no')

        # Filter by team if user is team-based
        if hasattr(user, 'team'):
            participants = participants.filter(team=user.team)

        program_participants.append({
            'program': program,
            'participants': participants
        })

    # Prepare filename
    if hasattr(user, 'team'):
        filename = f"all_programs_{user.team.name}_call_list.pdf"
    else:
        filename = "all_programs_call_list.pdf"

    # Render template
    template_path = 'all_call_list_pdf.html'  # New template for all programs
    context = {
        'program_participants': program_participants,
        'user': user,
        'is_team_user': hasattr(user, 'team'),
        'team_name': user.team.name if hasattr(user, 'team') else None
    }

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    template = get_template(template_path)
    html = template.render(context)

    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('We had some errors <pre>' + html + '</pre>')
    return response
