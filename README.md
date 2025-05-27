# Pokedex Challenge - Django

Ready to catch 'em all? This project is a Django-powered Pokedex application that allows users to explore, discover, and learn about Pokémon using data from the [PokeAPI](https://pokeapi.co/).

## Key Features

This application provides a rich user experience for Pokémon enthusiasts with the following features:

*   **Comprehensive Pokémon Listing**: Browse through a paginated list of Pokémon. The database is initially seeded from PokeAPI, ensuring a rich dataset from the start.
*   **Detailed Pokémon View**: Click on any Pokémon to see its detailed information, including:
    *   Official Sprite
    *   Pokédex ID, Height, and Weight
    *   Types and Abilities
    *   Base Stats displayed with visual progress bars
    *   Complete Evolution Chain, showing how the Pokémon evolves to and from other forms. Each Pokémon in the chain is clickable.
*   **Advanced Search & Filtering**:
    *   **Search by Name**: Quickly find any Pokémon by typing its name.
    *   **Filter by Type**: Display all Pokémon belonging to a selected type.
    *   **Filter by Ability**: Show all Pokémon that can have a specific ability (currently filters local DB, full API fetch for this filter is a potential improvement).
*   **Pokémon Comparison Tool**: Select any two Pokémon and compare their base stats side-by-side in a clear table format, highlighting the stronger stat for each category.
*   **Dynamic Home Page**: The main page welcomes users with a short introduction and showcases a carousel of random Pokémon with their sprites, linking directly to their detail pages. It also provides an overview of the application's features.
*   **Responsive Design**: Built with Bootstrap, the application is designed to be responsive and user-friendly on various screen sizes.
*   **Database Caching**: Pokémon data, once fetched from PokeAPI, is stored locally in a SQLite database to speed up subsequent requests and reduce API load. This includes Pokémon details, types, abilities, and stats.

## Technologies Used

*   **Python 3.x**
*   **Django 3.x/4.x** (or latest compatible version)
*   **Requests**: For making HTTP requests to the PokeAPI.
*   **HTML5, CSS3, JavaScript (via Bootstrap)**
*   **Bootstrap 4.5**: For responsive design and UI components.
*   **Font Awesome**: For icons.
*   **SQLite**: Default Django database for local storage.
*   **Docker**: For containerization of the application.

## Getting Started

Follow these instructions to get a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

*   Python 3.8 or higher (if running locally without Docker)
*   pip (Python package installer)
*   Git (optional, for cloning)
*   Docker Desktop (or Docker engine for Linux) if you prefer to run using Docker.

### Installation & Setup (Without Docker)

1.  **Clone the repository (or download the source code):**
    ```bash
    git clone <repository_url> # Replace <repository_url> with the actual URL
    cd Pokedex-Challenge
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv .venv
    # On Windows
    .venv\Scripts\activate
    # On macOS/Linux
    source .venv/bin/activate
    ```

3.  **Install the required packages:**
    ```bash
    pip install -r requirements.txt
    ```
    *Note: Ensure `requirements.txt` is up-to-date. If not, it should at least contain `Django` and `requests`.*

4.  **Apply database migrations:**
    ```bash
    python manage.py makemigrations pokedex_app
    python manage.py migrate
    ```

5.  **Run the development server:**
    ```bash
    python manage.py runserver
    ```
    The application will be accessible at `http://127.0.0.1:8000/` in your web browser.

### Running with Docker (Recommended for Easy Deployment)

This project includes a `Dockerfile` for easy setup and deployment using Docker.

1.  **Ensure Docker is installed and running** on your system.

