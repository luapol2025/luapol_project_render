from django.utils.crypto import get_random_string
from django.core.mail import send_mail
from django.urls import reverse
from .models import UserProfile, Event, Preguntas, Respuestas, ResultadoTest, Test, Preguntas, PreguntaTest, StudyAvailability, TestSubtemaFallado, PreguntasPorTema, StudyTopic, EventSection, UserAttemptsByDay, User
from datetime import datetime, timedelta
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
from django.shortcuts import render
import os, csv, random, json, math, uuid
from datetime import datetime, timedelta
from django.db.models import Q, Avg, Count, Sum, Count, F, FloatField, Subquery, OuterRef
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, Coalesce

########### REGISTER ############ 

def send_verification_email(user):
    user_profile = UserProfile.objects.get(user_oto=user)
    user_profile.activation_token = uuid.uuid4()  # genera un token nuevo
    user_profile.save()
    verification_link = reverse('luapol_app:verify_email', kwargs={
        'user_id': user.id,
        'token': user_profile.activation_token
    })
    verification_url = f'{settings.PROTOCOL}://{settings.DOMAIN}{verification_link}'
    subject = 'Confirma tu cuenta en Luapol'
    message = (
        f'Hola {user.username},\n\n'
        f'Gracias por registrarte en Luapol.\n'
        f'Por favor, confirma tu cuenta haciendo clic en el siguiente enlace:\n\n'
        f'{verification_url}\n\n'
        f'Si no solicitaste esta cuenta, ignora este mensaje.'
    )
    from_email = settings.EMAIL_HOST_USER
    recipient_list = [user.email]
    send_mail(subject, message, from_email, recipient_list)

########### GENERATE STUDY PLAN ############ 
def generate_study_plan(study_availability, request):
    order = 1  # Orden del evento dentro del bloque
    user = study_availability.user_oto
    block = user.id * 1000 + 1  # Número del bloque
    locked = False  # Controla si el evento está bloqueado inicialmente

    # Obtener las secciones disponibles para el usuario
    sections = StudyTopic.objects.values('section_id').distinct()

    for section in sections:
        descriptions_in_section = []
        title_numbers_in_section = []
        section_id = section['section_id']
        topics_in_block = 2

        # Filtrar temas que pertenezcan a la sección actual y obtener `title_number` y `description`
        topics = StudyTopic.objects.filter(section_id=section_id).order_by('title_number')

        # Dividir los temas en bloques de 2
        for i in range(0, len(topics), topics_in_block):
            topics_block = topics[i:i+topics_in_block]  # Obtener un bloque de hasta 2 temas
            title_numbers_in_block = []
            descriptions_in_block = []

            # Crear el event_section del bloque
            ''' Primero creamos el event section porque block number es principal de la tabla event_section y por lo tanto debe existir antes 
                que en la tabla event '''
            descriptions_in_block = [topic.description for topic in topics_block]
            # Descripciones unidas por comas después de procesar todos los temas en el bloque
            block_description = ", ".join(descriptions_in_block)
            save_event_section(section_id, block, block_description)

            # Test y revisión para cada tema individual en el bloque     
            for topic in topics_block:
                # Añadir la descripción del tema a la lista
                descriptions_in_block.append(topic.description)
                
                # Manejo de title_number y listas de números de temas
                title_number = [topic.title_number]
                title_numbers_in_block.extend(title_number)

                # Crear test individual y revisión para el tema
                test_individual = schedule_partial_event(user, title_number, order, block, locked)
                order += 1
                locked = True  # Bloquear el siguiente evento

                # Verificar si solo hay un tema en el bloque
                if len(topics_block) == 1:
                    break  # Salir del bucle después de la primera iteración

            # Manejo de title_number y listas de números de temas
            descriptions_in_section.extend(descriptions_in_block)
            title_numbers_in_section.extend(title_numbers_in_block)

            # Simulación del bloque de 2 temas
            simulation_partial = schedule_partial_simulation_event(user, title_numbers_in_block, order, block, request, locked)
            order += 1

            # Avanzar al siguiente bloque
            block += 1
            order = 1

        # solo crear bloque de sección si hay más de un bloque en la sección
        if len(title_numbers_in_section) > topics_in_block:

            # Al final de todos los bloques de la sección, crear el bloque de revisión de la sección completa        
            final_block_description = ", ".join(descriptions_in_section)

            # Crear el event_section
            ''' Primero creamos el event section porque block number es principal de la tabla event_section y por lo tanto debe existir antes 
                que en la tabla event '''
            save_event_section(section_id, block, final_block_description)
            
            # Primer test de todos los temas de la sección
            test_1_seccion = schedule_partial_event(user, title_numbers_in_section, order, block, locked)
            order += 1

            # Segundo test de todos los temas de la sección
            test_2_seccion = schedule_partial_event(user, title_numbers_in_section, order, block, locked)
            order += 1

            # Simulación de todos los temas de la sección
            simulation_section = schedule_partial_simulation_event(user, title_numbers_in_section, order, block, request, locked)
            order += 1
            
        # Avanzar al siguiente bloque y resetear `order`
        block += 1 
        order = 1

    # Programar un bloque de test completos
    generate_test_plan(study_availability, request)

