from django.shortcuts import redirect, render
from .models import *
from django.contrib import messages
from django.contrib.auth.decorators import login_required

# Create your views here.
def girls_page(request):
    categories = Category.objects.all()
    programs = Program.objects.all()
    contestants = Contestant.objects.all()
    participations = Participation.objects.all()
    group_participations =GroupParticipation.objects.all()
    points_configuration = PointsConfig.objects.all()

    context = {
        'categories': categories,
        'programs':programs,
        'contestants':contestants,
        'participations':participations,
        'group_participations': group_participations,
        'points_configuration':points_configuration,

    }
    return render(request, 'girls/girls_page.html', context)

def dashboard_off_campus(request):
    if request.user.role != 'off_campus': return redirect('dashboard_admin')
    off_campus = request.user.off_campus
    # In your view
    contestants = Contestant.objects.filter(off_campus=off_campus).order_by('category', 'name')

    context = {
        'off_campus':off_campus,
        'contestants':contestants,
    }
    return render(request, 'girls/dashboard_off_campus.html',context)

@login_required
def add_category_off(request):
    if not (request.user.is_superuser or request.user.role == 'admin'):
        return redirect('dashboard_off_campus')  # or wherever non-admins should go

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



