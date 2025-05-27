from django.urls import path
from . import views

urlpatterns = [
    path('', views.pokemon_list, name='pokemon_list'),
    path('<str:pokemon_name>/', views.pokemon_detail, name='pokemon_detail'),
] 