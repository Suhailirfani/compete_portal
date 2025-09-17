# competition_app/utils.py
def get_grade(marks):
    if marks >= 80:
        return 'A'
    elif marks >= 60:
        return 'B'
    elif marks >= 40:
        return 'C'
    return 'F'

POINTS_FOR_RANK = {1: 5, 2: 3, 3: 1}
POINTS_FOR_GRADE = {'A': 5, 'B': 3, 'C': 1}

def get_filtered_queryset(model, gender=None):
    qs = model.objects.all()
    if gender:
        qs = qs.filter(gender=gender)
    return qs