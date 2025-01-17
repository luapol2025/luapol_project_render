from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest
from .forms import LoginForm, RegisterForm, EventForm, TestForm, EditProfileForm, ForoPreguntaForm, ForoGeneralForm, ForoMensajeForm, StudyAvailabilityForm, ConfirmTestForm
from .models import User, Event, Preguntas, Respuestas, ResultadoTest, Test, Preguntas, PreguntaTest, UserProfile, StudyAvailability, StudyTopic, TestSubtemaFallado, ForoPregunta, ForoGeneral, ForoMensajes, ForoBase, ForoMeGusta, EventSection, SubTopic, Notifications
from .utils import send_verification_email, generate_test_plan, generate_test_review_report, unlock_next_event, generate_study_plan, finalize_test, get_shuffled_data, general_progress_report_individual, general_progress_report_global, attempts_report, generate_user_ranking
from django.urls import reverse
from django.utils import timezone
from django.contrib import messages
import uuid, json, logging, random
from django.contrib.auth.forms import PasswordChangeForm
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import send_mail
from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Q, F, Sum, Count
from django.db.models.functions import Coalesce

logger = logging.getLogger(__name__)

def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                if user.is_active:
                    login(request, user)
                    return redirect('luapol_app:start')
                else:
                    messages.error(request, 'Tu cuenta no está activada. Por favor, verifica tu correo electrónico.')
                    return render(request, 'login.html', {'form': form})
            else:
                messages.error(request, 'Usuario o contraseña incorrectos.')
                return render(request, 'login.html', {'form': form})
    else:
        form = LoginForm()
    return render(request, 'login.html', {'form': form})

def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False  # Desactivar cuenta hasta la verificación
            user.save()

            # Crear o recuperar el perfil del usuario
            user_profile, created = UserProfile.objects.get_or_create(user_oto=user)
            if created:
                user_profile.consent_given = form.cleaned_data.get('consent')
                user_profile.save()

            # Enviar el correo de verificación
            send_verification_email(user)

            # Redirigir a la página de verificación pendiente
            return redirect('luapol_app:verification_pending', user_id=user.id)
    else:
        form = RegisterForm()
    return render(request, 'register.html', {'form': form})

def verification_pending_view(request, user_id):
    user = get_object_or_404(User, id=user_id)  # Recuperar el usuario con el ID
    try:
        if user.is_active:
            messages.info(request, "Tu cuenta ya está verificada. Puedes iniciar sesión.")
            return redirect('luapol_app:login')
    except UserProfile.DoesNotExist:
        messages.error(request, "No se encontró un perfil asociado. Por favor, registra una cuenta.")
        return redirect('luapol_app:register')

    if request.method == 'POST':
        send_verification_email(user)
        messages.success(request, 'El enlace de activación se ha reenviado a tu correo electrónico.')

    return render(request, 'verification_pending.html', {'user': user})


def activate_account_view(request, user_id, token):
    try:
        user_profile = UserProfile.objects.get(user_oto=user_id, activation_token=token)
        user_profile.user_oto.is_active = True
        user_profile.activation_token = uuid.uuid4()  # Invalida el token
        user_profile.user_oto.save()
        user_profile.save()
        messages.success(request, 'Tu cuenta ha sido activada exitosamente. Ahora puedes iniciar sesión.')
        return redirect('luapol_app:login')
    except UserProfile.DoesNotExist:
        messages.error(request, 'Enlace de activación inválido o expirado.')
        return redirect('luapol_app:register')

def start_view(request):
    # Obtener las tareas o eventos del usuario
    user = request.user
    eventos = Event.objects.filter(user_fk=user).order_by('block_number', 'order')
    
    if not eventos.exists():
        # Si no hay eventos, mostrar un mensaje para configurar un plan
        return render(request, 'start.html', {
            'plan_no_configurado': True,  # Indicador de que no hay plan
            'plan_url': reverse('luapol_app:event_list')  # Enlace a la página de configuración del plan
        })

    # Última actividad completada, ordenada por bloques y orden
    ultima_completada = eventos.filter(completado=True).order_by('block_number', 'order').last()

    # Si hay una actividad completada, buscar la siguiente actividad
    if ultima_completada:
        siguiente_actividad = eventos.filter(
            completado=False, 
            block_number__gte=ultima_completada.block_number, 
            order__gt=ultima_completada.order
        ).order_by('block_number', 'order').first()
    else:
        # Si no hay ninguna actividad completada, buscar la primera actividad pendiente
        siguiente_actividad = eventos.filter(completado=False).order_by('block_number', 'order').first()

    # Renderizar la plantilla con los datos
    return render(request, 'start.html', {
        'ultima_completada': ultima_completada.title if ultima_completada else None,  # Solo pasamos el título
        'siguiente': siguiente_actividad.title if siguiente_actividad else None,  # Solo pasamos el título
    })

