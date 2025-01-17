from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Event, Preguntas, Respuestas, StudyAvailability, StudyTopic, ForoPregunta, ForoGeneral, ForoMensajes, ForoBase
from datetime import date, timedelta
from django.core.exceptions import ValidationError

class LoginForm(forms.Form):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)

class RegisterForm(UserCreationForm):
    consent = forms.BooleanField(
        label="Acepto la Política de Privacidad",
        widget=forms.CheckboxInput(),
        required=True,
        error_messages={
            'required': 'Debes aceptar la Política de Privacidad para registrarte.'
        }
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2', 'consent']

class EventForm(forms.ModelForm):
    start_time = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'id': 'start_time_picker', 'data-target':'#start_time_picker'}),
        input_formats=['%d/%m/%Y %H:%M']
    )
    end_time = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'id': 'end_time_picker', 'data-target':'#end_time_picker'}),
        input_formats=['%d/%m/%Y %H:%M']
    )

    class Meta:
        model = Event
        fields = ['title', 'description', 'start_time', 'end_time']

class TestForm(forms.Form):
    def __init__(self, questions_with_responses, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for question_data in questions_with_responses:
            pregunta_test = question_data['pregunta_test']
            respuestas = question_data['respuestas'] 

            # Usar las tuplas para construir las opciones
            self.fields[f'pregunta_{pregunta_test.pregunta_fk.id}'] = forms.ChoiceField(
                label=pregunta_test.pregunta_fk.pregunta,
                choices=respuestas,
                widget=forms.RadioSelect,
                required=False,
                initial=pregunta_test.respuesta_seleccionada_fk.id if pregunta_test.respuesta_seleccionada_fk else None
            )

class ConfirmTestForm(forms.Form):
    def __init__(self, questions_with_responses, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for question_data in questions_with_responses:
            pregunta_test = question_data['pregunta_test']
            respuesta_seleccionada = (
                pregunta_test.respuesta_seleccionada_fk.descripcion
                if pregunta_test.respuesta_seleccionada_fk
                else "Sin respuesta"
            )

            # Campo de solo lectura para mostrar la respuesta seleccionada
            self.fields[f'pregunta_{pregunta_test.pregunta_fk.id}'] = forms.CharField(
                label=pregunta_test.pregunta_fk.pregunta,
                initial=respuesta_seleccionada,
                widget=forms.TextInput(attrs={'readonly': 'readonly'}),
                required=False,
            )
   
class EditProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']
        labels = {
            'username': 'Username',
            'first_name': 'First Name',
            'last_name': 'Last Name',
            'email': 'Email',
        }
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

class ForoPreguntaForm(forms.ModelForm):
    asunto = forms.CharField(
        max_length=255,
        label="Asunto",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    contenido = forms.CharField(
        label="Contenido",
        widget=forms.Textarea(attrs={'class': 'form-control'})
    )

    class Meta:
        model = ForoPregunta
        fields = ['asunto', 'contenido']

    def save(self, commit=True):
        # Crear ForoBase
        foro_base = ForoBase(
            asunto=self.cleaned_data['asunto'],
            contenido=self.cleaned_data['contenido'],
            creado_por_fk=self.initial['user'],
        )
        foro_base.save()  # Asegúrate de guardar ForoBase antes de asociarlo

        # Asociar ForoBase a ForoPregunta
        foro_pregunta = super().save(commit=False)
        foro_pregunta.foro_base = foro_base

        if commit:
            foro_pregunta.save()

        return foro_pregunta


class ForoGeneralForm(forms.ModelForm):
    # Campos del modelo ForoBase
    asunto = forms.CharField(max_length=255, label="Asunto", widget=forms.TextInput(attrs={'class': 'form-control'}))
    contenido = forms.CharField(label="Contenido", widget=forms.Textarea(attrs={'class': 'form-control'}))

    class Meta:
        model = ForoGeneral
        fields = ['id_tema_fk']  # Solo el campo específico de ForoGeneral

    def save(self, commit=True):
        # Crear ForoBase
        foro_base = ForoBase(
            asunto=self.cleaned_data['asunto'],
            contenido=self.cleaned_data['contenido'],
            creado_por_fk=self.initial['user'],  # Usuario se debe pasar al inicializar el formulario
        )
        if commit:
            foro_base.save()

        # Asociar ForoBase a ForoGeneral
        foro_general = super().save(commit=False)
        foro_general.foro_base = foro_base
        if commit:
            foro_general.save()
        return foro_general

class ForoMensajeForm(forms.ModelForm):
    class Meta:
        model = ForoMensajes
        fields = ['contenido']
        labels = {
            'contenido': 'Contenido del Mensaje',
        }
        widgets = {
            'contenido': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }


class StudyAvailabilityForm(forms.ModelForm):
    class Meta:
        model = StudyAvailability
        fields = ['study_mode']
        widgets = {
            'study_mode': forms.RadioSelect,  # Opcional: para mostrar botones de radio
        }
        labels = {
            'study_mode': 'Selecciona el modo de estudio',
        }