def generate_test_plan(study_availability, request):
    
    user=study_availability.user_oto

    order = 1
    block = 1
    section = 1

    last_event = Event.objects.filter(user_fk=user).order_by('-block_number').first()
    if last_event:
        block = last_event.block_number + 1  # Start the next block after the last one
    
    # Obtener la última sección
    last_section = EventSection.objects.order_by('-block_section_id').first()
    if last_section:
        section = last_section.section_id + 1

    locked = section != 1  # Controla si el evento está bloqueado inicialmente 

    # Crear el event_section
    ''' Primero creamos el event section porque block number es principal de la tabla event_section y por lo tanto debe existir antes 
     que en la tabla event '''
    save_event_section(section, block, 'Tests Completos')

        
    # Programar los eventos de la semana en secuencia
    # Test 1 (desbloqueado inicialmente)
    test_1 = schedule_practice_event(user, order, block, locked)
    order += 1

    # Test 2 (bloqueado inicialmente)
    test_2 = schedule_practice_event(user, order, block, True)
    order += 1

    # Día de descanso (sin evento programado)

    # Simulacro (bloqueado inicialmente)
    simulation = schedule_simulation_event(user, order, block, request, True)
    order += 1

    return None

def schedule_practice_event(user, order, block, locked):
    # Crear el test a través de la función centralizada `create_test_view`
    test = create_practice_test(user)

    test_description = 'Práctica'
    event_title = f"Test de {test_description}"
    event_description = f"Test de {test_description}"
    is_review = False

    save_event(event_title, event_description, user, test, locked, order, block, is_review)

    return test

def schedule_simulation_event(user, order, block, request, locked):
    # Crear el test a través de la función centralizada `create_test_view`
    test = create_simulation_test(user, request)

    # Descripción del evento
    test_description = 'Simulación'
    event_title = f"Test de {test_description}"
    event_description = f"Test de {test_description}"
    is_review = False

    save_event(event_title, event_description, user, test, locked, order, block, is_review)

    return test

def schedule_partial_event(user, title_numbers, order, block, locked):
    # Crear el test usando `title_numbers` directamente como una lista de enteros
    test = create_partial_test(user, title_numbers)

    # Convertir `title_numbers` en una lista de cadenas para construir el título
    titles_str = ", ".join(map(str, title_numbers))

    # Consultar las descripciones de cada `title_number`
    descriptions = StudyTopic.objects.filter(title_number__in=title_numbers).values_list('description', flat=True)
    descriptions_str = "; ".join(descriptions)
    tema_str = 'Tema' if len(title_numbers) == 1 else 'Temas'

    # Construir el título y descripción del evento usando `title_numbers` y `descriptions`
    event_title = f"Test Parcial: {tema_str} {titles_str}"
    event_description = f"Test parcial de los temas {titles_str}: {descriptions_str}"
    is_review = False

    # Guardar el evento
    save_event(event_title, event_description, user, test, locked, order, block, is_review)

    return test

def schedule_partial_simulation_event(user, title_numbers, order, block, request, locked):
    # Crear el test de simulación usando `title_numbers` directamente como una lista de enteros
    test = create_partial_simulation_test(user, title_numbers, request)

    # Convertir `title_numbers` en una lista de cadenas para construir el título
    titles_str = ", ".join(map(str, title_numbers))

    # Consultar las descripciones de cada `title_number`
    descriptions = StudyTopic.objects.filter(title_number__in=title_numbers).values_list('description', flat=True)
    descriptions_str = "; ".join(descriptions)
    tema_str = 'Tema' if len(title_numbers) == 1 else 'Temas'

    # Construir el título y descripción del evento usando `title_numbers` y `descriptions`
    event_title = f"Test Simulación: {tema_str} {titles_str}"
    event_description = f"Test simulación: {tema_str} {descriptions_str}"
    is_review = False

    # Guardar el evento
    save_event(event_title, event_description, user, test, locked, order, block, is_review)

    return test

