from django.db.models import Count
from .models import BallotCategory


def category_ready(category):
    return category.method == 'online' and category.approved and category_complete(category)


def category_complete(category):
    if category.method != 'online':
        return False
    divisions = list(category.divisions.prefetch_related('candidates'))
    return bool(divisions) and all(
        d.candidates.count() == d.required_candidates
        and d.candidates.filter(confirmed=True).count() == d.required_candidates
        and not d.candidates.filter(name__iexact='TO BE CONFIRMED').exists()
        for d in divisions
    )


def published_categories():
    return [c for c in BallotCategory.objects.filter(method='online', approved=True).prefetch_related('divisions__candidates').order_by('display_order') if category_ready(c)]


def category_results(category):
    return category.divisions.prefetch_related('candidates').all().annotate(
        ballot_count=Count('selections')
    )
