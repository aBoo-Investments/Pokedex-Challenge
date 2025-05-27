from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
import requests
from .models import Pokemon, Type, Ability # Import new models
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger # For DB pagination
from django.db.models import Q # For complex lookups
# from django.db import models # This was an erroneously added import by the model

# Create your views here.

def get_or_fetch_pokemon_details(pokemon_name_or_id):
    """Helper: Gets Pokemon from DB. If stats are missing or Pokemon not found, fetches/updates from API."""
    identifier_kwargs = {}
    if isinstance(pokemon_name_or_id, int):
        identifier_kwargs['pokeapi_id'] = pokemon_name_or_id
        fetch_name_or_id_for_api = str(pokemon_name_or_id) # API needs string for ID too
    else:
        name_lower = str(pokemon_name_or_id).lower()
        identifier_kwargs['name'] = name_lower
        fetch_name_or_id_for_api = name_lower

    try:
        pokemon_obj = Pokemon.objects.get(**identifier_kwargs)
        if not pokemon_obj.stats: # If stats are missing, force API re-fetch and update
            print(f"[DB STATS MISSING] Stats missing for {pokemon_obj.name}. Will re-sync from API.")
            raise Pokemon.DoesNotExist # Treat as if not found to trigger API path
        print(f"[DB CACHE HIT] Fetched {pokemon_obj.name} from DB (with stats).")
        return pokemon_obj
    except Pokemon.DoesNotExist:
        print(f"[API SYNC] {fetch_name_or_id_for_api} not in DB or needs stats update. Syncing from API.")
        api_url = f'https://pokeapi.co/api/v2/pokemon/{fetch_name_or_id_for_api}/' # No trailing comma
        response = requests.get(api_url)

        if response.status_code == 200:
            data = response.json()
            api_stats = {stat['stat']['name']: stat['base_stat'] for stat in data.get('stats', [])}
            
            defaults = {
                'name': data.get('name').lower(),
                'pokeapi_id': data.get('id'),
                'height': data.get('height'),
                'weight': data.get('weight'),
                'sprite_url': data.get('sprites', {}).get('front_default'),
                'stats': api_stats
            }
            
            # Use the original identifier_kwargs for lookup in update_or_create
            # This ensures we find by name if name was passed, or by ID if ID was passed.
            # The defaults will then update all fields, including potentially name (if API differs) or ID.
            pokemon_obj, created = Pokemon.objects.update_or_create(
                **identifier_kwargs, 
                defaults=defaults
            )

            # Update types
            db_types = []
            for type_info in data.get('types', []):
                type_obj, _ = Type.objects.get_or_create(name=type_info['type']['name'])
                db_types.append(type_obj)
            pokemon_obj.types.set(db_types)

            # Update abilities
            db_abilities = []
            for ability_info in data.get('abilities', []):
                ability_obj, _ = Ability.objects.get_or_create(name=ability_info['ability']['name'])
                db_abilities.append(ability_obj)
            pokemon_obj.abilities.set(db_abilities) # Save abilities after setting them
            
            action = "CREATED" if created else "UPDATED"
            print(f"[API SYNC] Pokemon {pokemon_obj.name} {action} in DB.")
            return pokemon_obj
        else:
            print(f"[API SYNC ERROR] Failed to fetch {fetch_name_or_id_for_api} from API. Status: {response.status_code}")
            return None