2.  **Clone the repository (if you haven't already):**
    ```bash
    git clone <repository_url> # Replace <repository_url> with the actual URL
    cd Pokedex-Challenge
    ```

3.  **Build the Docker image:**
    From the root directory of the project (where the `Dockerfile` is located), run:
    ```bash
    docker build -t pokedex-challenge .
    ```
    This command builds a Docker image and tags it as `pokedex-challenge`.

4.  **Run the Docker container:**
    ```bash
    docker run -p 8000:8000 pokedex-challenge
    ```
    This command starts a container from the `pokedex-challenge` image and maps port 8000 of the container to port 8000 on your host machine.
    The application will then be accessible at `http://127.0.0.1:8000/` in your web browser.

    *   The first time you run the container, migrations will be applied automatically as defined in the `Dockerfile`.
    *   To run commands inside the running container (e.g., `manage.py` commands), you can use `docker exec`:
        ```bash
        # Find your container ID or name
        docker ps 
        # Execute a command (replace <container_id_or_name>)
        docker exec -it <container_id_or_name> python manage.py shell 
        ```

### Running Tests

This project includes a suite of tests to ensure functionality. To run the tests:

1.  **Ensure you have your virtual environment activated (if not using Docker):**
    ```bash
    # On Windows
    .venv\Scripts\activate
    # On macOS/Linux
    source .venv/bin/activate
    ```

2.  **Run the tests from the project's root directory (where `manage.py` is located):**
    ```bash
    python manage.py test pokedex_app
    ```
    This command will discover and run all tests within the `pokedex_app` application.

3.  **To run tests within a Docker container (if you have a running container or want to run them in a fresh one):**
    *   If you have a running container (e.g., from `docker run -d ...`):
        ```bash
        # Find your container ID or name
        docker ps 
        # Execute tests inside the container (replace <container_id_or_name>)
        docker exec -it <container_id_or_name> python manage.py test pokedex_app
        ```
    *   To run tests in a temporary container (builds the image if not present, then runs tests and removes container):
        You can modify the `CMD` in your `Dockerfile` temporarily or use a separate Docker command for testing that overrides the default `CMD`. For instance, if you want to run tests as part of a build process or one-off:
        ```bash
        docker build -t pokedex-challenge-test .
        docker run --rm pokedex-challenge-test python manage.py test pokedex_app
        ```
        (Note: The `CMD` in the provided `Dockerfile` runs migrations and then the server. For a dedicated test run in a new container, you'd typically override this `CMD` or have a specific test stage in a multi-stage Dockerfile for CI scenarios).

## Project Structure

```
Pokedex-Challenge/
├── pokedex_project/         # Django project directory
│   ├── __init__.py
│   ├── settings.py          # Project settings
│   ├── urls.py              # Main URL configurations
│   ├── wsgi.py
│   └── asgi.py
├── pokedex_app/             # Django app for Pokedex functionality
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── migrations/          # Database migrations
│   ├── models.py            # Database models (Pokemon, Type, Ability)
│   ├── static/              # Static files (CSS, JS, images)
│   │   └── pokedex_app/
│   │       └── images/
│   │           └── pokemon_placeholder.png
│   ├── templates/           # HTML templates
│   │   └── pokedex_app/
│   │       ├── base.html
│   │       ├── index.html
│   │       ├── pokemon_list.html
│   │       ├── pokemon_detail.html
│   │       ├── pokemon_compare.html
│   │       └── partials/
│   │           └── _evolution_chain_display.html
│   ├── tests.py
│   ├── urls.py              # App-specific URL configurations
│   └── views.py             # View functions (logic for handling requests)
├── .venv/                   # Virtual environment directory (if used locally)
├── Dockerfile               # Docker configuration for building the image
├── .dockerignore            # Specifies intentionally untracked files that Docker should ignore
├── manage.py                # Django's command-line utility
├── requirements.txt         # Project dependencies
└── README.md                # This file
```

## Future Enhancements & Ideas

While the current Pokedex is functional and feature-rich, here are some ideas for future development:

*   **Advanced Filtering & Sorting**: 
    *   Allow filtering by multiple types simultaneously (e.g., Grass AND Poison).
    *   Implement sorting of the Pokémon list by stats (e.g., highest Attack, lowest Speed).
    *   Filter by generation or region.
*   **User Accounts & Favorites**: 
    *   Allow users to create accounts.
    *   Enable users to mark Pokémon as favorites and view their favorite list.
*   **"Caught" List / My Pokedex**: 
    *   Users could mark Pokémon they have "caught" in games.
*   **Enhanced API Data**: 
    *   Display more detailed information like move sets, locations where Pokémon can be found, or flavor text entries from different game versions.
    *   Fetch and display shiny sprites.
*   **Full API Fetch for Ability Filter**: Currently, the ability filter in the list view only filters Pokémon already in the local database. Implement a full API fetch for the selected ability (similar to the type filter) to ensure all Pokémon with that ability are shown and cached.
*   **Asynchronous Background Tasks for API Interaction & Data Sync**: 
    *   Implement a task queue system (e.g., Celery with Redis or RabbitMQ as a broker) to handle API calls and data synchronization asynchronously, preventing blocking of user requests.
    *   Utilize Celery Beat to schedule periodic tasks for fetching updates from PokeAPI (e.g., daily updates for Pokémon data, checking for new Pokémon) to keep the local database current without manual intervention or direct user-triggered load.
    *   Leverage Django custom management commands, potentially triggered by Celery tasks, for bulk data operations such as initial database seeding or large-scale data migrations/updates from the API.
    *   This architecture would significantly improve application responsiveness, especially for operations requiring external API calls, make the system more resilient to API downtimes or rate limits, and ensure data freshness.
*   **Improved UI/UX**: 
    *   More dynamic interactions with JavaScript (e.g., live search results without page reload).
    *   Custom styling beyond Bootstrap defaults for a more unique look and feel.
    *   Better loading indicators for API calls, especially if deferring to background tasks.
*   **Admin Interface Enhancements**: Customize the Django admin to better manage Pokémon data, types, and abilities, and potentially to monitor background tasks.
*   **Testing**: Write more comprehensive unit and integration tests, covering more edge cases and UI interactions (e.g., with Selenium), and tests for the asynchronous tasks.
*   **Deployment**: Document steps for deploying the application to a platform like Heroku, PythonAnywhere, or AWS, including considerations for Celery workers and broker services.
*   **Team Builder**: A feature where users can build a team of Pokémon and see combined type weaknesses/resistances.
*   **Docker Compose for Multi-Container Setups**: For more complex deployments (e.g., with a separate database container like PostgreSQL, a web server like Nginx, Celery workers, and a Redis broker), implement `docker-compose.yml`.
*   **Production-Ready Dockerfile**: Optimize the `Dockerfile` for production (e.g., using a non-root user, multi-stage builds, Gunicorn as the application server instead of Django's development server).

---

This Pokedex Challenge project serves as a great way to practice and showcase Django development skills. Enjoy exploring the world of Pokémon!