@login_required
def event_list_view(request):
    user = request.user

    # Obtener todos los eventos del usuario y ordenarlos por block_number y order
    eventos = Event.objects.filter(user_fk=user).order_by('block_number', 'order')

    # Obtener todas las secciones relacionadas y organizarlas en un diccionario
    event_sections = {
        section.block_number: section for section in EventSection.objects.filter(block_number__in=eventos.values_list('block_number', flat=True))
    }

    # Organizar los eventos en una estructura anidada por sección y bloque
    eventos_por_seccion = {}
    for evento in eventos:
        block_number = evento.block_number.block_number
        print('block_number', block_number)

        # Obtener la sección del bloque desde el diccionario (si existe)
        event_section = event_sections.get(block_number)
        print('event_section', event_section)
        if event_section:
            section_id = event_section.block_section_id
            print('section_id', section_id)
            section_description = f"Sección {section_id}"
            block_description = event_section.block_description

            # Crear la estructura de la sección si no existe
            if section_id not in eventos_por_seccion:
                eventos_por_seccion[section_id] = {
                    'section_description': section_description,
                    'bloques': {}
                }

            # Crear la estructura del bloque si no existe en la sección
            if block_number not in eventos_por_seccion[section_id]['bloques']:
                eventos_por_seccion[section_id]['bloques'][block_number] = {
                    'block_description': block_description,
                    'eventos': []
                }

            # Añadir el evento al bloque correspondiente
            eventos_por_seccion[section_id]['bloques'][block_number]['eventos'].append(evento)

    # Verificar si se puede crear un nuevo bloque
    last_event = eventos.order_by('-block_number', '-order').first()
    can_create_block = not Event.objects.filter(user_fk=user, block_number=last_event.block_number, completado=False).exists() if last_event else True
    print(eventos_por_seccion)

    return render(request, 'event_list.html', {
        'eventos_por_seccion': eventos_por_seccion,
        'can_create_block': can_create_block
    })

def chat_view(request):
    return render(request, 'luapol_app.html')

########## START TEST ###########
@login_required
def test_start_view(request, test_id):

    test = get_object_or_404(Test, id=test_id)
    event = Event.objects.filter(test_fk=test).first()

    # Redirigir si el usuario proviene de un test
    shuffled_data = request.session.get('shuffled_data', [])
    if test.is_active:
        finalize_test(request, test, event)
        messages.success(request, 'Tu intento se ha marcado como completado y se te ha redirigido a la página principal.')
        return redirect('luapol_app:event_list')

    # Determinar si se pueden hacer más intentos
    test_to_review = test.oportunidades == 0

    if request.method == 'POST':
        if 'start_test' in request.POST:
            # Iniciar un nuevo intento
            test.is_active = True
            test.fecha_inicio = timezone.now()

            # Mezclar preguntas
            preguntas_test = list(test.preguntas_test.all())
            random.shuffle(preguntas_test)

            # Preparar datos mezclados para la sesión
            shuffled_data = []
            for pregunta_test in preguntas_test:
                respuestas = list(pregunta_test.pregunta_fk.respuestas.all())
                random.shuffle(respuestas)  # Mezclar respuestas

                # Crear la estructura con tuplas
                respuestas_con_tuplas = [(respuesta.id, respuesta.descripcion) for respuesta in respuestas]
                
                shuffled_data.append({
                    'test_fk': test.id,
                    'pregunta_fk': pregunta_test.pregunta_fk.id,
                    'respuestas': respuestas_con_tuplas,  # Almacenar directamente las tuplas
                })

                # Reiniciar respuestas seleccionadas y estado de corrección
                pregunta_test.respuesta_seleccionada_fk = None
                pregunta_test.es_correcta = False
                pregunta_test.save()

            # Almacenar los datos mezclados en la sesión
            request.session['shuffled_data'] = shuffled_data
            test.save()
            return redirect('luapol_app:test_detail', test_id=test.id)

    # Renderizar la plantilla de inicio de test
    return render(request, 'test_start.html', {
        'test': test,
        'test_to_review': test_to_review,
    })

