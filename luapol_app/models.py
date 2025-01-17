from django.contrib.auth.models import User
from django.db import models
import secrets, string, uuid, datetime
from django.utils import timezone
from multiselectfield import MultiSelectField
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.core.exceptions import ValidationError

def generate_unique_key():
    # Generar una cadena aleatoria de 10 caracteres alfanuméricos
    return uuid.uuid4().hex[:20]

class StudyTopic(models.Model):
    id = models.CharField(primary_key=True, max_length=20, default=generate_unique_key, editable=False)
    title_number = models.IntegerField(unique=True)  # Cada tema tendrá un número de título único
    description = models.CharField(max_length=255)  # Descripción del tema principal
    page_count = models.IntegerField(default=0)  # Páginas totales del tema
    section_id = models.IntegerField()
    section_description = models.CharField(max_length=255)

    def __str__(self):
        return self.description  # Solo muestra la descripción del tema principal

class SubTopic(models.Model):
    study_topic_fk = models.ForeignKey(StudyTopic, on_delete=models.CASCADE, related_name='subtopics')
    subtopic_description = models.CharField(max_length=255)  # Descripción del subtema
    subtopic_id = models.IntegerField(primary_key=True)  # ID único para cada subtema
    page_count = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.study_topic_fk.description}: {self.subtopic_description}"

class EventSection(models.Model):
    id = models.CharField(primary_key=True, max_length=20, default=generate_unique_key, editable=False)
    block_section_id = models.IntegerField()
    block_number = models.IntegerField(unique=True)  # Sigue siendo único aquí para identificación
    block_description = models.CharField(max_length=255)

    def __str__(self):
        return f"Section {self.block_section_id}, Block {self.block_number}"

class Event(models.Model):
    id = models.CharField(primary_key=True, max_length=20, default=generate_unique_key, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField()
    creation_date = models.DateTimeField(auto_now_add=True)
    user_fk = models.ForeignKey(User, on_delete=models.CASCADE)
    test_fk = models.ForeignKey('Test', null=True, blank=True, on_delete=models.SET_NULL)
    completado = models.BooleanField(default=False)
    is_review = models.BooleanField(default=False)
    locked = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    
    # Relaciona block_number con block_number en EventSection
    block_number = models.ForeignKey(EventSection, to_field='block_number', on_delete=models.CASCADE)

    def __str__(self):
        return self.title

'''
class EventAnalytics(models.Model):
    id = models.CharField(primary_key=True, max_length=20, default=generate_unique_key, editable=False)
    event_fk = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="analytics")  # Relación con Event
    fecha_inicio = models.DateTimeField(null=True, blank=True)
    fecha_completado = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"TestAnalytics #{self.id}"
'''
        
class Test(models.Model):
    TEST_TYPE_CHOICES = [
        ('PARTIAL', 'Partial'),
        ('PRACTICE', 'Practice'),
        ('SIMULATION', 'Simulation'),
        ('DEFAULT', 'Default'),
    ]

    id = models.CharField(primary_key=True, max_length=20, default=generate_unique_key, editable=False)
    usuario_fk = models.ForeignKey(User, on_delete=models.CASCADE)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_submision = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=False) 
    aciertos = models.IntegerField(default=0)
    aciertos_1 = models.IntegerField(default=0)
    tipo = models.CharField(max_length=20, choices=TEST_TYPE_CHOICES, default='DEFAULT')
    oportunidades = models.IntegerField(default=0)
    aprobado = models.BooleanField(default=False)
    tiempo_medio = models.FloatField(default=0.0)   

    def __str__(self):
        return f"Test #{self.id}"

'''
class TestAnalytics(models.Model):
    id = models.CharField(primary_key=True, max_length=20, default=generate_unique_key, editable=False)
    fecha_inicio = models.DateTimeField(null=True, blank=True)
    fecha_inicio_1 = models.DateTimeField(null=True, blank=True)
    fecha_submision_1 = models.DateTimeField(null=True, blank=True)
    aciertos_1 = models.IntegerField(default=0)
    tiempo_medio_1 = models.FloatField(default=0.0)

    def __str__(self):
        return f"TestAnalytics #{self.id}"
'''
        
