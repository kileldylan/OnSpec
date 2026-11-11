from django.http import HttpResponse
from django.views.decorators.http import require_safe

@require_safe
def health_check(request):
    return HttpResponse(status=204)