def save_event(event_title, event_description, user, test, locked, order, block, is_review):
    
    # Crear el evento
    Event.objects.create(
        title=event_title,
        description=event_description,
        user_fk=user,
        test_fk=test,
        locked=locked,
        order=order,
        block_number=block,
        is_review=is_review
    )

def save_event_section(section_id, block_number, block_description):
    
    # Crear el event_section
    event_section = EventSection.objects.create(
        block_section_id=section_id,
        block_number=block_number,
        block_description=block_description
    )

    return event_section

def get_questions(anio, cantidad_total):
    """
    Cargar preguntas del syllabus según el año y seleccionar la cantidad adecuada
    de preguntas según la proporción por tema, ajustando al final para asegurar
    que se seleccionen exactamente 'cantidad_total' preguntas.
    """
    syllabus_data = leer_syllabus()  # Obtener datos del syllabus por tema
    preguntas_seleccionadas = []
    temas_pendientes = []

    total_preguntas_seleccionadas = 0

    # Recorremos los temas en lugar de subtemas
    for tema, data in syllabus_data.items():
        proporcion_tema = data['proporciones_por_anio'].get(anio, 0)  
        num_preguntas_a_seleccionar = math.floor(proporcion_tema * cantidad_total)  # Usamos floor para redondear hacia abajo

        preguntas_relacionadas = list(Preguntas.objects.filter(subtema_fk__study_topic_fk=tema))

        # Verificar si hay suficientes preguntas para el tema
        if len(preguntas_relacionadas) < num_preguntas_a_seleccionar:
            raise ValueError(f"No hay suficientes preguntas para el tema {data['tema']}.")

        # Añadimos este tema a la lista pendiente si necesita ajustar el número de preguntas
        temas_pendientes.append({
            'tema': tema,
            'preguntas': preguntas_relacionadas,
            'a_seleccionar': num_preguntas_a_seleccionar
        })

        total_preguntas_seleccionadas += num_preguntas_a_seleccionar

    # Ajuste para asegurar que seleccionamos exactamente 'cantidad_total' preguntas
    preguntas_restantes = cantidad_total - total_preguntas_seleccionadas

    for tema in sorted(temas_pendientes, key=lambda x: len(x['preguntas']), reverse=True):
        if preguntas_restantes <= 0:
            break
        # Seleccionar una pregunta extra hasta alcanzar 'cantidad_total'
        tema['a_seleccionar'] += min(preguntas_restantes, len(tema['preguntas']) - tema['a_seleccionar'])
        preguntas_restantes -= tema['a_seleccionar'] - math.floor(proporcion_tema * cantidad_total)

    # Seleccionar preguntas finales de cada tema
    for tema in temas_pendientes:
        preguntas_seleccionadas.extend(random.sample(tema['preguntas'], tema['a_seleccionar']))

    return preguntas_seleccionadas

# Función de soporte para crear un test y asociar las preguntas seleccionadas
def create_test_questions(user, test_type, preguntas_aleatorias):

    nuevo_test = Test.objects.create(usuario_fk=user, tipo=test_type)
    for pregunta in preguntas_aleatorias:
        PreguntaTest.objects.create(test_fk=nuevo_test, pregunta_fk=pregunta)
    return nuevo_test

# Función para crear simulación (SIMULATION)
def create_simulation_test(user, request):
    anio = random.choice(['2023', '2022', '2021', '2020'])
    preguntas_aleatorias = get_questions(anio, 10)

    nuevo_test = create_test_questions(user, 'SIMULATION', preguntas_aleatorias)

    # Gestión del temporizador en la sesión
    request.session['simulation_test_id'] = nuevo_test.id
    request.session['remaining_time'] = 50 * 60  # 50 minutos
    messages.info(request, f'El test se ha creado basado en la estructura de preguntas del año {anio}.')

    return nuevo_test

# Función para crear prueba práctica (PRACTICE)
def create_practice_test(user):
    anio = random.choice(['2023', '2022', '2021', '2020'])
    preguntas_aleatorias = get_questions(anio, 10)

    nuevo_test = create_test_questions(user, 'PRACTICE', preguntas_aleatorias)

    return nuevo_test

