from django.http import JsonResponse
from django.views.decorators.http import require_safe


@require_safe
def health_check(request):
    return JsonResponse({"status": "ok"})