@login_required
def test_detail_view(request, test_id):
    test = get_object_or_404(Test, id=test_id)
    shuffled_data = request.session.get('shuffled_data', [])

    if not test.is_active:
        messages.success(request, 'No tienes ningún test en activo. Se te ha redirigido a la página principal.')
        return redirect('luapol_app:event_list')
    
    # Calcular tiempo restante solo para SIMULATION
    if test.tipo == 'SIMULATION':
        remaining_time = request.session.get('remaining_time')
        if remaining_time is None:
            # Supongamos que la duración es de 30 minutos (1800 segundos)
            remaining_time = 60 # test.preguntas_test.all().count() * 60  Valor inicial en segundos
        else:
            remaining_time = int(remaining_time)
    else:
        remaining_time = None

    # Obtener preguntas y respuestas reordenadas
    questions_with_responses = get_shuffled_data(shuffled_data)

    if request.method == 'POST':
        form = TestForm(questions_with_responses=questions_with_responses, data=request.POST)
        if form.is_valid():
            test.aciertos = 0
            for question_data in questions_with_responses:
                pregunta_test = question_data['pregunta_test']
                respuesta_seleccionada_id = form.cleaned_data.get(f'pregunta_{pregunta_test.pregunta_fk.id}')
                respuesta = None

                if respuesta_seleccionada_id:
                    respuesta = Respuestas.objects.get(id=respuesta_seleccionada_id)
                    pregunta_test.es_correcta = respuesta.es_correcta
                    if respuesta.es_correcta:
                        test.aciertos += 1
                else:
                    pregunta_test.es_correcta = False

                pregunta_test.respuesta_seleccionada_fk = respuesta
                pregunta_test.save()

            test.aprobado = test.aciertos >= len(shuffled_data) / 2
            test.save()

            if 'exit_btn' in request.POST:
                event = Event.objects.filter(test_fk=test, is_review=False).first()
                finalize_test(request, test, event)
                return redirect('luapol_app:event_list')
            elif 'submit_btn' in request.POST:
                return redirect('luapol_app:confirm_test', test_id=test_id)
    else:
        form = TestForm(questions_with_responses=questions_with_responses)

    return render(request, 'test_detail.html', {
        'form': form,
        'test': test,
        'remaining_time': remaining_time,
    })

@csrf_exempt
def test_save_remaining_time_view(request, test_id):
    test = get_object_or_404(Test, id=test_id)
    if request.method == "POST":
        data = json.loads(request.body)
        remaining_time = data.get('remaining_time')
        if test.is_active:
            if remaining_time is not None:
                request.session['remaining_time'] = remaining_time
                return JsonResponse({"status": "success"})
            else:
                request.session['remaining_time'] = None
        return JsonResponse({"status": "error", "message": "No remaining_time provided"}, status=400)

@login_required
def confirm_test_view(request, test_id):
    test = get_object_or_404(Test, id=test_id)
    event = Event.objects.filter(test_fk=test, is_review=False).first()

    if not test.is_active:
        messages.success(request, 'No tienes ningún test en activo. Se te ha redirigido a la página principal.')
        return redirect('luapol_app:event_list')

    # Calcular tiempo restante solo para SIMULATION
    if test.tipo == 'SIMULATION':
        remaining_time = request.session.get('remaining_time')
        if remaining_time:
            remaining_time = int(remaining_time)
    else:
        remaining_time = None

    # Obtener preguntas y respuestas mezcladas de la sesión
    shuffled_data = request.session.get('shuffled_data', [])

    # Obtener preguntas y respuestas utilizando get_shuffled_data
    questions_with_responses = get_shuffled_data(shuffled_data)

    # Inicializar el formulario
    form = ConfirmTestForm(questions_with_responses=questions_with_responses)

    if request.method == 'POST':
        if 'confirm_btn' in request.POST:
            finalize_test(request, test, event)
            return redirect('luapol_app:test_analysis', test_id=test.id)

        elif 'back_btn' in request.POST:
            return redirect('luapol_app:test_detail', test_id=test.id)

    return render(request, 'test_confirmation.html', {
        'test': test,
        'form': form,  # Pasar el formulario al template
        'remaining_time': remaining_time,
    })

