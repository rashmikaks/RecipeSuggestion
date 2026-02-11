TasteTrack – Smart Recipe Assistant

1. Project Overview
TasteTrack is a Streamlit-based smart recipe assistant that recommends personalized recipes based on the user's mood and the current weather. The system integrates APIs and libraries to analyze sentiment, fetch live weather data, generate recipes using AI, and store user feedback in a local database.

Core Components:
- OpenWeatherMap API: Fetches real-time weather data.
- TextBlob: Performs mood sentiment analysis.
- Groq LLaMA 3.3 API: Generates and enhances recipe content.
- SQLite: Stores recipes and user feedback.
- Streamlit: Provides an interactive user interface.

2. Dependencies
Install Python 3.10 or above.

Create a virtual environment to keep dependencies isolated: (optional)
    python3 -m venv venv
Activate the virtual environment:
    source venv/bin/activate        # For macOS/Linux
    venv\Scripts\activate           # For Windows

Install required libraries using:
    pip install -r requirements.txt

If needed, individual modules can be installed using:
    pip install streamlit requests textblob groq pandas

3. Setup Instructions
    1. Extract the ZIP archive TasteTrack.zip
    2. Open the terminal and navigate to the folder:
        cd TasteTrack
    3. Ensure the following files are present:
        app.py
        requirements.txt
        tastetrack.db
    4. Open app.py and update the API keys:
        WEATHER_API_KEY = "your_openweather_api_key"
        GROQ_API_KEY = "your_groq_api_key"
    5. Run the Streamlit application:
        streamlit run app.py

4. Usage Instructions
    1. Enter a city name to fetch current weather data.
    2. Select or type a mood (Happy, Relaxed, Tired, etc.).
    3. Click Get Recipes to view personalized results.
    4. Review ingredients and steps.
    5. Provide feedback using Like or Dislike buttons.
    6. Use sidebar options:
    - Admin (DB Viewer): View or clear recipes.
    - Analytics: Visualize feedback statistics.

5. Features
- AI-generated recipe suggestions based on mood and weather.
- Interactive Streamlit web interface.
- Local database storage using SQLite.
- Mood sentiment detection using TextBlob.
- Analytics visualization for user feedback.