class StudyAvailability(models.Model):
    STUDY_MODES = [
        ('tests', 'Solo Tests'),
        ('study', 'Estudio Completo')
    ]

    id = models.CharField(primary_key=True, max_length=20, default=generate_unique_key, editable=False)
    user_oto = models.OneToOneField(User, on_delete=models.CASCADE)
    study_mode = models.CharField("Modo de estudio", choices=STUDY_MODES, max_length=20, default='study')

    def __str__(self):
        return f"{self.user_oto.username} - {self.get_study_mode_display()}"

class UserProfile(models.Model):
    user_oto = models.OneToOneField(User, on_delete=models.CASCADE)
    consent_given = models.BooleanField(default=False)
    activation_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)  # Cambiado a UUIDField

    def __str__(self):
        return self.user_oto.username

class Preguntas(models.Model):
    id = models.CharField(primary_key=True, max_length=20, default=generate_unique_key)
    id_pregunta = models.CharField(max_length=255)
    subtema_fk = models.ForeignKey(SubTopic, on_delete=models.CASCADE, to_field='subtopic_id')
    n_pregunta = models.CharField(max_length=255)
    pregunta = models.CharField(max_length=1000)

    def __str__(self):
        return self.pregunta

class TestSubtemaFallado(models.Model):
    id = models.CharField(primary_key=True, max_length=20, default=generate_unique_key, editable=False)
    test_fk = models.ForeignKey('Test', on_delete=models.CASCADE)  # Relación con el Test
    subtema_fk = models.ForeignKey(SubTopic, on_delete=models.CASCADE)  # Relación con StudyTopic
    fallos = models.IntegerField(default=0)  # Número de veces que se falló en este subtema

    def __str__(self):
        return f"Test {self.test_fk.id} - Subtema {self.subtema_fk.subtema} - Fallos: {self.fallos}"
    
    class Meta:
        ordering = ['-fallos']  # Ordenar por fallos de mayor a menor

class Respuestas(models.Model):
    id = models.CharField(primary_key=True, max_length=20, default=generate_unique_key)
    pregunta_fk = models.ForeignKey(Preguntas, related_name='respuestas', on_delete=models.CASCADE)
    n_respuesta = models.CharField(max_length=255)
    id_respuesta = models.CharField(max_length=255)
    es_correcta = models.BooleanField(default=False)
    descripcion = models.CharField(max_length=1000)
    comentarios = models.TextField(blank=True, null=True)

class PreguntaTest(models.Model):
    id = models.CharField(primary_key=True, max_length=20, default=generate_unique_key, editable=False)
    test_fk = models.ForeignKey(Test, related_name='preguntas_test', on_delete=models.CASCADE)
    pregunta_fk = models.ForeignKey(Preguntas, on_delete=models.CASCADE)
    respuesta_seleccionada_fk = models.ForeignKey(Respuestas, null=True, blank=True, on_delete=models.SET_NULL)
    es_correcta = models.BooleanField(default=False)
    es_favorita = models.BooleanField(default=False)

    def __str__(self):
        return f"Test {self.test_fk.id} - Pregunta {self.pregunta_fk.id_pregunta}"

class ResultadoTest(models.Model):
    id = models.CharField(primary_key=True, max_length=20, default=generate_unique_key, editable=False)
    fecha_hora = models.DateTimeField(default=timezone.now)
    # Relación con la pregunta y respuesta elegida
    pregunta_fk = models.ForeignKey(Preguntas, on_delete=models.CASCADE)
    respuesta_elegida_fk = models.ForeignKey(Respuestas, on_delete=models.CASCADE)
    es_correcta = models.BooleanField(default=False)

    def __str__(self):
        return f"Test realizado el {self.fecha_hora}"

class PreguntasPorTema(models.Model):
    id = models.CharField(primary_key=True, max_length=20, default=generate_unique_key, editable=False)
    tema_fk = models.ForeignKey(StudyTopic, on_delete=models.CASCADE)  # Relación con el tema principal
    anio = models.IntegerField()  # Año en el que se hicieron las preguntas
    numero_preguntas = models.IntegerField()  # Número de preguntas en ese año para el tema

    def __str__(self):
        return f"{self.tema_fk.description} - {self.anio}: {self.numero_preguntas} preguntas"

class ForoBase(models.Model):
    id = models.CharField(primary_key=True, max_length=20, default=generate_unique_key, editable=False)
    asunto = models.CharField(max_length=255)
    contenido = models.TextField()
    creado_por_fk = models.ForeignKey(User, on_delete=models.CASCADE)
    fecha_creacion = models.DateTimeField(default=timezone.now)
    likes = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.asunto

    class Meta:
        ordering = ['-likes', '-fecha_creacion']
        verbose_name = "Entrada de Foro"
        verbose_name_plural = "Entradas de Foro"