def create_partial_test(user, titles):
    preguntas_aleatorias = []

    # Iterar sobre cada título en la lista
    for title in titles:
        preguntas_relacionadas = Preguntas.objects.filter(subtema_fk__study_topic_fk__title_number=title)
        preguntas_aleatorias.extend(random.sample(list(preguntas_relacionadas), 2))

    nuevo_test = create_test_questions(user, 'PARTIAL', preguntas_aleatorias)

    return nuevo_test

# Función para crear simulación (SIMULATION)
def create_partial_simulation_test(user, titles, request):
    preguntas_aleatorias = []

    # Iterar sobre cada título en la lista
    for title in titles:
        preguntas_relacionadas = Preguntas.objects.filter(subtema_fk__study_topic_fk__title_number=title)
        preguntas_aleatorias.extend(random.sample(list(preguntas_relacionadas), 2))

    # Crear el test con 1 oportunidad para SIMULATION
    nuevo_test = create_test_questions(user, 'SIMULATION', preguntas_aleatorias)

    # Gestión del temporizador en la sesión
    simulation_seconds = 30 * len(preguntas_aleatorias)
    request.session['simulation_test_id'] = nuevo_test.id
    request.session['remaining_time'] = simulation_seconds 

    return nuevo_test

def leer_syllabus():
    syllabus_data = {}

    # Inicializamos una estructura para acumular los totales de preguntas por año
    total_preguntas_por_anio = {
        '2023': 0,
        '2022': 0,
        '2021': 0,
        '2020': 0,
    }

    # Obtener todas las preguntas por tema de la base de datos
    preguntas_por_tema = PreguntasPorTema.objects.all()

    # Recorrer las preguntas por tema y año
    for pregunta in preguntas_por_tema:
        tema_id = pregunta.tema_fk.id  # Usar el ID del tema
        anio = str(pregunta.anio)  # Convertir el año a cadena
        numero_preguntas = pregunta.numero_preguntas

        # Acumular el total de preguntas por año
        total_preguntas_por_anio[anio] += numero_preguntas

        # Si el tema no está en syllabus_data, inicializamos su estructura
        if tema_id not in syllabus_data:
            syllabus_data[tema_id] = {
                'preguntas_por_anio': {
                    '2023': 0,
                    '2022': 0,
                    '2021': 0,
                    '2020': 0
                }
            }

        # Añadir el número de preguntas para el año correspondiente
        syllabus_data[tema_id]['preguntas_por_anio'][anio] += numero_preguntas

    # Calcular las proporciones para cada tema con respecto al total por año
    for tema_id, data in syllabus_data.items():
        proporciones_por_anio = {}
        for anio in total_preguntas_por_anio.keys():
            total_anio = total_preguntas_por_anio[anio]
            if total_anio > 0:
                # Calculamos la proporción de preguntas para este tema respecto al total
                proporciones_por_anio[anio] = data['preguntas_por_anio'][anio] / total_anio
            else:
                proporciones_por_anio[anio] = 0  # Evitamos la división por cero

        # Añadir la proporción calculada al tema
        syllabus_data[tema_id]['proporciones_por_anio'] = proporciones_por_anio

    return syllabus_data

def generate_test_review_report(test):

    # Limpiar entradas existentes en TestSubtemaFallado para este test
    TestSubtemaFallado.objects.filter(test_fk=test).delete()

    preguntas_test = test.preguntas_test.all()
    subtemas_fallados = {}

    # Registrar los subtemas fallados
    for pregunta_test in preguntas_test:
        if not pregunta_test.es_correcta:
            # Access the SubTopic instance directly
            subtema_instance = pregunta_test.pregunta_fk.subtema_fk  # This fetches the full SubTopic instance

            # Track the fallos for the subtema
            if subtema_instance in subtemas_fallados:
                subtemas_fallados[subtema_instance] += 1
            else:
                subtemas_fallados[subtema_instance] = 1

    # Guardar los subtemas fallados en TestSubtemaFallado
    for subtema_instance, fallos in subtemas_fallados.items():
        # Create TestSubtemaFallado with the full SubTopic instance
        TestSubtemaFallado.objects.create(test_fk=test, subtema_fk=subtema_instance, fallos=fallos)

    return subtemas_fallados

def unlock_next_event(current_event):
    # Obtener el siguiente evento en la secuencia basado en el campo `order`
    next_event = Event.objects.filter(
        user_fk=current_event.user_fk,
        order__gt=current_event.order,  # Buscar eventos con un orden mayor al actual
        locked=True
    ).order_by('order').first()

    if next_event:
        # Desbloquear el siguiente evento
        next_event.locked = False
        next_event.save()

