
from django.core.management.base import BaseCommand
from luapol_app.models import PreguntasPorTema, StudyTopic
import random

class Command(BaseCommand):
    help = 'Populate PreguntasPorTema with 20 questions per year, ensuring new topics are included.'

    def handle(self, *args, **kwargs):
        PreguntasPorTema.objects.all().delete()
        self.stdout.write(self.style.WARNING('Tabla PreguntasPorTema vaciada.'))

        temas = ['Geografía', 'Historia', 'Ciencia', 'Matemáticas', 'Literatura', 'Arte', 'Música', 'Tecnología', 'Filosofía', 'Economía', 'Psicología', 'Sociología']
        anos = [2020, 2021, 2022, 2023]

        for ano in anos:
            numero_total_preguntas = 100
            minimo_preguntas_por_tema = 5
            preguntas_restantes = numero_total_preguntas - (minimo_preguntas_por_tema * len(temas))
            distribucion_preguntas = self.generar_distribucion_aleatoria(preguntas_restantes, len(temas))

            for i, tema_nombre in enumerate(temas):
                tema, created = StudyTopic.objects.get_or_create(description=tema_nombre)
                numero_preguntas = minimo_preguntas_por_tema + distribucion_preguntas[i]
                PreguntasPorTema.objects.create(
                    tema_fk=tema,
                    anio=ano,
                    numero_preguntas=numero_preguntas
                )

                self.stdout.write(self.style.SUCCESS(f'{numero_preguntas} preguntas añadidas para {tema_nombre} en el año {ano}'))

        self.stdout.write(self.style.SUCCESS('Datos de preguntas por tema poblados correctamente.'))

    def generar_distribucion_aleatoria(self, total, partes):
        divisiones = sorted(random.sample(range(1, total), partes - 1))
        return [a - b for a, b in zip(divisiones + [total], [0] + divisiones)]