def pokemon_list(request):
    query = request.GET.get('q')
    selected_type_name = request.GET.get('type_filter_name')
    selected_ability_name = request.GET.get('ability_filter_name')
    search_error = None
    all_types_for_filter = []
    all_abilities_for_filter = []

    # Fetch all available Pokemon types for the filter dropdown (same as before)
    all_types_from_db = Type.objects.all().order_by('name')
    if not all_types_from_db:
        try:
            types_response = requests.get('https://pokeapi.co/api/v2/type?limit=100') 
            if types_response.status_code == 200:
                api_types_results = types_response.json().get('results', [])
                for api_type in api_types_results:
                    type_obj, _ = Type.objects.get_or_create(name=api_type['name'])
                    all_types_for_filter.append(type_obj)
            else:
                search_error = "Could not fetch Pokemon types for filtering."
        except requests.RequestException:
            search_error = "Error connecting to API to fetch types."
    else:
        all_types_for_filter = list(all_types_from_db)

    # Fetch all available Pokemon abilities for the filter dropdown
    all_abilities_from_db = Ability.objects.all().order_by('name')
    if not all_abilities_from_db:
        print("[ABILITY SEED] No abilities in DB, fetching from API.")
        try:
            # PokeAPI ability endpoint might be paginated, but let's try a high limit
            # There are around 300-400 abilities
            abilities_response = requests.get('https://pokeapi.co/api/v2/ability?limit=400') 
            if abilities_response.status_code == 200:
                api_abilities_results = abilities_response.json().get('results', [])
                for api_ability in api_abilities_results:
                    ability_obj, _ = Ability.objects.get_or_create(name=api_ability['name'])
                    all_abilities_for_filter.append(ability_obj)
                print(f"[ABILITY SEED] Fetched and saved {len(all_abilities_for_filter)} abilities.")
            else:
                search_error = (search_error or "") + " Could not fetch Pokemon abilities for filtering."
        except requests.RequestException:
            search_error = (search_error or "") + " Error connecting to API to fetch abilities."
    else:
        all_abilities_for_filter = list(all_abilities_from_db)

    pokemon_queryset = Pokemon.objects.all().order_by('pokeapi_id')

    if query and not selected_type_name and not selected_ability_name:
        pokemon_obj = get_or_fetch_pokemon_details(query)
        if pokemon_obj:
            return redirect(reverse('pokemon_detail', kwargs={'pokemon_name': pokemon_obj.name}))
        else:
            search_error = f"Pokemon '{query}' not found."
    
    elif selected_type_name and not query and not selected_ability_name:
        # Filter by type
        # First, check if we have any Pokemon of this type in DB
        current_db_pokemon_of_type_count = Pokemon.objects.filter(types__name=selected_type_name).count()
        
        # Fetch all Pokemon of this type from API to ensure DB is complete for this type
        # This can be slow for types with many Pokemon if they are not already in DB.
        # Consider adding a flag or a more sophisticated check if this is too slow.
        print(f"[TYPE FILTER] Filtering by type: {selected_type_name}.")
        try:
            type_api_url = f'https://pokeapi.co/api/v2/type/{selected_type_name.lower()}/'
            type_response = requests.get(type_api_url)
            if type_response.status_code == 200:
                type_data = type_response.json()
                pokemon_from_type_api = type_data.get('pokemon', [])
                print(f"[TYPE FILTER] API returned {len(pokemon_from_type_api)} Pokemon for type {selected_type_name}.")
                for p_entry in pokemon_from_type_api:
                    pokemon_name_to_fetch = p_entry['pokemon']['name']
                    # This helper will fetch from API and save to DB if not already present
                    get_or_fetch_pokemon_details(pokemon_name_to_fetch) 
                # After ensuring all Pokemon of this type are in DB, filter the queryset
                pokemon_queryset = pokemon_queryset.filter(types__name=selected_type_name)
                if not pokemon_queryset.exists() and not search_error:
                    search_error = f"No Pokémon of type '{selected_type_name.capitalize()}' found even after API check (this shouldn't happen if API call was successful)."
            else:
                search_error = f"Could not fetch full list for type '{selected_type_name.capitalize()}' from API. Status: {type_response.status_code}"
                # Fallback to filtering only what's in DB for this type
                pokemon_queryset = pokemon_queryset.filter(types__name=selected_type_name)
                if not pokemon_queryset.exists() and not search_error:
                     search_error = search_error or f"No Pokémon of type '{selected_type_name.capitalize()}' found in local DB and API fetch failed."
        except requests.RequestException as e:
            search_error = f"API error when fetching type details for {selected_type_name}: {e}"
            pokemon_queryset = pokemon_queryset.filter(types__name=selected_type_name) # Fallback

    elif selected_ability_name and not query and not selected_type_name:
        # Filter by ability
        print(f"[ABILITY FILTER] Filtering by ability: {selected_ability_name}.")
        # Similar to type: fetch all Pokemon with this ability from API to ensure DB is complete.
        # This is a simplified version for now, filtering on existing DB data.
        # A full implementation would hit the ability endpoint and use get_or_fetch_pokemon_details.
        pokemon_queryset = pokemon_queryset.filter(abilities__name=selected_ability_name)
        if not pokemon_queryset.exists() and not search_error:
             search_error = f"No Pokémon with ability '{selected_ability_name.capitalize()}' found in the local database. Full fetch for abilities not yet implemented for list view."

    # Initial DB seeding (if no filters/query and DB is sparse)
    # Check total Pokemon in DB, not just current queryset, to decide on seeding.
    if Pokemon.objects.count() < 20 and not query and not selected_type_name and not selected_ability_name:
        print("[DB SEED] DB has less than 20 Pokemon, attempting to seed first 20 from API.")
        try:
            initial_response = requests.get('https://pokeapi.co/api/v2/pokemon?limit=20')
            if initial_response.status_code == 200:
                for p_info in initial_response.json().get('results', []):
                    get_or_fetch_pokemon_details(p_info['name'])
                pokemon_queryset = Pokemon.objects.all().order_by('pokeapi_id') # Re-query after seeding
            else:
                 search_error = search_error or "Failed to seed initial Pokemon data from API."
        except requests.RequestException:
            search_error = search_error or "API error during initial Pokemon data seed."

    paginator = Paginator(pokemon_queryset, 20)
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        'pokemon_list_from_db': page_obj,
        'search_error': search_error,
        'query': query,
        'all_types_for_filter': all_types_for_filter,
        'selected_type_name': selected_type_name,
        'all_abilities_for_filter': all_abilities_for_filter,
        'selected_ability_name': selected_ability_name
    }
    return render(request, 'pokedex_app/pokemon_list.html', context)

