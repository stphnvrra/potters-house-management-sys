from django.core.management.base import BaseCommand
from inventory.models import ProductionArea

class Command(BaseCommand):
    help = 'Seeds the initial production areas'

    def handle(self, *args, **options):
        areas = [
            'Production Head',
            'Layout Artist A',
            'Layout Artist B',
            'Job Out Printing',
            'Assembly',
            'Customization',
            'Invitation',
            'Marketing',
            'Packaging',
            'Photobooth',
        ]
        
        for i, area_name in enumerate(areas):
            area, created = ProductionArea.objects.get_or_create(
                name=area_name,
                defaults={'display_order': i}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created area: {area_name}'))
            else:
                self.stdout.write(self.style.WARNING(f'Area already exists: {area_name}'))