def finalize_test(request, test, event):
    
    test.fecha_submision = timezone.now()
    test.is_active = False
    test.oportunidades += 1
    test.save()

    # Generar reporte del test
    generate_test_review_report(test)

    # Marcar evento asociado como completado y desbloquear el siguiente
    if event:
        if test.aprobado:
            event.completado = True
            event.save()
            unlock_next_event(event)

    # Limpiar la sesión
    request.session.pop('shuffled_data', None)
    request.session.pop('remaining_time', None)

    # Actualizar o crear un registro de intentos
    attempt, created = UserAttemptsByDay.objects.get_or_create(
        user_fk=test.usuario_fk,
        defaults={'attempt_count': 1}
    )
    if not created:
        attempt.attempt_count += 1
        attempt.save()

def get_shuffled_data(shuffled_data):
    questions_with_responses = []
    for question_data in shuffled_data:
        # Recuperar la instancia de PreguntaTest
        pregunta_test = PreguntaTest.objects.get(
            pregunta_fk=question_data['pregunta_fk'],
            test_fk=question_data['test_fk']
        )

        # Las respuestas ya vienen en formato de tuplas
        respuestas_ordenadas = question_data['respuestas']

        questions_with_responses.append({
            'pregunta_test': pregunta_test,
            'respuestas': respuestas_ordenadas,
        })

    return questions_with_responses

########### REPORTS ############ 

def general_progress_report_individual(user):
    """
    Genera un reporte de progreso basado en intentos:
    - Días estudiados por mes.
    - Días y semanas consecutivas de estudio hasta la fecha.
    - Datos para el calendario interactivo.
    """
    # Rango de fechas: últimos 12 meses
    fecha_actual = timezone.now()
    fecha_inicio = fecha_actual - timedelta(days=360)
    
    # Query base para intentos
    intentos_query = UserAttemptsByDay.objects.filter(user_fk=user, date_attempted__gte=fecha_inicio)

    # Días estudiados por mes
    dias_por_mes = (
        intentos_query
        .annotate(month=TruncMonth('date_attempted'))
        .values('month')
        .annotate(total=Count('date_attempted'))
        .order_by('month')
    )

    # Formato de datos para gráfico de barras
    meses = []
    dias_mes = []
    for i in range(12):
        mes = (fecha_actual - timedelta(days=30 * i)).date().replace(day=1)
        meses.insert(0, mes.strftime('%B'))
        total_dias = next((item['total'] for item in dias_por_mes if item['month'].month == mes.month), 0)
        dias_mes.insert(0, total_dias)
    
    # Días y semanas consecutivas
    intentos_totales = UserAttemptsByDay.objects.filter(user_fk=user).order_by('date_attempted')
    dias = {attempt.date_attempted for attempt in intentos_totales}
    dias_consecutivos = 0
    semanas_consecutivas = 0

    # Calcular días consecutivos
    current_date = fecha_actual.date()
    while current_date in dias:
        dias_consecutivos += 1
        current_date -= timedelta(days=1)

    # Calcular semanas consecutivas
    current_week = fecha_actual.isocalendar()[1]
    semanas = {attempt.date_attempted.isocalendar()[1] for attempt in intentos_totales}
    while current_week in semanas:
        semanas_consecutivas += 1
        current_week -= 1

    # Datos para calendario interactivo (sin límite de fechas)
    calendario = {}
    for intento in intentos_totales:
        mes_key = intento.date_attempted.strftime('%Y-%m')
        if mes_key not in calendario:
            calendario[mes_key] = set()
        calendario[mes_key].add(intento.date_attempted.day)

    # Convertir conjuntos a listas para que sean JSON serializables
    for mes_key in calendario:
        calendario[mes_key] = list(calendario[mes_key])

    return {
        'dias_por_mes': dias_mes,
        'meses': meses,
        'dias_consecutivos': dias_consecutivos,
        'semanas_consecutivas': semanas_consecutivas,
        'calendario': calendario,
    }

