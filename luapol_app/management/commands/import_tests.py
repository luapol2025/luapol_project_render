
import csv
import os
from django.core.management.base import BaseCommand
from luapol_app.models import Preguntas, Respuestas, SubTopic

class Command(BaseCommand):
    help = 'Importa datos desde el archivo CSV generated_questions_answers.csv'

    def handle(self, *args, **kwargs):
        directorio_actual = os.path.dirname(os.path.abspath(__file__))
        archivo_csv = os.path.join(directorio_actual, '../files/completed_questions_answers.csv')

        with open(archivo_csv, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                try:
                    pregunta_id = row['ID Pregunta']
                    subtema_id = row['ID SubTema']

                    # Buscar el subtema correspondiente en la tabla SubTopic
                    subtema_instance = SubTopic.objects.get(subtopic_id=subtema_id)

                    # Crear o actualizar la pregunta
                    pregunta_instance, created = Preguntas.objects.update_or_create(
                        id_pregunta=pregunta_id,
                        subtema_fk=subtema_instance,
                        defaults={
                            'n_pregunta': row['n Pregunta'],
                            'pregunta': row['Pregunta']
                        }
                    )

                    # Crear la respuesta relacionada con la pregunta
                    Respuestas.objects.update_or_create(
                        id_respuesta=row['ID Respuesta'],
                        defaults={
                            'n_respuesta': row['n Respuesta'],
                            'pregunta_fk': pregunta_instance,
                            'es_correcta': row['Es Correcta'].strip().lower() == 'sí',
                            'descripcion': row['Descripcio'],
                            'comentarios': row['Comentaris']
                        }
                    )

                except SubTopic.DoesNotExist:
                    print(f"Error: Subtema con ID {subtema_id} no encontrado para la pregunta {pregunta_id}")
                except KeyError as e:
                    print(f"KeyError: {e} in row: {row}")
                except Exception as ex:
                    print(f"Exception: {ex} in row: {row}")

        self.stdout.write(self.style.SUCCESS('Datos cargados exitosamente'))
