from django.shortcuts import render
from apps.final_voting.models import BallotCategory, Election

def landing_view(request):
    categories = BallotCategory.objects.order_by('display_order')
    context = {
        'election': Election.current(),
        'categories': categories,
        'categories_count': categories.count(),
    }
    return render(request, 'pages/landing.html', context)