class ForoPregunta(models.Model):
    foro_base = models.OneToOneField(
        ForoBase, on_delete=models.CASCADE, related_name="foropregunta"
    )
    id_pregunta_fk = models.ForeignKey(
        Preguntas, null=False, blank=False, on_delete=models.CASCADE,
        related_name="entradas_pregunta", verbose_name="Pregunta Relacionada"
    )

    class Meta:
        verbose_name = "Entrada de Foro (Pregunta)"
        verbose_name_plural = "Entradas de Foro (Preguntas)"


class ForoGeneral(models.Model):
    foro_base = models.OneToOneField(
        ForoBase, on_delete=models.CASCADE, related_name="forogeneral"
    )
    id_tema_fk = models.ForeignKey(
        StudyTopic, null=True, blank=True, on_delete=models.CASCADE,
        related_name="entradas_general", verbose_name="Tema Relacionado"
    )

    class Meta:
        verbose_name = "Entrada de Foro (General)"
        verbose_name_plural = "Entradas de Foro (Generales)"

class ForoMensajes(models.Model):
    id = models.CharField(primary_key=True, max_length=20, default=generate_unique_key, editable=False)
    contenido = models.TextField(verbose_name="Contenido del Mensaje")
    autor_fk = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Autor del Mensaje")
    fecha_publicacion = models.DateTimeField(default=timezone.now)
    likes = models.PositiveIntegerField(default=0)

    # Relación con ForoBase
    foro_base_fk = models.ForeignKey(
        ForoBase, null=False, blank=False, on_delete=models.CASCADE, related_name="mensajes"
    )

    class Meta:
        verbose_name = "Mensaje de Foro"
        verbose_name_plural = "Mensajes de Foro"
        ordering = ['-likes', '-fecha_publicacion'] 

    def __str__(self):
        return f"Mensaje de {self.autor_fk} en '{self.foro_base_fk.asunto}'"

class ForoMeGusta(models.Model):
    id = models.CharField(primary_key=True, max_length=20, default=generate_unique_key, editable=False)
    usuario_fk = models.ForeignKey(User, on_delete=models.CASCADE)
    foro_base_fk = models.ForeignKey(
        ForoBase, null=True, blank=True, on_delete=models.CASCADE, related_name="me_gusta"
    )
    foro_mensaje_fk = models.ForeignKey(
        'ForoMensajes', null=True, blank=True, on_delete=models.CASCADE, related_name="me_gusta_mensajes"
    )  # Nuevo campo para relacionar con ForoMensajes

    class Meta:
        unique_together = ('usuario_fk', 'foro_base_fk', 'foro_mensaje_fk')  # Garantiza un único "me gusta" por combinación única

    def __str__(self):
        if self.foro_base_fk:
            return f"Me gusta de {self.usuario_fk} en '{self.foro_base_fk.asunto}'"
        elif self.foro_mensaje_fk:
            return f"Me gusta de {self.usuario_fk} en mensaje ID '{self.foro_mensaje_fk.id}'"

class Notifications(models.Model):
    id = models.CharField(primary_key=True, max_length=20, default=generate_unique_key, editable=False)
    user_fk = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")  # Relación con User
    subject = models.CharField(max_length=100)  # Título de la notificación
    message = models.TextField()  # Detalle de la notificación
    is_read = models.BooleanField(default=False)  # Estado de lectura
    created_at = models.DateTimeField(auto_now_add=True)  # Fecha de creación de la notificación

    def __str__(self):
        return f"Notification for {self.user_fk.username} - {self.message}"
    
class UserAttemptsByDay(models.Model):
    user_fk = models.ForeignKey(User, on_delete=models.CASCADE)
    date_attempted = models.DateField(default=timezone.now)  # Solo la fecha, sin horas ni minutos
    attempt_count = models.PositiveIntegerField(default=1)   # Número de intentos realizados en esa fecha

    class Meta:
        unique_together = ('user_fk', 'date_attempted')  # Evita duplicados por usuario y fecha

    def __str__(self):
        return f"{self.user_fk.username} - {self.date_attempted}: {self.attempt_count} intentos"