def index(request):
    return render(request, 'pokedex_app/index.html')

# Helper function to recursively parse evolution stages
def _parse_evolution_stage(stage_data):
    species_name = stage_data['species']['name']
    # Ensure Pokemon is in our DB and we have its details (sprite, etc.)
    pokemon_obj = get_or_fetch_pokemon_details(species_name) 

    if not pokemon_obj:
        print(f"Warning: Could not get/fetch Pokemon details for {species_name} in evolution chain.")
        return None 

    current_evolution_node = {
        'pokemon': pokemon_obj, 
        'name': pokemon_obj.name.capitalize(),
        'sprite_url': pokemon_obj.sprite_url,
        'detail_url': reverse('pokemon_detail', kwargs={'pokemon_name': pokemon_obj.name}),
        'evolves_to': []
    }
    
    for next_stage_data in stage_data.get('evolves_to', []):
        next_node = _parse_evolution_stage(next_stage_data) 
        if next_node: 
            current_evolution_node['evolves_to'].append(next_node)
    
    return current_evolution_node

# Main function to fetch and process evolution chain
def get_pokemon_evolution_chain(pokemon_name_or_id):
    """
    Fetches and processes the evolution chain for a given Pokemon.
    Returns a structured dictionary representing the evolution tree.
    """
    # Step 1: Get the initial Pokemon's data to find its species URL
    # We use its name for consistency in API calls, fetched via our helper
    # to ensure it's a valid/known Pokemon name.
    initial_pokemon_for_name = get_or_fetch_pokemon_details(pokemon_name_or_id)
    if not initial_pokemon_for_name:
        print(f"EvolutionChain: Initial Pokemon {pokemon_name_or_id} not found by helper.")
        return None
    
    pokemon_api_url = f'https://pokeapi.co/api/v2/pokemon/{initial_pokemon_for_name.name.lower()}/'
    try:
        pokemon_response = requests.get(pokemon_api_url)
        pokemon_response.raise_for_status()
        pokemon_api_data = pokemon_response.json()
    except requests.RequestException as e:
        print(f"EvolutionChain: Error fetching Pokemon data from {pokemon_api_url}: {e}")
        return None

    species_url = pokemon_api_data.get('species', {}).get('url')
    if not species_url:
        print(f"EvolutionChain: Species URL not found for {initial_pokemon_for_name.name}.")
        return None

    # Step 2: Get species data to find the evolution chain URL
    try:
        species_response = requests.get(species_url)
        species_response.raise_for_status()
        species_data = species_response.json()
    except requests.RequestException as e:
        print(f"EvolutionChain: Error fetching species data from {species_url}: {e}")
        return None

    evolution_chain_url = species_data.get('evolution_chain', {}).get('url')
    if not evolution_chain_url:
        print(f"EvolutionChain: Evolution chain URL not found in species data for {initial_pokemon_for_name.name}.")
        return None

    # Step 3: Get evolution chain data
    try:
        chain_response = requests.get(evolution_chain_url)
        chain_response.raise_for_status()
        evolution_chain_data = chain_response.json()
    except requests.RequestException as e:
        print(f"EvolutionChain: Error fetching evolution chain data from {evolution_chain_url}: {e}")
        return None
    
    if not evolution_chain_data or 'chain' not in evolution_chain_data:
        print("EvolutionChain: Evolution chain data is malformed or 'chain' key is missing.")
        return None

    # Step 4: Parse the chain data starting from the root
    return _parse_evolution_stage(evolution_chain_data['chain'])

