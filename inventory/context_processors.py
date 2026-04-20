from .models import ProductionArea, JobOrderProduct

def production_context(request):
    if not request.user.is_authenticated:
        return {}
        
    production_areas = ProductionArea.objects.all()
    area_stats = {}
    for area in production_areas:
        area_stats[area.id] = JobOrderProduct.objects.filter(current_area=area).count()
        
    return {
        'production_areas': production_areas,
        'area_stats': area_stats,
    }