@login_required
def finalize_test_view(request, test_id):
    if request.method == 'POST':
        test = get_object_or_404(Test, id=test_id)
        event = Event.objects.filter(test_fk=test, is_review=False).first()

        # Finalizar el examen
        finalize_test(request, test, event)

        # Redirigir al usuario después de finalizar
        return redirect('luapol_app:event_list')

    return JsonResponse({'error': 'Método no permitido'}, status=405)

@login_required
def test_detail_review_view(request, test_id):
    test = get_object_or_404(Test, id=test_id)

    preguntas_test = PreguntaTest.objects.filter(test_fk=test).order_by('id')

    return render(request, 'test_detail_review.html', {
        'test': test,
        'preguntas_test': preguntas_test,
    })

@login_required
def test_analysis_view(request, test_id):
    test = get_object_or_404(Test, id=test_id)
    event = Event.objects.filter(test_fk=test).first()
    preguntas_test = test.preguntas_test.all()

    # Obtener los subtemas fallados asociados al test
    testSubtemaFallados = TestSubtemaFallado.objects.filter(test_fk=test)

    # Calcular preguntas incorrectas
    preguntas_incorrectas = len(preguntas_test) - test.aciertos

    # Agrupar fallos por tema y subtemas
    fallos_por_tema = (
        testSubtemaFallados
        .values('subtema_fk__study_topic_fk__description', 'subtema_fk__study_topic_fk__id')
        .annotate(total_fallos=Sum('fallos'))
        .order_by('-total_fallos')
    )

    fallos_por_subtema = (
        testSubtemaFallados
        .values('subtema_fk__study_topic_fk__id', 'subtema_fk__subtopic_description')
        .annotate(total_fallos=Sum('fallos'))
        .order_by('-total_fallos')
    )

    return render(request, 'test_analysis.html', {
        'test': test,
        'event': event,
        'testSubtemaFallados': testSubtemaFallados,
        'preguntas_incorrectas': preguntas_incorrectas,
        'preguntas_test': preguntas_test,
        'fallos_por_tema': fallos_por_tema,
        'fallos_por_subtema': fallos_por_subtema,
    })

########## END TEST ###########

########## START REPORTS ###########

def list_reports_view(request):
    return render(request, 'reports_start.html')

@login_required
def general_progress_view(request):
    user = request.user

    # Reportes personal y global
    indivual_report = general_progress_report_individual(user=user)
    global_report = general_progress_report_global()

    context = {
        'personal_meses': json.dumps(indivual_report['meses']),
        'personal_dias_por_mes': json.dumps(indivual_report['dias_por_mes']),
        'dias_consecutivos': indivual_report['dias_consecutivos'],
        'semanas_consecutivas': indivual_report['semanas_consecutivas'],
        'calendario': json.dumps(indivual_report['calendario']),
        'media_dias_por_mes': json.dumps(global_report['media_dias_por_mes']),
    }

    return render(request, 'report_general_progress.html', context)

@login_required
def average_attempts_view(request):
    """
    Vista que genera el reporte de intentos agrupados por evento, bloque y sección.
    """
    user = request.user

    # Unificar datos individuales y globales
    report = attempts_report(user=user)

    context = {
        'intentos_por_evento': report['intentos_por_evento'],
        'intentos_por_bloque': report['intentos_por_bloque'],
        'intentos_por_seccion': report['intentos_por_seccion'],
    }

    return render(request, 'report_average_attempts.html', context)

@login_required
def user_ranking_view(request):
    """
    Vista que muestra el ranking de alumnos basado en intentos promedio.
    """
    # Obtener el ranking
    ranking_queryset = generate_user_ranking()

    # Configurar paginador
    paginator = Paginator(ranking_queryset, 10)  # 10 elementos por página
    page_number = request.GET.get('page')  # Número de página actual desde la URL
    ranking = paginator.get_page(page_number)  # Obtener la página actual

    return render(request, 'report_user_ranking.html', {
        'ranking': ranking,
    })

########## END REPORTS ###########

@login_required
def profile_view(request):
    user = request.user
    return render(request, 'profile.html', {'user': user})

@login_required
def change_password_view(request):
    if request.method == 'POST':
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Importante para que el usuario no sea desconectado
            messages.success(request, 'Tu contraseña ha sido actualizada con éxito.')
            return redirect('luapol_app:my_profile')  # Redirigir al perfil después de cambiar la contraseña
        else:
            messages.error(request, 'Por favor, corrige los errores a continuación.')
    else:
        form = PasswordChangeForm(user=request.user)

    return render(request, 'change_password.html', {'form': form})

