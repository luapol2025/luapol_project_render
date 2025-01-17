
import os
import csv
from django.core.management.base import BaseCommand
from luapol_app.models import StudyTopic, SubTopic 

class Command(BaseCommand):
    help = 'Importar datos desde final_syllabus_with_sections.csv a las tablas StudyTopic y SubTopic'

    def handle(self, *args, **kwargs):
        directorio_actual = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(directorio_actual, '../files/final_syllabus_with_sections.csv')

        # Abrimos el archivo CSV y procesamos cada fila
        with open(file_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                # Asignar las columnas del CSV a las variables correspondientes
                section_id = int(row['section_id'])
                section_description = row['section_description']
                title_number = int(row['title_number'])
                description = row['description']
                page_count = int(row['page_count'])

                # Crear o actualizar el registro en StudyTopic con la información de la sección
                topic, topic_created = StudyTopic.objects.update_or_create(
                    title_number=title_number,
                    defaults={
                        'description': description,
                        'page_count': page_count,
                        'section_id': section_id,  # Almacenar directamente en StudyTopic
                        'section_description': section_description  # Almacenar directamente en StudyTopic
                    }
                )

                # Procesar los subtemas
                subtema_id = int(row['subtema_id'])
                subtema_description = row['subtema']
                subtema_page_count = int(row['page_count'])

                # Crear o actualizar el registro en SubTopic
                subtopic, sub_created = SubTopic.objects.update_or_create(
                    subtopic_id=subtema_id,
                    study_topic_fk=topic,
                    defaults={
                        'subtopic_description': subtema_description,
                        'page_count': subtema_page_count
                    }
                )

                if topic_created:
                    self.stdout.write(self.style.SUCCESS(f'Tema "{description}" con sección "{section_description}" creado con éxito.'))
                if sub_created:
                    self.stdout.write(self.style.SUCCESS(f'Subtema "{subtema_description}" creado con éxito.'))
                else:
                    self.stdout.write(self.style.SUCCESS(f'Subtema "{subtema_description}" actualizado con éxito.'))
