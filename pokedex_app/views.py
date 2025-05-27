from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
import requests
from .models import Pokemon, Type, Ability # Import new models
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger # For DB pagination
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

def pokemon_detail(request, pokemon_name):
    pokemon_name_lower = pokemon_name.lower()
    pokemon_obj = get_or_fetch_pokemon_details(pokemon_name_lower)

    if pokemon_obj:
        pokemon_data_dict = {
            'id': pokemon_obj.pokeapi_id,
            'name': pokemon_obj.name.capitalize(),
            'height': pokemon_obj.height,
            'weight': pokemon_obj.weight,
            'abilities': [ability.name for ability in pokemon_obj.abilities.all()],
            'types': [ptype.name for ptype in pokemon_obj.types.all()],
            'sprite_front': pokemon_obj.sprite_url,
            'stats': pokemon_obj.stats if pokemon_obj.stats else {} 
        }
        context = {
            'pokemon_name': pokemon_obj.name.capitalize(),
            'pokemon_data': pokemon_data_dict,
            'error': None
        }
    else:
        context = {
            'pokemon_name': pokemon_name.capitalize(),
            'pokemon_data': None,
            'error': f"Could not find or fetch data for {pokemon_name.capitalize()}."
        }
    return render(request, 'pokedex_app/pokemon_detail.html', context)