@login_required
def edit_profile_view(request):
    if request.method == 'POST':
        form = EditProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated successfully.')
            return redirect('mi_perfil')
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = EditProfileForm(instance=request.user)

    return render(request, 'edit_profile.html', {'form': form})

def privacy_policy_view(request):
    return render(request, 'privacy_policy.html')

@login_required
def delete_event_view(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        event_id = data.get('id')

        try:
            event = Event.objects.get(id=event_id, user_fk=request.user)
            event.delete()
            return JsonResponse({'success': True})
        except Event.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Event not found'}, status=404)

    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)


@login_required
def new_block_view(request):
    user = request.user
    study_availability = StudyAvailability.objects.get(user_oto=user)
    generate_study_plan(study_availability, request)
    return redirect('luapol_app:event_list')

def create_block_view(request):
    # Obtener el usuario actual y la disponibilidad de estudio, o crearla si no existe
    study_availability, created = StudyAvailability.objects.get_or_create(user_oto=request.user)

    # Manejo de la opción seleccionada con el formulario
    if request.method == 'POST':
        form = StudyAvailabilityForm(request.POST, instance=study_availability)
        if form.is_valid():
            study_availability = form.save()

            # Redirigir a la lista de eventos después de guardar
            if study_availability.study_mode == 'study':
                generate_study_plan(study_availability, request)
            elif study_availability.study_mode == 'tests':
                generate_test_plan(study_availability, request)

            messages.success(request, "Bloque creado con éxito.")
            return redirect('luapol_app:event_list')
    else:
        form = StudyAvailabilityForm(instance=study_availability)

    # Renderizar la página de selección
    return render(request, 'create_block.html', {'form': form})
    
@login_required
def complete_review_view(request, test_id):
    if request.method == 'POST':
        # Obtener el test asociado
        test = get_object_or_404(Test, id=test_id)

        # Buscar el evento de revisión relacionado con este test
        review_event = Event.objects.filter(test_fk=test, is_review=True).first()

        if review_event:
            # Marcar el evento como completado
            review_event.completado = True
            review_event.save()
            messages.success(request, 'El análisis ha sido completado y el evento de revisión ha sido marcado como completado.')

            # Llamar a unlock_next_event para desbloquear el siguiente evento
            unlock_next_event(review_event)

        else:
            messages.error(request, 'No se encontró un evento de revisión asociado a este test.')

        # Redirigir de vuelta al análisis del test
        return redirect('luapol_app:event_list')
    else:
        # Si no es una solicitud POST, devolver un error de mala solicitud
        return HttpResponseBadRequest('Solicitud no válida.')

@login_required
def preguntas_favoritas_view(request):
    # Filtrar las preguntas que están marcadas como favoritas por el usuario actual
    preguntas_favoritas = PreguntaTest.objects.filter(test_fk__usuario_fk=request.user, es_favorita=True)

    # Pasar las preguntas favoritas al contexto
    return render(request, 'preguntas_favoritas.html', {
        'preguntas_favoritas': preguntas_favoritas,
    })

@login_required
def toggle_favorita(request, pregunta_test_id):
    pregunta_test = get_object_or_404(PreguntaTest, id=pregunta_test_id)

    # Solo el dueño del test puede modificar los favoritos
    if pregunta_test.test_fk.usuario_fk != request.user:
        return JsonResponse({'error': 'No autorizado'}, status=403)

    # Alternar el valor de es_favorita
    pregunta_test.es_favorita = not pregunta_test.es_favorita
    pregunta_test.save()

    return JsonResponse({'favorita': pregunta_test.es_favorita})

########## START FORUM ###########

@login_required
def forum_entries_for_question(request):
    pregunta_id = request.GET.get('pregunta', '')
    test_id = request.GET.get('test_id', '')

    # Busca las entradas del foro relacionadas con la pregunta específica
    entradas_relacionadas = ForoBase.objects.filter(foropregunta__id_pregunta_fk__id_pregunta=pregunta_id
    ).order_by('-fecha_creacion')

    # Obtén la descripción de la pregunta
    pregunta = get_object_or_404(Preguntas, id_pregunta=pregunta_id)

    return render(request, 'forum_entries_for_question.html', {
        'entradas': entradas_relacionadas,
        'pregunta': pregunta,
        'test_id': test_id,
    })

