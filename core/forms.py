from django import forms
from .models import Contestant, Participation, Team, Program

class ContestantForm(forms.ModelForm):
    class Meta:
        model = Contestant
        fields = ['name']




from .models import Contestant, Team, Category

class ContestantForm(forms.ModelForm):
    class Meta:
        model = Contestant
        fields = ['name', 'team', 'category']

class TeamCategoryForm(forms.Form):
    team = forms.ModelChoiceField(queryset=Team.objects.all())
    category = forms.ModelChoiceField(queryset=Category.objects.all())

# forms.py
from django import forms
from .models import Participation, Team, Category, Contestant, Program

class ParticipationForm(forms.ModelForm):
    team = forms.ModelChoiceField(queryset=Team.objects.all(), required=True)
    category = forms.ModelChoiceField(queryset=Category.objects.all(), required=True)

    class Meta:
        model = Participation
        fields = ['team', 'category', 'contestant', 'program']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)  # 👈 Accept user from view
        super().__init__(*args, **kwargs)

        # 👇 Hide team field if user is team role
        if user and user.role == 'team':
            if hasattr(user, 'team'):
                self.fields['team'].initial = user.team
                self.fields['team'].widget = forms.HiddenInput()
            else:
                self.fields['team'].queryset = Team.objects.none()

        # Initialize empty contestants and programs
        self.fields['contestant'].queryset = Contestant.objects.none()
        self.fields['program'].queryset = Program.objects.none()

        if 'team' in self.data and 'category' in self.data:
            try:
                team_id = int(self.data.get('team'))
                category_id = int(self.data.get('category'))

                self.fields['contestant'].queryset = Contestant.objects.filter(
                    team_id=team_id, category_id=category_id
                ).order_by('name')

                self.fields['program'].queryset = Program.objects.filter(
                    category_id=category_id
                ).order_by('name')

            except (ValueError, TypeError):
                pass

        elif self.instance.pk:
            # Editing existing
            self.fields['contestant'].queryset = Contestant.objects.filter(
                team=self.instance.team, category=self.instance.category
            )
            self.fields['program'].queryset = Program.objects.filter(
                category=self.instance.category
            )



from django.contrib.auth.models import User

class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ['user', 'name']
        widgets = {
            'user': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
        }


class MarkEntryForm(forms.ModelForm):
    class Meta:
        model = Participation
        fields = ['marks']