def general_progress_report_global():
    """
    Genera un reporte de progreso basado en intentos:
    - Días estudiados por mes.
    - Días y semanas consecutivas de estudio hasta la fecha.
    - Datos para el calendario interactivo.
    """
    # Rango de fechas: últimos 12 meses
    fecha_actual = timezone.now()
    fecha_inicio = fecha_actual - timedelta(days=360)
    
    # Query base para intentos
    intentos_query = UserAttemptsByDay.objects.filter(date_attempted__gte=fecha_inicio)

    # Días estudiados por mes
    dias_por_mes = (
        intentos_query
        .annotate(month=TruncMonth('date_attempted'))
        .values('month')
        .annotate(total=Count('date_attempted'), usuarios=Count('user_fk', distinct=True))
        .order_by('month')
    )

    # Formato de datos para gráfico de barras
    meses = []
    media_dias_por_mes = []
    for i in range(12):
        mes = (fecha_actual - timedelta(days=30 * i)).date().replace(day=1)
        meses.insert(0, mes.strftime('%B'))
        # Total de días estudiados en el mes
        total_dias_mes = next((item['total'] for item in dias_por_mes if item['month'].month == mes.month), 0)
        # Total de usuarios únicos en el mes
        total_usuarios_mes = next((item['usuarios'] for item in dias_por_mes if item['month'].month == mes.month), 0)
        # Calcular la media para el mes actual
        media_mes = total_dias_mes / total_usuarios_mes if total_usuarios_mes > 0 else 0
        media_dias_por_mes.insert(0, media_mes)

    return {
        'media_dias_por_mes': media_dias_por_mes,
        'meses': meses,
    }

def attempts_report(user):
    """
    Calcula intentos agrupados por evento, bloque y sección, tanto individuales como globales.
    """
    # Base query global (todos los usuarios)
    global_query = Event.objects.filter(test_fk__aprobado=True)

    # Query individual para un usuario específico
    individual_query = global_query.filter(user_fk=user) if user else global_query

    # Intentos por evento
    intentos_por_evento = (
        individual_query
        .values('id', 'title')
        .annotate(
            intentos_individuales=Sum('test_fk__oportunidades'),
            intentos_globales=Subquery(
                global_query.filter(id=OuterRef('id')).values('id')
                .annotate(intentos=Sum('test_fk__oportunidades'))
                .values('intentos')[:1]
            )
        )
        .order_by('id')
    )

    # Intentos por bloque
    intentos_por_bloque = (
        individual_query
        .values('block_number__block_number', 'block_number__block_description')
        .annotate(
            intentos_individuales=Sum('test_fk__oportunidades'),
            intentos_globales=Subquery(
                global_query.filter(block_number=OuterRef('block_number'))
                .values('block_number')
                .annotate(intentos=Sum('test_fk__oportunidades'))
                .values('intentos')[:1]
            )
        )
        .order_by('block_number__block_number')
    )

    # Intentos por sección
    intentos_por_seccion = (
        individual_query
        .annotate(
            section_description=Subquery(
                StudyTopic.objects.filter(section_id=OuterRef('block_number__block_section_id'))
                .values('section_description')[:1]
            )
        )
        .values('block_number__block_section_id', 'section_description')
        .annotate(
            intentos_individuales=Sum('test_fk__oportunidades'),
            intentos_globales=Subquery(
                global_query.filter(block_number__block_section_id=OuterRef('block_number__block_section_id'))
                .values('block_number__block_section_id')
                .annotate(intentos=Sum('test_fk__oportunidades'))
                .values('intentos')[:1]
            )
        )
        .order_by('block_number__block_section_id')
    )

    return {
        'intentos_por_evento': list(intentos_por_evento),
        'intentos_por_bloque': list(intentos_por_bloque),
        'intentos_por_seccion': list(intentos_por_seccion),
    }

def generate_user_ranking():

    """
    Calcula el ranking de alumnos basado en intentos para completar un test.
    
    :param alumnos_queryset: Queryset de alumnos.
    :param minimo_tests: Número mínimo de tests completados para participar en el ranking.
    :return: Lista ordenada de alumnos con su promedio de intentos.
    """

    minimum_tests = 1
    ranking = (
            User.objects.annotate(
                # Contar solo los tests aprobados
                tests_completados=Count('test', filter=Q(test__aprobado=True)),
                # Sumar intentos de los tests aprobados, manejando valores NULL
                total_intentos=Coalesce(Sum('test__oportunidades', filter=Q(test__aprobado=True)), 0)
            )
            .filter(
                tests_completados__gte=minimum_tests,  # Mínimo requerido de tests completados
            )
            .annotate(
                # Calcular el score: tests_completados / total_intentos
                score=Coalesce(F('tests_completados') * 100 / F('total_intentos'), 0)
            )
            .order_by('-score')  # Orden descendente: mayor score primero
        )
            
    return ranking