@login_required
def forum_newPregunta_view(request):
    pregunta_id = request.GET.get('pregunta', '')
    test_id = request.GET.get('test_id', '')

    pregunta_relacionada = get_object_or_404(Preguntas, id_pregunta=pregunta_id)
    test = get_object_or_404(Test, id=test_id)

    if request.method == 'POST':
        form = ForoPreguntaForm(request.POST, initial={'user': request.user})
        if form.is_valid():
            new_entry = form.save(commit=False)
            new_entry.id_pregunta_fk = pregunta_relacionada
            new_entry.save()
            messages.success(request, 'La nueva entrada se creó exitosamente.')
            return redirect('luapol_app:test_detail_review', test_id=test.id)
        else:
            messages.error(request, 'Hubo un error al crear la entrada. Revisa el formulario.')
    else:
        form = ForoPreguntaForm(initial={'user': request.user})

    return render(request, 'forum_new_pregunta.html', {
        'form': form,
        'test_id': test_id,
        'pregunta_id': pregunta_id,
        'descripcion_pregunta': pregunta_relacionada.pregunta,
    })

@login_required
def forum_newGeneral_view(request):
    form = ForoGeneralForm(initial={'user': request.user})
    if request.method == 'POST':
        form = ForoGeneralForm(request.POST, initial={'user': request.user})
        if form.is_valid():
            new_entry = form.save(commit=True)
            messages.success(request, 'La nueva entrada general se creó exitosamente.')
            return redirect('luapol_app:forum_list')
        else:
            messages.error(request, 'Hubo un error al crear la entrada. Revisa el formulario.')

    return render(request, 'forum_new_general.html', {
        'form': form,
    })

@login_required
def forum_list_view(request):
    filtro = request.GET.get('filtro', 'all')
    tema_id = request.GET.get('tema', 'all')  # Tema seleccionado desde el desplegable

    # Filtrar las entradas según el tipo
    if filtro == 'preguntas':
        entradas = ForoBase.objects.filter(foropregunta__isnull=False).order_by('-fecha_creacion')
    elif filtro == 'general':
        entradas = ForoBase.objects.filter(forogeneral__isnull=False).order_by('-fecha_creacion')
    else:  # Mostrar todas las entradas
        entradas = ForoBase.objects.all().order_by('-fecha_creacion')

    # Aplicar el filtro por tema
    if tema_id != 'all':
        entradas = entradas.filter(
            Q(forogeneral__id_tema_fk_id=tema_id) |  # Filtro para entradas generales
            Q(foropregunta__id_pregunta_fk__subtema_fk__study_topic_fk_id=tema_id)  # Filtro para preguntas relacionadas con el tema
        )

    # Anotar el número de respuestas y el total de "me gusta"
    entradas = entradas.annotate(
        num_respuestas=Count('mensajes'),
        total_megusta=F('likes') + Coalesce(Sum('mensajes__likes'), 0)
    )

    # Paginación: 10 entradas por página
    paginator = Paginator(entradas, 10)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Obtener todos los temas de la tabla StudyTopic
    temas = StudyTopic.objects.all()

    return render(request, 'forum_list.html', {
        'entradas': page_obj,
        'filtro': filtro,
        'temas': temas,  # Pasar los temas al template
        'tema_id': tema_id,  # Pasar el tema seleccionado al template
    })

@login_required
def forum_detail_view(request, entrada_id):
    # Buscar la entrada directamente en ForoBase
    entrada = get_object_or_404(ForoBase, id=entrada_id)

    # Obtener mensajes relacionados
    mensajes = ForoMensajes.objects.filter(foro_base_fk=entrada).order_by('fecha_publicacion')

    if request.method == 'POST':
        form = ForoMensajeForm(request.POST)
        if form.is_valid():
            mensaje = form.save(commit=False)
            # Asociar el mensaje a la entrada de ForoBase
            mensaje.foro_base_fk = entrada
            mensaje.autor_fk = request.user
            mensaje.save()
            return redirect('luapol_app:forum_detail', entrada_id=entrada.id)
    else:
        form = ForoMensajeForm()

    return render(request, 'forum_detail.html', {
        'entrada': entrada,
        'mensajes': mensajes,
        'form': form,
    })

