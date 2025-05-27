from django.test import TestCase, Client
from django.urls import reverse, resolve
from unittest.mock import patch, MagicMock # For mocking API calls

from .models import Pokemon, Type, Ability
from .views import get_or_fetch_pokemon_details, index, pokemon_list, pokemon_detail, pokemon_compare # Import views for URL tests

# Sample API response data for mocking
SAMPLE_POKEMON_API_DATA = {
    'id': 1,
    'name': 'bulbasaur',
    'height': 7,
    'weight': 69,
    'sprites': {'front_default': 'https://example.com/bulbasaur.png'},
    'types': [
        {'type': {'name': 'grass'}},
        {'type': {'name': 'poison'}}
    ],
    'abilities': [
        {'ability': {'name': 'overgrow'}},
        {'ability': {'name': 'chlorophyll'}}
    ],
    'stats': [
        {'stat': {'name': 'hp'}, 'base_stat': 45},
        {'stat': {'name': 'attack'}, 'base_stat': 49}
    ]
}

SAMPLE_TYPE_API_DATA = {
    'name': 'grass',
    'pokemon': [
        {'pokemon': {'name': 'bulbasaur', 'url': 'https://pokeapi.co/api/v2/pokemon/1/'}},
        {'pokemon': {'name': 'ivysaur', 'url': 'https://pokeapi.co/api/v2/pokemon/2/'}}
    ]
}

class ModelTests(TestCase):
    def test_type_str(self):
        type_obj = Type.objects.create(name='grass')
        self.assertEqual(str(type_obj), 'Grass')

    def test_ability_str(self):
        ability_obj = Ability.objects.create(name='overgrow')
        self.assertEqual(str(ability_obj), 'Overgrow')

    def test_pokemon_str(self):
        pokemon_obj = Pokemon.objects.create(pokeapi_id=1, name='bulbasaur')
        self.assertEqual(str(pokemon_obj), 'Bulbasaur')

class ViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        # Create some initial data that views might rely on
        self.type_grass = Type.objects.create(name='grass')
        self.type_poison = Type.objects.create(name='poison')
        self.ability_overgrow = Ability.objects.create(name='overgrow')
        self.pokemon1 = Pokemon.objects.create(
            pokeapi_id=1, name='bulbasaur', height=7, weight=69, 
            sprite_url='https://example.com/bulbasaur.png',
            stats={"hp": 45, "attack": 49}
        )
        self.pokemon1.types.add(self.type_grass, self.type_poison)
        self.pokemon1.abilities.add(self.ability_overgrow)

        self.pokemon2 = Pokemon.objects.create(
            pokeapi_id=25, name='pikachu', height=4, weight=60,
            sprite_url='https://example.com/pikachu.png',
            stats={"hp": 35, "attack": 55}
        )

    def test_index_view(self):
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pokedex_app/index.html')

    def test_pokemon_list_view(self):
        response = self.client.get(reverse('pokemon_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pokedex_app/pokemon_list.html')
        self.assertTrue('pokemon_list_from_db' in response.context)

    def test_pokemon_detail_view_existing(self):
        response = self.client.get(reverse('pokemon_detail', args=['bulbasaur']))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pokedex_app/pokemon_detail.html')
        self.assertContains(response, 'Bulbasaur')

    def test_pokemon_detail_view_not_existing_api_fail(self):
        # Mock API to simulate Pokemon not found
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_get.return_value = mock_response
            
            response = self.client.get(reverse('pokemon_detail', args=['nonexistentpokemon']))
            self.assertEqual(response.status_code, 200) # View itself returns 200
            self.assertTemplateUsed(response, 'pokedex_app/pokemon_detail.html')
            self.assertTrue(response.context['error']) # Error message should be in context
            self.assertIsNone(response.context['pokemon_data'])

    def test_pokemon_compare_view_get(self):
        response = self.client.get(reverse('pokemon_compare'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pokedex_app/pokemon_compare.html')

    def test_pokemon_compare_view_with_pokemon(self):
        response = self.client.get(reverse('pokemon_compare'), {'pokemon1': 'bulbasaur', 'pokemon2': 'pikachu'})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pokedex_app/pokemon_compare.html')
        self.assertTrue('comparison_results' in response.context)
        self.assertIsNotNone(response.context['pokemon1_data'])
        self.assertIsNotNone(response.context['pokemon2_data'])
        self.assertContains(response, "Bulbasaur")
        self.assertContains(response, "Pikachu")

    def test_pokemon_compare_view_same_pokemon(self):
        response = self.client.get(reverse('pokemon_compare'), {'pokemon1': 'bulbasaur', 'pokemon2': 'bulbasaur'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['error_message'])
        self.assertIn("Please select two different Pokémon", response.context['error_message'])

class HelperFunctionTests(TestCase):
    @patch('requests.get')
    def test_get_or_fetch_pokemon_details_new_pokemon(self, mock_get):
        # Configure the mock to return a successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_POKEMON_API_DATA
        mock_get.return_value = mock_response

        pokemon = get_or_fetch_pokemon_details('bulbasaur')

        mock_get.assert_called_once_with('https://pokeapi.co/api/v2/pokemon/bulbasaur/')
        self.assertIsNotNone(pokemon)
        self.assertEqual(pokemon.name, 'bulbasaur')
        self.assertEqual(pokemon.pokeapi_id, 1)
        self.assertTrue(Pokemon.objects.filter(name='bulbasaur').exists())
        self.assertTrue(Type.objects.filter(name='grass').exists())
        self.assertTrue(Ability.objects.filter(name='overgrow').exists())
        self.assertIsNotNone(pokemon.stats.get('hp'))

    def test_get_or_fetch_pokemon_details_existing_pokemon(self):
        # Create a Pokemon in the DB first
        Type.objects.create(name='fire')
        Pokemon.objects.create(
            pokeapi_id=4, name='charmander', 
            stats={"hp": 39}, 
            sprite_url='https://example.com/charmander.png'
        )
        
        with patch('requests.get') as mock_get: # Ensure API is NOT called
            pokemon = get_or_fetch_pokemon_details('charmander')
            mock_get.assert_not_called()
            self.assertIsNotNone(pokemon)
            self.assertEqual(pokemon.name, 'charmander')

    @patch('requests.get')
    def test_get_or_fetch_pokemon_details_existing_needs_stats_update(self, mock_get):
        # Create Pokemon without stats
        Pokemon.objects.create(pokeapi_id=1, name='bulbasaur', sprite_url='url')
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_POKEMON_API_DATA # API will return full data with stats
        mock_get.return_value = mock_response

        pokemon = get_or_fetch_pokemon_details('bulbasaur')

        mock_get.assert_called_once_with('https://pokeapi.co/api/v2/pokemon/bulbasaur/')
        self.assertIsNotNone(pokemon)
        self.assertIsNotNone(pokemon.stats) 
        self.assertEqual(pokemon.stats.get('hp'), 45)

    @patch('requests.get')
    def test_get_or_fetch_pokemon_details_api_failure(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        pokemon = get_or_fetch_pokemon_details('nonexistent')
        self.assertIsNone(pokemon)

class UrlTests(TestCase):
    def test_index_url_resolves(self):
        url = reverse('index')
        self.assertEqual(resolve(url).func, index)

    def test_pokemon_list_url_resolves(self):
        url = reverse('pokemon_list')
        self.assertEqual(resolve(url).func, pokemon_list)

    def test_pokemon_detail_url_resolves(self):
        url = reverse('pokemon_detail', args=['some-pokemon'])
        self.assertEqual(resolve(url).func, pokemon_detail)
    
    def test_pokemon_compare_url_resolves(self):
        url = reverse('pokemon_compare')
        self.assertEqual(resolve(url).func, pokemon_compare)