def pokemon_detail(request, pokemon_name):
    pokemon_name_lower = pokemon_name.lower()
    pokemon_obj = get_or_fetch_pokemon_details(pokemon_name_lower)
    evolution_chain_data = None

    if pokemon_obj:
        pokemon_data_dict = {
            'id': pokemon_obj.pokeapi_id,
            'name': pokemon_obj.name.capitalize(),
            'height': pokemon_obj.height,
            'weight': pokemon_obj.weight,
            'abilities': [ability.name.capitalize() for ability in pokemon_obj.abilities.all()],
            'types': [ptype.name.capitalize() for ptype in pokemon_obj.types.all()],
            'sprite_front': pokemon_obj.sprite_url,
            'stats': pokemon_obj.stats if pokemon_obj.stats else {} 
        }
        # Fetch evolution chain
        evolution_chain_data = get_pokemon_evolution_chain(pokemon_obj.name) # Pass name

        context = {
            'pokemon_name': pokemon_obj.name.capitalize(),
            'pokemon_data': pokemon_data_dict,
            'evolution_chain': evolution_chain_data,
            'error': None
        }
    else:
        context = {
            'pokemon_name': pokemon_name.capitalize(),
            'pokemon_data': None,
            'evolution_chain': None,
            'error': f"Could not find or fetch data for {pokemon_name.capitalize()}."
        }
    return render(request, 'pokedex_app/pokemon_detail.html', context)

def pokemon_compare(request):
    pokemon1_name = request.GET.get('pokemon1')
    pokemon2_name = request.GET.get('pokemon2')
    pokemon1_data = None
    pokemon2_data = None
    comparison_results = None
    error_message = None

    # Get all Pokemon names for dropdowns
    all_pokemon_for_select = Pokemon.objects.all().order_by('name')
    if not all_pokemon_for_select and Pokemon.objects.count() < 151: # Try to fetch more if DB is sparse
        print("[ComparePage] DB has too few Pokemon for selection, attempting to seed initial 151 from API.")
        try:
            initial_response = requests.get('https://pokeapi.co/api/v2/pokemon?limit=151') # Gen 1 for starters
            if initial_response.status_code == 200:
                for p_info in initial_response.json().get('results', []):
                    get_or_fetch_pokemon_details(p_info['name']) # This will save them to DB
                all_pokemon_for_select = Pokemon.objects.all().order_by('name') # Re-query
            else:
                 print("[ComparePage SEED ERROR] Failed to seed initial Pokemon data from API.")
        except requests.RequestException:
            print("[ComparePage SEED ERROR] API error during initial Pokemon data seed.")

    if pokemon1_name and pokemon2_name:
        if pokemon1_name == pokemon2_name:
            error_message = "Please select two different Pokémon to compare."
        else:
            pokemon1_obj = get_or_fetch_pokemon_details(pokemon1_name)
            pokemon2_obj = get_or_fetch_pokemon_details(pokemon2_name)

            if pokemon1_obj and pokemon2_obj:
                pokemon1_data = {
                    'name': pokemon1_obj.name.capitalize(),
                    'sprite_url': pokemon1_obj.sprite_url,
                    'types': [t.name.capitalize() for t in pokemon1_obj.types.all()],
                    'stats': pokemon1_obj.stats or {},
                    'detail_url': reverse('pokemon_detail', kwargs={'pokemon_name': pokemon1_obj.name})
                }
                pokemon2_data = {
                    'name': pokemon2_obj.name.capitalize(),
                    'sprite_url': pokemon2_obj.sprite_url,
                    'types': [t.name.capitalize() for t in pokemon2_obj.types.all()],
                    'stats': pokemon2_obj.stats or {},
                    'detail_url': reverse('pokemon_detail', kwargs={'pokemon_name': pokemon2_obj.name})
                }

                # Basic stat comparison logic
                comparison_results = {}
                all_stat_names = sorted(list(set((pokemon1_data['stats'].keys() | pokemon2_data['stats'].keys()))))
                
                for stat_name in all_stat_names:
                    val1 = pokemon1_data['stats'].get(stat_name, 0)
                    val2 = pokemon2_data['stats'].get(stat_name, 0)
                    winner = 'pokemon1' if val1 > val2 else ('pokemon2' if val2 > val1 else 'tie')
                    comparison_results[stat_name.capitalize()] = {
                        'pokemon1_value': val1,
                        'pokemon2_value': val2,
                        'winner': winner
                    }
            else:
                error_message = "Could not retrieve data for one or both selected Pokémon."
                if not pokemon1_obj:
                    error_message += f" Problem with {pokemon1_name}."
                if not pokemon2_obj:
                    error_message += f" Problem with {pokemon2_name}."
    
    context = {
        'all_pokemon': all_pokemon_for_select,
        'pokemon1_name': pokemon1_name,
        'pokemon2_name': pokemon2_name,
        'pokemon1_data': pokemon1_data,
        'pokemon2_data': pokemon2_data,
        'comparison_results': comparison_results,
        'error_message': error_message,
        'title': "Compare Pokémon"
    }
    return render(request, 'pokedex_app/pokemon_compare.html', context)