@login_required
def toggle_forum_megusta_view(request, object_type, object_id):
    if object_type == 'entrada':
        # Buscar en ForoBase
        objeto = get_object_or_404(ForoBase, id=object_id)
    elif object_type == 'mensaje':
        # Buscar en ForoMensajes
        objeto = get_object_or_404(ForoMensajes, id=object_id)
    else:
        return JsonResponse({"error": "Tipo de objeto no válido."}, status=400)

    # Manejar "me gusta"
    like, created = ForoMeGusta.objects.get_or_create(
        usuario_fk=request.user,
        foro_base_fk=objeto if object_type == 'entrada' else None,
        foro_mensaje_fk=objeto if object_type == 'mensaje' else None,
    )

    if not created:
        like.delete()
        objeto.likes -= 1
    else:
        objeto.likes += 1

    objeto.save()
    return JsonResponse({"likes": objeto.likes})


########## END FORUM ###########

########## START NOTIFICATIONS ###########

@login_required
def notifications(request):
    """
    Muestra todas las notificaciones del usuario con paginación.
    """
    notifications_list = Notifications.objects.filter(user_fk=request.user).order_by('-created_at')
    paginator = Paginator(notifications_list, 10)  # 10 notificaciones por página

    page_number = request.GET.get('page', 1)  # Obtén el número de página de la URL
    notifications = paginator.get_page(page_number)

    return render(request, 'notifications.html', {'notifications': notifications})

@login_required
def check_notifications(request):
    """
    Verifica si el usuario tiene notificaciones no leídas.
    """
    has_unread = Notifications.objects.filter(user_fk=request.user, is_read=False).exists()
    return JsonResponse({"has_unread": has_unread})

@login_required
def notification_detail(request, notification_id):
    """
    Devuelve los detalles de una notificación en formato JSON y la marca como leída.
    """
    try:
        notification = Notifications.objects.get(id=notification_id, user_fk=request.user)
        notification.is_read = True  # Marcar como leída
        notification.save()

        return JsonResponse({
            "subject": notification.subject,
            "message": notification.message,
            "created_at": notification.created_at.strftime("%d %b %Y, %H:%M")
        })
    except Notifications.DoesNotExist:
        return JsonResponse({"error": "Notificación no encontrada."}, status=404)

########## END NOTIFICATIONS ###########

def delete_all_blocks(user):
    """
    Elimina todos los bloques de eventos y sus dependencias, incluyendo los eventos de revisión y secciones de eventos.
    Si se proporciona un usuario, borra solo los eventos asociados a ese usuario.
    """
    # Filtrar eventos por usuario
    events = Event.objects.filter(user_fk=user)
    
    deleted_count = 0  # Contador para eventos eliminados
    block_numbers_to_delete = set()  # Conjunto para almacenar los block_numbers únicos

    # Recorrer todos los eventos y borrar cada uno junto con sus dependencias si existen
    for event in events:
        # Almacenar el block_number del evento actual para la eliminación de la sección
        block_numbers_to_delete.add(event.block_number)

        try:
            # Verificar si el `Event` tiene un `Test` asociado de manera segura
            if event.test_fk:
                test = event.test_fk
                pregunta_tests = PreguntaTest.objects.filter(test_fk=test)
                preguntas_ids = pregunta_tests.values_list('pregunta_fk_id', flat=True)

                # Borrar los resultados y preguntas vinculadas al `Test`
                ResultadoTest.objects.filter(pregunta_fk_id__in=preguntas_ids).delete()
                pregunta_tests.delete()
                test.delete()
                
        except Test.DoesNotExist:
            pass
    

        # Finalmente, borrar el evento en sí
        event.delete()
        deleted_count += 1

    # Borrar las secciones de eventos correspondientes a los block_numbers eliminados
    EventSection.objects.filter(block_number__in=block_numbers_to_delete).delete()

    # Retornar la cantidad de eventos eliminados para confirmación
    return deleted_count

@login_required
def delete_blocks_view(request):
    # Llamar a `delete_all_blocks` para borrar todos los eventos y dependencias del usuario actual
    deleted_count = delete_all_blocks(user=request.user)

    # Agregar un mensaje de confirmación
    messages.success(request, f"Se han eliminado {deleted_count} bloques de eventos y sus dependencias.")

    # Redirigir a la lista de eventos u otra página después de borrar los bloques
    return redirect('luapol_app:event_list')

