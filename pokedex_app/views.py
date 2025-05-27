from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
import requests
from .models import Pokemon, Type, Ability # Import new models
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger # For DB pagination

# Create your views here.

def get_or_fetch_pokemon_details(pokemon_name_or_id):
    """Helper function to get Pokemon from DB or fetch from API and save."""
    try:
        if isinstance(pokemon_name_or_id, int):
            pokemon_obj = Pokemon.objects.get(pokeapi_id=pokemon_name_or_id)
        else:
            pokemon_obj = Pokemon.objects.get(name=str(pokemon_name_or_id).lower())
        print(f"[DB CACHE] Fetched {pokemon_obj.name} from DB for list/filter.")
        return pokemon_obj
    except Pokemon.DoesNotExist:
        print(f"[API FETCH] {pokemon_name_or_id} not in DB, fetching from API for list/filter.")
        api_url = f'https://pokeapi.co/api/v2/pokemon/{str(pokemon_name_or_id).lower()}/'
        response = requests.get(api_url)
        if response.status_code == 200:
            data = response.json()
            db_types = []
            for type_info in data.get('types', []):
                type_obj, _ = Type.objects.get_or_create(name=type_info['type']['name'])
                db_types.append(type_obj)
            db_abilities = []
            for ability_info in data.get('abilities', []):
                ability_obj, _ = Ability.objects.get_or_create(name=ability_info['ability']['name'])
                db_abilities.append(ability_obj)
            
            new_pokemon_obj = Pokemon.objects.create(
                pokeapi_id=data.get('id'),
                name=data.get('name'),
                height=data.get('height'),
                weight=data.get('weight'),
                sprite_url=data.get('sprites', {}).get('front_default')
            )
            new_pokemon_obj.types.set(db_types)
            new_pokemon_obj.abilities.set(db_abilities)
            return new_pokemon_obj
        return None

def pokemon_list(request):
    query = request.GET.get('q')
    selected_type_name = request.GET.get('type_filter_name')
    search_error = None
    all_types_for_filter = []

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

    pokemon_queryset = Pokemon.objects.all().order_by('pokeapi_id')

    if query and not selected_type_name:
        # Search by name (same as before)
        try:
            pokemon_obj = Pokemon.objects.get(name=query.lower())
            return redirect(reverse('pokemon_detail', kwargs={'pokemon_name': pokemon_obj.name}))
        except Pokemon.DoesNotExist:
            api_url = f'https://pokeapi.co/api/v2/pokemon/{query.lower()}/'
            response = requests.get(api_url)
            if response.status_code == 200:
                # The detail view will handle saving this new Pokemon to DB
                return redirect(reverse('pokemon_detail', kwargs={'pokemon_name': query.lower()}))
            else:
                search_error = f"Pokemon '{query}' not found."
    
    elif selected_type_name:
        # Filter by type
        # First, check if we have any Pokemon of this type in DB
        current_db_pokemon_of_type_count = Pokemon.objects.filter(types__name=selected_type_name).count()
        
        # Fetch all Pokemon of this type from API to ensure DB is complete for this type
        # This can be slow for types with many Pokemon if they are not already in DB.
        # Consider adding a flag or a more sophisticated check if this is too slow.
        print(f"[TYPE FILTER] Filtering by type: {selected_type_name}. Pokemon in DB: {current_db_pokemon_of_type_count}")
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

    # Initial DB seeding (if no filters/query and DB is sparse)
    # Check total Pokemon in DB, not just current queryset, to decide on seeding.
    if Pokemon.objects.count() < 20 and not query and not selected_type_name:
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
        'selected_type_name': selected_type_name
    }
    return render(request, 'pokedex_app/pokemon_list.html', context)

def index(request):
    return render(request, 'pokedex_app/index.html')

def pokemon_detail(request, pokemon_name):
    pokemon_name_lower = pokemon_name.lower()
    try:
        # Try to fetch from DB first
        pokemon_obj = Pokemon.objects.get(name=pokemon_name_lower)
        # Construct pokemon_data dictionary from the DB object
        pokemon_data_dict = {
            'id': pokemon_obj.pokeapi_id,
            'name': pokemon_obj.name.capitalize(),
            'height': pokemon_obj.height,
            'weight': pokemon_obj.weight,
            'abilities': [ability.name for ability in pokemon_obj.abilities.all()],
            'types': [ptype.name for ptype in pokemon_obj.types.all()],
            'sprite_front': pokemon_obj.sprite_url
        }
        # Reconstruct stats if you decide to store them as JSON or separate model later
        # For now, if we have the basic data from DB, we might not have stats unless fetched.
        # To keep it simple, if found in DB, we assume we have what we need for display.
        # If stats are critical, we'd fetch them if not in pokemon_data_dict.

        context = {
            'pokemon_name': pokemon_obj.name.capitalize(),
            'pokemon_data': pokemon_data_dict,
            'error': None
        }
        print(f"[DB CACHE] Fetched {pokemon_name_lower} from DB.") # Log DB hit

    except Pokemon.DoesNotExist:
        # Not in DB, fetch from API
        print(f"[API FETCH] {pokemon_name_lower} not in DB, fetching from API.") # Log API fetch
        api_url = f'https://pokeapi.co/api/v2/pokemon/{pokemon_name_lower()}/'
        response = requests.get(api_url)
        context = {
            'pokemon_name': pokemon_name.capitalize(),
            'pokemon_data': None,
            'error': None
        }

        if response.status_code == 200:
            data = response.json()
            
            # Create or update Type and Ability objects
            db_types = []
            for type_info in data.get('types', []):
                type_name = type_info['type']['name']
                type_obj, _ = Type.objects.get_or_create(name=type_name)
                db_types.append(type_obj)

            db_abilities = []
            for ability_info in data.get('abilities', []):
                ability_name = ability_info['ability']['name']
                ability_obj, _ = Ability.objects.get_or_create(name=ability_name)
                db_abilities.append(ability_obj)

            # Create Pokemon object in DB
            pokemon_obj = Pokemon.objects.create(
                pokeapi_id=data.get('id'),
                name=data.get('name'),
                height=data.get('height'),
                weight=data.get('weight'),
                sprite_url=data.get('sprites', {}).get('front_default')
            )
            pokemon_obj.types.set(db_types)
            pokemon_obj.abilities.set(db_abilities)
            
            # Construct pokemon_data for the template from API data (same as before, essentially)
            context['pokemon_data'] = {
                'id': data.get('id'),
                'name': data.get('name').capitalize(),
                'height': data.get('height'),
                'weight': data.get('weight'),
                'abilities': [a.name for a in db_abilities],
                'types': [t.name for t in db_types],
                'stats': {stat['stat']['name']: stat['base_stat'] for stat in data.get('stats', [])},
                'sprite_front': data.get('sprites', {}).get('front_default')
            }
        else:
            context['error'] = f"Could not fetch data for {pokemon_name.capitalize()} from API. Status: {response.status_code}"
    
    except Exception as e:
        # Catch any other unexpected errors during DB or API interaction
        print(f"[ERROR] Unexpected error in pokemon_detail for {pokemon_name_lower}: {e}")
        context = {
            'pokemon_name': pokemon_name.capitalize(),
            'pokemon_data': None,
            'error': f"An unexpected error occurred while fetching data for {pokemon_name.capitalize()}."
        }

    return render(request, 'pokedex_app/pokemon_detail.html', context)
