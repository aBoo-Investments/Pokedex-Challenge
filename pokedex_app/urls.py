from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('pokemon/', views.pokemon_list, name='pokemon_list'),
    path('pokemon/<str:pokemon_name>/', views.pokemon_detail, name='pokemon_detail'),
    path('compare/', views.pokemon_compare, name='pokemon_compare'),
] 