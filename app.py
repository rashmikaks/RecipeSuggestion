# app.py - Final merged TasteTrack (UI upgraded + sensor fixes)
import streamlit as st
import requests
import sqlite3
import os
import re
import json
import pandas as pd
from datetime import datetime
from textblob import TextBlob
from groq import Groq
import csv

from fit import collect_data  # your Google Fit collector

# -------- Config ----------
st.set_page_config(page_title="TasteTrack", page_icon="🍲", layout="centered")
WEATHER_SENSOR_URL = "http://10.37.194.153:5050/latest"
WEATHER_API_KEY = "86913ffe1b323a7bf0611b6e56ca77f6"
GROQ_API_KEY = "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"
groq_client = Groq(api_key=GROQ_API_KEY)

DB_FILE = "tastetrack.db"
CSV_FILE = "accuracy_results.csv"

# -------- DB init (home-mode uses DB) ----------
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS recipes (
    title TEXT PRIMARY KEY,
    ingredients TEXT,
    steps TEXT,
    mood TEXT,
    weather TEXT,
    source TEXT
)
""")
c.execute("CREATE TABLE IF NOT EXISTS feedback (recipe TEXT, liked INTEGER)")
conn.commit()

# -------- CSV init (votes) ----------
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "recipe_title", "rank", "steps", "active_minutes", "calories",
            "heart_points", "temperature", "condition", "cuisine_used",
            "country_detected", "city_detected", "date"
        ])

# -------- Helpers ----------
def enhance_recipe_text(recipe):
    """Ask LLM to add quantities / expand steps. Returns recipe dict."""
    try:
        prompt = f"""
Improve and enrich the following recipe for a professional cookbook.
- Add realistic quantities and make steps descriptive.
- Return JSON strictly: {{ "ingredients": [...], "steps": [...] }}

