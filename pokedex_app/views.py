from django.shortcuts import render, redirect
from django.urls import reverse
import requests

# Create your views here.

def pokemon_list(request):
    query = request.GET.get('q')
    selected_type_url = request.GET.get('type_filter') # URL of the selected type
    search_error = None
    pokemon_entries = []
    next_url = None
    previous_url = None
    all_types = []

    # Fetch all available Pokemon types for the filter dropdown
    try:
        types_response = requests.get('https://pokeapi.co/api/v2/type?limit=100') # Assuming less than 100 types
        if types_response.status_code == 200:
            all_types = types_response.json().get('results', [])
        else:
            search_error = "Could not fetch Pokemon types for filtering."
    except requests.RequestException:
        search_error = "Error connecting to API to fetch types."

    if query and not selected_type_url: # Search by name only if no type filter is active
        api_url = f'https://pokeapi.co/api/v2/pokemon/{query.lower()}/'
        response = requests.get(api_url)
        if response.status_code == 200:
            return redirect(reverse('pokemon_detail', kwargs={'pokemon_name': query.lower()}))
        else:
            search_error = f"Pokemon '{query}' not found. Displaying the general list (or filtered list if type is selected)."
    
    if selected_type_url:
        # Fetch Pokemon by selected type
        try:
            type_response = requests.get(selected_type_url)
            if type_response.status_code == 200:
                type_data = type_response.json()
                pokemon_results_from_type = [p['pokemon'] for p in type_data.get('pokemon', [])]
                # We get name and URL, need to fetch details like sprite and all types (for consistency)
                for pokemon in pokemon_results_from_type:
                    detail_url = pokemon.get('url')
                    if detail_url:
                        detail_response = requests.get(detail_url)
                        if detail_response.status_code == 200:
                            detail_data = detail_response.json()
                            pokemon['types'] = [t['type']['name'] for t in detail_data.get('types', [])]
                            pokemon['abilities'] = [a['ability']['name'] for a in detail_data.get('abilities', [])]
                            pokemon['sprite'] = detail_data.get('sprites', {}).get('front_default')
                        else:
                            pokemon['types'] = []
                            pokemon['abilities'] = []
                            pokemon['sprite'] = None
                    else:
                        pokemon['types'] = []
                        pokemon['abilities'] = []
                        pokemon['sprite'] = None
                pokemon_entries = pokemon_results_from_type
                # Pagination is disabled when filtering by type for simplicity for now
                next_url = None
                previous_url = None
            else:
                search_error = f"Could not fetch Pokemon for the selected type. Status: {type_response.status_code}"
        except requests.RequestException:
            search_error = "Error connecting to API to fetch Pokemon by type."

    elif not query: # If not searching by name and not filtering by type, show paginated list
        page_url = request.GET.get('page_url', 'https://pokeapi.co/api/v2/pokemon?limit=20')
        list_response = requests.get(page_url)
        if list_response.status_code == 200:
            data = list_response.json()
            pokemon_results = data.get('results', [])
            next_url = data.get('next')
            previous_url = data.get('previous')
            for pokemon in pokemon_results: # Fetch details for paginated list
                detail_url = pokemon.get('url')
                if detail_url:
                    detail_response = requests.get(detail_url)
                    if detail_response.status_code == 200:
                        detail_data = detail_response.json()
                        pokemon['types'] = [t['type']['name'] for t in detail_data.get('types', [])]
                        pokemon['abilities'] = [a['ability']['name'] for a in detail_data.get('abilities', [])]
                        pokemon['sprite'] = detail_data.get('sprites', {}).get('front_default')
                    else: # Handle error for individual Pokemon detail fetch
                        pokemon['types'] = []
                        pokemon['abilities'] = []
                        pokemon['sprite'] = None 
                else:
                    pokemon['types'] = []
                    pokemon['abilities'] = []
                    pokemon['sprite'] = None 
            pokemon_entries = pokemon_results
        else:
            search_error = search_error or "Could not fetch Pokemon list from API."

    context = {
        'pokemon_list': pokemon_entries,
        'next_url': next_url,
        'previous_url': previous_url,
        'search_error': search_error,
        'query': query,
        'all_types': all_types,
        'selected_type_url': selected_type_url
    }
    return render(request, 'pokedex_app/pokemon_list.html', context)

def index(request):
    return render(request, 'pokedex_app/index.html')

def pokemon_detail(request, pokemon_name):
    api_url = f'https://pokeapi.co/api/v2/pokemon/{pokemon_name.lower()}/'
    response = requests.get(api_url)
    context = {
        'pokemon_name': pokemon_name.capitalize(),
        'pokemon_data': None,
        'error': None
    }

    if response.status_code == 200:
        data = response.json()
        # Extract relevant details
        # This is a basic extraction, can be expanded significantly
        context['pokemon_data'] = {
            'id': data.get('id'),
            'name': data.get('name').capitalize(),
            'height': data.get('height'), # In decimetres
            'weight': data.get('weight'), # In hectograms
            'abilities': [ability['ability']['name'] for ability in data.get('abilities', [])],
            'types': [type_info['type']['name'] for type_info in data.get('types', [])],
            'stats': {stat['stat']['name']: stat['base_stat'] for stat in data.get('stats', [])},
            'sprite_front': data.get('sprites', {}).get('front_default')
        }
        # Potentially save/update this Pokemon in our local DB
        # from .models import Pokemon
        # Pokemon.objects.update_or_create(
        #     pokeapi_id=data.get('id'),
        #     defaults={
        #         'name': data.get('name'),
        #         'height': data.get('height'),
        #         'weight': data.get('weight'),
        #         # Add other fields as necessary, handle types/abilities relationally
        #     }
        # )

    else:
        context['error'] = f"Could not fetch data for {pokemon_name.capitalize()}. Status: {response.status_code}"

    return render(request, 'pokedex_app/pokemon_detail.html', context)
