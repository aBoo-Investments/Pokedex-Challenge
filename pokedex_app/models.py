from django.db import models

# Create your models here.

class Type(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name.capitalize()

class Ability(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name.capitalize()

class Pokemon(models.Model):
    pokeapi_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=100, unique=True)
    height = models.IntegerField(null=True, blank=True)  # In decimetres
    weight = models.IntegerField(null=True, blank=True)  # In hectograms
    sprite_url = models.URLField(max_length=255, null=True, blank=True)
    types = models.ManyToManyField(Type, related_name='pokemons')
    abilities = models.ManyToManyField(Ability, related_name='pokemons')
    stats = models.JSONField(null=True, blank=True)

    def __str__(self):
        return self.name.capitalize()
