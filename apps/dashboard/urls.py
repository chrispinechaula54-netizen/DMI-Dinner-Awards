from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='final_voting:manage', permanent=False), name='overview'),
    path('toggle-period/', views.toggle_period_view, name='toggle_period'),
    path('categories/', views.categories_view, name='categories'),
    path('nominations/', views.nominations_view, name='nominations'),
    path('statistics/', views.statistics_view, name='statistics'),
    path('name-review/', views.name_review_view, name='name_review'),
]

