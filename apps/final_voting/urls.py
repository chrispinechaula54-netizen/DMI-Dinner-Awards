from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = 'final_voting'
urlpatterns = [
    path('', views.ballot_view, name='ballot'),
    path('submit/', views.submit_ballot, name='submit'),
    path('manage/', views.manage_view, name='manage'),
    path('dashboard/', RedirectView.as_view(pattern_name='final_voting:manage', permanent=False), name='dashboard'),
    path('manage/action/', views.manage_action, name='manage_action'),
    path('preview/', views.preview_view, name='preview'),
    path('results/', views.results_view, name='results'),
    path('results/dinner/', views.dinner_result, name='dinner_result'),
    path('results/winner/', views.confirm_winner, name='confirm_winner'),
]