Title: {recipe.get('title')}
Ingredients: {', '.join(recipe.get('ingredients', []))}
Steps: {', '.join(recipe.get('steps', []))}
"""
        resp = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role":"user","content":prompt}],
        )
        txt = resp.choices[0].message.content
        m = re.search(r"\{.*\}", txt, re.S)
        if m:
            improved = json.loads(m.group())
            recipe["ingredients"] = improved.get("ingredients", recipe.get("ingredients", []))
            recipe["steps"] = improved.get("steps", recipe.get("steps", []))
    except Exception:
        pass
    return recipe

def normalize_ingredient(i):
    """Convert dictionary ingredient to readable string, or return string."""
    if isinstance(i, dict):
        parts = []
        # Common keys: quantity, name, description
        qty = i.get("quantity") or i.get("qty") or i.get("amount")
        name = i.get("name") or i.get("ingredient") or i.get("item")
        desc = i.get("description") or i.get("note")
        if qty:
            parts.append(str(qty))
        if name:
            parts.append(str(name))
        text = " ".join(parts).strip()
        if desc:
            text = f"{text} ({desc})" if text else f"{desc}"
        return text if text else json.dumps(i)
    return str(i)

def normalize_step(s):
    """Convert dictionary step to readable string, or return string."""
    if isinstance(s, dict):
        # Possible keys: action, description, step, text, instruction
        action = s.get("action") or s.get("title") or s.get("instruction") or ""
        desc = s.get("description") or s.get("text") or s.get("details") or ""
        combined = ""
        if action:
            combined = action.strip()
            if desc:
                # ensure punctuation separation
                combined = combined.rstrip(".") + ". " + desc.strip()
        else:
            combined = desc.strip()
        return combined.strip() if combined.strip() else json.dumps(s)
    return str(s)

def clean_step_text(s):
    """Remove duplicated 'Step X:' patterns at the start and return the cleaned step text.
    We'll render steps with a single 'Step i:' prefix in the UI.
    """
    if not isinstance(s, str):
        return s
    # Remove any leading repeated "Step <num>:" sequences (case-insensitive).
    # Example: "Step 1: Step 1: Mix" -> "Mix"
    s2 = re.sub(r'^(?:\s*(?i:step)\s*\d+\s*:\s*)+', '', s).strip()
    # Also remove any leftover initial 'Step X:' if present
    s2 = re.sub(r'^(?i:step)\s*\d+\s*:\s*', '', s2).strip()
    return s2

def pretty_card_start():
    st.markdown("<div style='padding:14px; border-radius:8px; box-shadow:0 1px 6px rgba(0,0,0,0.06); margin-bottom:12px;'>", unsafe_allow_html=True)

def pretty_card_end():
    st.markdown("</div>", unsafe_allow_html=True)

# -------- Session defaults ----------
defaults = {
    "recipe_index": 0, "recipes": [], "source": "", "weather_main": "", "temp": 0,
    "mood": "", "sentiment": "", "show_details": False,
    "sensor_recipes": [], "sensor_steps": None, "sensor_active": None,
    "sensor_calories": None, "sensor_heart": None, "sensor_temp": None,
    "sensor_condition": None, "sensor_city": None, "sensor_state": None,
    "sensor_country": None, "meal_time": None, "food_type": None,
    "cuisine_override": None, "last_cuisine_used": None
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# -------- Header (small) ----------
st.markdown("""
<style>
div.stButton > button { background-color:#6c6c6c !important; color: white !important; border-radius:8px !important; padding:10px 18px !important; }
.small-btn .stButton>button { padding:6px 10px !important; font-size:14px !important; }
.card-title { font-size:22px; margin-bottom:6px; font-weight:700; }
.card-sub { color:#555; margin-bottom:8px; }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 style='text-align:center'>TasteTrack — Smart Recipe Assistant</h1>", unsafe_allow_html=True)
st.markdown("<hr>", unsafe_allow_html=True)

# -------- Sidebar mode toggle and pages ----------
mode = st.sidebar.radio("Mode:", ["User Mode", "Sensor Mode"])

if mode == "User Mode":
    pages = ["Home", "Admin (DB Viewer)", "Analytics"]
else:
    pages = ["Smart Sensor Mode", "Accuracy Results"]

page = st.sidebar.radio("Page:", pages)

# -------------------- PAGE: HOME --------------------
if mode == "User Mode" and page == "Home":
    location = st.text_input("Enter city:")
    if location:
        try:
            url = f"http://api.openweathermap.org/data/2.5/weather?q={location}&appid={WEATHER_API_KEY}&units=metric"
            res = requests.get(url, timeout=8); data = res.json()
            if res.status_code == 200 and "weather" in data:
                w = data["weather"][0]
                main = w.get("main","Unknown"); desc = w.get("description","").title()
                temp = data.get("main",{}).get("temp","N/A"); icon = w.get("icon","01d")
                st.image(f"http://openweathermap.org/img/wn/{icon}@2x.png", width=80)
                st.markdown(f"**{location.title()} — {main}**  \n{desc}  \nTemperature: {temp} °C")
                st.session_state.weather_main = main; st.session_state.temp = temp
            else:
                st.error("Weather fetch failed.")
        except Exception as e:
            st.error(f"Weather error: {e}")

    st.subheader("How do you feel?")
    mood_choice = st.radio("Mood input:", ["Choose Mood","Enter Mood"], horizontal=True)
    if mood_choice == "Choose Mood":
        mood_text = st.selectbox("Mood:", ["Happy","Stressed","Relaxed","Excited","Tired","Sad","Bored"])
    else:
        mood_text = st.text_input("Enter mood:")

    if st.button("Get Recipes"):
        if not mood_text or not mood_text.strip():
            st.warning("Select or enter a mood.")
        else:
            blob = TextBlob(mood_text); score = blob.sentiment.polarity
            st.session_state.mood = mood_text; st.session_state.sentiment = score
            # DB lookup
            c.execute("SELECT * FROM recipes WHERE mood=? AND weather=?", (mood_text, st.session_state.weather_main))
            rows = c.fetchall()
            if rows:
                st.session_state.recipes = [{
                    "title": r[0],
                    "ingredients": json.loads(r[1]),
                    "steps": json.loads(r[2]),
                    "mood": r[3], "weather": r[4], "source": r[5]
                } for r in rows]
                st.success("Loaded from DB")
            else:
                st.info("Generating via AI...")
                try:
                    prompt = f"Suggest 3 recipes for mood '{mood_text}' and weather '{st.session_state.weather_main}'. Return JSON array."
                    resp = groq_client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user","content":prompt}])
                    txt = resp.choices[0].message.content; m = re.search(r"\[.*\]", txt, re.S)
                    if m:
                        recs = json.loads(m.group())
                        recs = [enhance_recipe_text(r) for r in recs]
                        for r in recs:
                            c.execute("INSERT OR REPLACE INTO recipes VALUES (?,?,?,?,?,?)",
                                      (r["title"], json.dumps(r["ingredients"]), json.dumps(r["steps"]), mood_text, st.session_state.weather_main, "Groq AI"))
                        conn.commit()
                        st.session_state.recipes = recs; st.success("Generated & saved")
                    else:
                        st.error("AI invalid format.")
                except Exception as e:
                    st.error(f"AI error: {e}")

    # show recipe if present
    if st.session_state.recipes:
        r = st.session_state.recipes[st.session_state.recipe_index]
        pretty_card_start()
        # Title: single-line style
        st.markdown(f"<h3 style='margin:0; padding:0; font-weight:700;'>{r.get('title')}</h3>", unsafe_allow_html=True)

        # toggles for expanders: persist state keys
        home_ing_key = "home_ing_exp"
        home_step_key = "home_step_exp"
        if home_ing_key not in st.session_state:
            st.session_state[home_ing_key] = False
        if home_step_key not in st.session_state:
            st.session_state[home_step_key] = False

        col1, col2 = st.columns([1,1])
        with col1:
            if st.button("Show Ingredients", key="home_show_ings", use_container_width=True):
                st.session_state[home_ing_key] = not st.session_state[home_ing_key]
        with col2:
            if st.button("Next Recipe", key="home_next", use_container_width=True):
                st.session_state.recipe_index = (st.session_state.recipe_index + 1) % len(st.session_state.recipes)

        # Ingredients expander
        if st.session_state.get(home_ing_key, False):
            with st.expander("Ingredients", expanded=True):
                for ing in r.get("ingredients", []):
                    st.markdown(f"- {normalize_ingredient(ing)}")

        # Steps expander
        if st.session_state.get(home_step_key, False):
            with st.expander("Steps", expanded=True):
                for i, s in enumerate(r.get("steps", []), start=1):
                    step_text = clean_step_text(normalize_step(s))
                    st.markdown(f"**Step {i}:** {step_text}")

        # Also show a small "Show Steps" button separate
        if st.button("Show Steps", key="home_show_steps", use_container_width=True):
            st.session_state[home_step_key] = not st.session_state[home_step_key]

        st.caption(f"Source: {r.get('source')}")
        # feedback
        col1, col2 = st.columns(2)
        with col1:
            if st.button("👍 Like", key="home_like"):
                c.execute("INSERT INTO feedback VALUES (?,?)", (r["title"], 1)); conn.commit(); st.success("Thanks!")
        with col2:
            if st.button("👎 Dislike", key="home_dislike"):
                c.execute("INSERT INTO feedback VALUES (?,?)", (r["title"], 0)); conn.commit(); st.warning("Noted")
        pretty_card_end()

# -------------------- PAGE: SMART SENSOR MODE --------------------
elif mode == "Sensor Mode" and page == "Smart Sensor Mode":
    st.title("Smart Sensor Mode")
    # meal time
    hh = datetime.now().hour
    if hh < 12: st.session_state.meal_time = "Morning"
    elif hh < 16: st.session_state.meal_time = "Afternoon"
    elif hh < 20: st.session_state.meal_time = "Evening"
    else: st.session_state.meal_time = "Night"
    st.info(f"Meal time: {st.session_state.meal_time}")

    # cuisine UI: radio Auto / Manual (Option C)
    cuisine_mode = st.radio("Cuisine selection:", ["Auto (use detected country)", "Manual (enter cuisine)"])
    if cuisine_mode == "Manual (enter cuisine)":
        override = st.text_input("Enter cuisine (e.g. Italian):").strip()
        st.session_state.cuisine_override = override if override else None
    else:
        # keep previous override if present but the UI "Auto" should clear typed value
        st.session_state.cuisine_override = None

    # food category
    st.write("Category:")
    st.session_state.food_type = st.selectbox("", ["Breakfast","Lunch","Dinner","Snacks","Dessert","Beverage","Soup","High Protein","Comfort Food","Hydration","Weight Loss Friendly"])

    # Google Fit - connect button
    col_a, col_b = st.columns([1,1])
    with col_a:
        if st.button("Connect Google Fit"):
            try:
                sd = collect_data()
                st.session_state.sensor_steps = sd.get("steps",0)
                st.session_state.sensor_active = sd.get("active_minutes",0)
                st.session_state.sensor_calories = sd.get("calories_burned",0.0)
                st.session_state.sensor_heart = sd.get("heart_points",0.0)
                st.success("Google Fit data collected")
            except Exception as e:
                st.error(f"Fit error: {e}")
    with col_b:
        st.write("")  # placeholder for alignment (no large blank blocks)

    # Google Fit display: 4-column clean layout (Steps | Active Minutes | Calories Burned | Heart Points)
    if st.session_state.sensor_steps is not None:
        g1, g2, g3, g4 = st.columns(4)
        with g1:
            st.markdown("**Steps**")
            st.markdown(st.session_state.sensor_steps)
        with g2:
            st.markdown("**Active Minutes**")
            st.markdown(st.session_state.sensor_active)
        with g3:
            st.markdown("**Calories Burned**")
            st.markdown(st.session_state.sensor_calories)
        with g4:
            st.markdown("**Heart Points**")
            st.markdown(st.session_state.sensor_heart)

    # fetch weather from phone
    # st.markdown("Open get_location.html on phone and press 'Send Location'. Then click below.")
    if st.button("Fetch Weather from Phone"):
        try:
            r = requests.get(WEATHER_SENSOR_URL, timeout=8); data = r.json()
            weather = data.get("weather", {})
            if weather and "weather" in weather and "main" in weather:
                cond = weather["weather"][0].get("description","")
                main_cond = weather["weather"][0].get("main","")
                temp = weather.get("main",{}).get("temp", None)
                st.session_state.sensor_temp = temp
                st.session_state.sensor_condition = main_cond
                st.session_state.sensor_city = data.get("city","Unknown")
                st.session_state.sensor_state = data.get("state","")
                st.session_state.sensor_country = data.get("country","")
                st.success(f"Fetched weather for {st.session_state.sensor_city}")
            else:
                st.error("No weather in response")
        except Exception as e:
            st.error(f"Sensor server error: {e}")

    # -- Persistent weather display (two rows: City|State|Country and Temperature|Condition) --
    if st.session_state.get("sensor_city") or st.session_state.get("sensor_country") or st.session_state.get("sensor_temp") is not None:
        # Row 1: City | State | Country
        c1, c2, c3 = st.columns(3)
        with c1:
            city_txt = st.session_state.get("sensor_city") or "Unknown"
            st.markdown(f"**City**  \n{city_txt}")
        with c2:
            state_txt = st.session_state.get("sensor_state") or "N/A"
            st.markdown(f"**State**  \n{state_txt}")
        with c3:
            country_txt = st.session_state.get("sensor_country") or "N/A"
            st.markdown(f"**Country**  \n{country_txt}")
        # Row 2: Temperature | Condition
        d1, d2 = st.columns([1,1])
        with d1:
            temp_txt = st.session_state.get("sensor_temp")
            temp_display = f"{temp_txt} °C" if temp_txt is not None else "N/A"
            st.markdown(f"**Temperature**  \n{temp_display}")
        with d2:
            cond_txt = st.session_state.get("sensor_condition") or "N/A"
            st.markdown(f"**Condition**  \n{cond_txt}")

    # generate recipes (sensor) - not stored in DB per choice
    if st.button("Generate Top 3 Recipes"):
        if st.session_state.sensor_steps is None or st.session_state.sensor_temp is None:
            st.warning("Collect Google Fit and Phone Weather first.")
        else:
            try:
                # decide cuisine
                if st.session_state.cuisine_override:
                    cuisine_used = st.session_state.cuisine_override
                else:
                    cuisine_used = st.session_state.sensor_country or "Local"

                prompt = f"""
You are a GLOBAL smart food recommender.
User context:
- City: {st.session_state.sensor_city}
- State: {st.session_state.sensor_state}
- Country: {st.session_state.sensor_country}
- Cuisine override: {cuisine_used}
- Meal time: {st.session_state.meal_time}
- Category: {st.session_state.food_type}
- Weather: {st.session_state.sensor_condition}
- Temp (C): {st.session_state.sensor_temp}
- Activity: steps={st.session_state.sensor_steps}, active_min={st.session_state.sensor_active}, calories={st.session_state.sensor_calories}, heart={st.session_state.sensor_heart}

Rules:
1) Use cuisine_override if provided (exact cuisine). Otherwise choose dishes typical for the detected country.
2) Match meal time (breakfast/snack/main/night).
3) Match category (e.g. Dessert, High Protein).
4) Consider weather and activity (hot -> cooling; cold -> warm; high activity -> protein).
5) Return EXACT JSON array of 3 objects:
[
  {{
    "title": "Recipe Name",
    "ingredients": ["item1","item2"],
    "steps": ["step1","step2"]
  }},
  ...
]
Do NOT output anything outside the JSON.
"""
                resp = groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role":"user","content":prompt}],
                )
                txt = resp.choices[0].message.content
                m = re.search(r"\[.*\]", txt, re.S)
                if not m:
                    st.error("AI returned invalid format.")
                else:
                    recipes = json.loads(m.group())
                    final = []
                    for rcp in recipes:
                        rcp = enhance_recipe_text(rcp)  # keep enhancement
                        # clean steps of duplicated "Step X:" patterns after normalization
                        rcp["steps"] = [clean_step_text(normalize_step(s)) for s in rcp.get("steps", [])]
                        # normalize ingredients as well
                        rcp["ingredients"] = [normalize_ingredient(i) for i in rcp.get("ingredients", [])]
                        final.append(rcp)
                    # set to session (do NOT store in DB)
                    st.session_state.sensor_recipes = final
                    st.session_state.last_cuisine_used = cuisine_used
                    st.success("Top 3 recipes generated")
            except Exception as e:
                st.error(f"AI error: {e}")

    # display & vote (votes saved to CSV)
    if st.session_state.sensor_recipes:
        st.subheader("Top 3 (Sensor Mode)")
        icons = ["🥇","🥈","🥉"]
        for idx, r in enumerate(st.session_state.sensor_recipes):
            pretty_card_start()
            # Title on one line
            title_html = r.get("title") or "Recipe"
            st.markdown(f"<h3 style='margin:0; padding:0; font-weight:700;'>{title_html}</h3>", unsafe_allow_html=True)

            # expander states per recipe
            exp_ing = f"sensor_ing_exp_{idx}"
            exp_step = f"sensor_step_exp_{idx}"
            if exp_ing not in st.session_state:
                st.session_state[exp_ing] = False
            if exp_step not in st.session_state:
                st.session_state[exp_step] = False

            cols = st.columns([1,1,1])
            with cols[0]:
                if st.button("Show Ingredients", key=f"s_show_ing_{idx}", help="Show ingredients", use_container_width=True):
                    st.session_state[exp_ing] = not st.session_state[exp_ing]
            with cols[1]:
                if st.button("Show Steps", key=f"s_show_step_{idx}", help="Show steps", use_container_width=True):
                    st.session_state[exp_step] = not st.session_state[exp_step]
            with cols[2]:
                if st.button("Vote (This is best)", key=f"s_vote_{idx}", help="Vote for this recipe", use_container_width=True):
                    try:
                        with open(CSV_FILE, "a", newline="") as f:
                            w = csv.writer(f)
                            w.writerow([
                                r.get("title"),
                                idx+1,
                                st.session_state.sensor_steps,
                                st.session_state.sensor_active,
                                st.session_state.sensor_calories,
                                st.session_state.sensor_heart,
                                st.session_state.sensor_temp,
                                st.session_state.sensor_condition,
                                st.session_state.last_cuisine_used,
                                st.session_state.sensor_country,
                                st.session_state.sensor_city,
                                datetime.now().isoformat()
                            ])
                        st.success("Vote recorded")
                    except Exception as e:
                        st.error(f"Save error: {e}")

            # Ingredients expander
            if st.session_state.get(exp_ing, False):
                with st.expander("Ingredients", expanded=True):
                    # ingredients might already be normalized above; ensure readable
                    for ing in r.get("ingredients", []):
                        st.markdown(f"- {ing}")

            # Steps expander
            if st.session_state.get(exp_step, False):
                with st.expander("Steps", expanded=True):
                    for i, s in enumerate(r.get("steps", []), start=1):
                        st.markdown(f"**Step {i}:** {s}")

            pretty_card_end()

        # explore more
        if st.button("🔁 Explore More"):
            try:
                cuisine_used = st.session_state.last_cuisine_used or (st.session_state.sensor_country or "Local")
                prompt = f"Suggest 3 different recipes for cuisine={cuisine_used}, meal_time={st.session_state.meal_time}, category={st.session_state.food_type}, weather={st.session_state.sensor_condition}, steps={st.session_state.sensor_steps}. Return JSON array."
                resp = groq_client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user","content":prompt}])
                txt = resp.choices[0].message.content; m = re.search(r"\[.*\]", txt, re.S)
                if m:
                    newr = json.loads(m.group())
                    final = []
                    for rr in newr:
                        rr = enhance_recipe_text(rr)
                        rr["steps"] = [clean_step_text(normalize_step(s)) for s in rr.get("steps", [])]
                        rr["ingredients"] = [normalize_ingredient(i) for i in rr.get("ingredients", [])]
                        final.append(rr)
                    st.session_state.sensor_recipes = final; st.success("New set ready")
                else:
                    st.error("AI invalid")
            except Exception as e:
                st.error(f"Explore error: {e}")

# -------------------- PAGE: ACCURACY RESULTS (Sensor Mode) --------------------
elif mode == "Sensor Mode" and page == "Accuracy Results":
    st.title("Accuracy Results (Sensor votes)")
    if os.path.exists(CSV_FILE):
        df = pd.read_csv(CSV_FILE)
        if df.empty:
            st.info("No votes yet.")
        else:
            st.subheader("Rank counts")
            st.bar_chart(df["rank"].value_counts())
            total = len(df); rank1 = len(df[df["rank"]==1])
            acc = (rank1/total)*100 if total>0 else 0.0
            st.metric("Rank1 chosen %", f"{acc:.2f}%")
            # show cuisine used column only if present
            if "cuisine_used" in df.columns:
                st.subheader("Cuisine used (top)")
                st.write(df["cuisine_used"].value_counts().head(10))
            else:
                st.info("No cuisine info in CSV.")
            st.write("---")
            st.dataframe(df)
    else:
        st.warning("No vote CSV found.")

# -------------------- PAGE: ADMIN (DB Viewer) --------------------
elif mode == "User Mode" and page == "Admin (DB Viewer)":
    st.header("Recipe DB Viewer")
    pw = st.text_input("Admin password", type="password")
    if pw == "123":
        df = pd.read_sql_query("SELECT * FROM recipes", conn)
        st.dataframe(df)
        if st.button("Clear DB"):
            c.execute("DELETE FROM recipes"); conn.commit(); st.success("Cleared")
    else:
        st.warning("Enter admin password")

# -------------------- PAGE: ANALYTICS (User Mode) --------------------
elif mode == "User Mode" and page == "Analytics":
    st.header("Feedback Analytics")
    df = pd.read_sql_query("SELECT * FROM feedback", conn)
    if df.empty:
        st.info("No feedback yet.")
    else:
        st.bar_chart(df["liked"].value_counts()); st.write(f"Total feedback: {len(df)}")

# End of file
