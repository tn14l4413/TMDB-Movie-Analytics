import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import create_engine

# -------------------------------------------------------------
# PAGE CONFIGURATION & DATABASE CONNECTION
# -------------------------------------------------------------
st.set_page_config(
    page_title="TMDB Movie Analytics Dashboard",
    page_icon="🎬",
    layout="wide",
)

# Configure your MySQL connection credentials here
# Remember to URL-encode special characters in passwords (e.g. '@' as '%40')
DB_USER = "root"
DB_PASSWORD = "Manoj1297%40"  # Update with your MySQL password
DB_HOST = "127.0.0.1"
DB_NAME = "tmdb"


@st.cache_resource
def get_db_engine():
  try:
    engine = create_engine(
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
    )
    return engine
  except Exception as e:
    st.error(f"Database connection failed: {e}")
    return None


engine = get_db_engine()


# Load core analytical dataframes cached for performance
@st.cache_data
def load_data():
  if not engine:
    return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

  movies_df = pd.read_sql("SELECT * FROM movies", engine)
  genres_df = pd.read_sql("SELECT * FROM genres", engine)
  movie_genres_df = pd.read_sql("SELECT * FROM movie_genres", engine)
  cast_df = pd.read_sql("SELECT * FROM `cast`", engine)

  # Pre-process dates and years
  movies_df["release_date"] = pd.to_datetime(
      movies_df["release_date"], errors="coerce"
  )
  movies_df["release_year"] = movies_df["release_date"].dt.year

  return movies_df, genres_df, movie_genres_df, cast_df


movies_df, genres_df, movie_genres_df, cast_df = load_data()

if movies_df.empty:
  st.warning(
      "⚠️ Please check your database connection credentials in `app.py` and"
      " ensure tables are loaded."
  )
  st.stop()


# -------------------------------------------------------------
# SHARED SIDEBAR FILTERS (Page 1 Logic & State Management)
# -------------------------------------------------------------
st.sidebar.header("🎬 Global Movie Filters")

# Initialize Session State defaults
if "selected_genres" not in st.session_state:
  st.session_state.selected_genres = []
if "year_range" not in st.session_state:
  min_y = int(movies_df["release_year"].min(skipna=True) or 1990)
  max_y = int(movies_df["release_year"].max(skipna=True) or 2026)
  st.session_state.year_range = (min_y, max_y)
if "min_rating" not in st.session_state:
  st.session_state.min_rating = 0.0
if "selected_lang" not in st.session_state:
  st.session_state.selected_lang = "All"

# 1. Genre Multiselect
all_genres = sorted(genres_df["genre_name"].dropna().unique().tolist())
selected_genres = st.sidebar.multiselect(
    "Select Genres", all_genres, default=st.session_state.selected_genres
)
st.session_state.selected_genres = selected_genres

# 2. Release Year Range Slider
min_year_val = int(movies_df["release_year"].min(skipna=True) or 1900)
max_year_val = int(movies_df["release_year"].max(skipna=True) or 2026)
year_range = st.sidebar.slider(
    "Release Year Range",
    min_value=min_year_val,
    max_value=max_year_val,
    value=st.session_state.year_range,
)
st.session_state.year_range = year_range

# 3. Minimum Rating Slider
min_rating = st.sidebar.slider(
    "Minimum Vote Average",
    min_value=0.0,
    max_value=10.0,
    value=st.session_state.min_rating,
    step=0.5,
)
st.session_state.min_rating = min_rating

# 4. Language Selectbox
languages = ["All"] + sorted(
    movies_df["original_language"].dropna().unique().tolist()
)
selected_lang = st.sidebar.selectbox(
    "Original Language",
    languages,
    index=languages.index(st.session_state.selected_lang)
    if st.session_state.selected_lang in languages
    else 0,
)
st.session_state.selected_lang = selected_lang

# -------------------------------------------------------------
# FILTERING ENGINE
# -------------------------------------------------------------
filtered_movies = movies_df.copy()

# Apply Year Filter
filtered_movies = filtered_movies[
    (filtered_movies["release_year"] >= year_range[0])
    & (filtered_movies["release_year"] <= year_range[1])
]

# Apply Rating Filter
filtered_movies = filtered_movies[
    filtered_movies["vote_average"] >= min_rating
]

# Apply Language Filter
if selected_lang != "All":
  filtered_movies = filtered_movies[
      filtered_movies["original_language"] == selected_lang
  ]

# Apply Genre Filter via Bridge Table
if selected_genres:
  valid_genre_ids = genres_df[genres_df["genre_name"].isin(selected_genres)][
      "genre_id"
  ].tolist()
  matched_movie_ids = movie_genres_df[
      movie_genres_df["genre_id"].isin(valid_genre_ids)
  ]["movie_id"].tolist()
  filtered_movies = filtered_movies[
      filtered_movies["movie_id"].isin(matched_movie_ids)
  ]

# Live Filter Match Counter in Sidebar
st.sidebar.markdown("---")
st.sidebar.metric(
    label="Matching Movies Found", value=f"{len(filtered_movies):,}"
)

# -------------------------------------------------------------
# NAVIGATION MENU
# -------------------------------------------------------------
st.sidebar.markdown("---")
page = st.sidebar.radio(
    "Navigation Menu", ["1. Filters Overview", "2. Dashboard", "3. Query Explorer"]
)

# =============================================================
# PAGE 1: FILTERS OVERVIEW
# =============================================================
if page == "1. Filters Overview":
  st.title("🎛️ Interactive Filter Control Center")
  st.markdown("""
    Welcome to the **TMDB Movie Analytics Platform**! Use the control panel on the sidebar to dynamically filter the global movie repository. 
    """)

  col1, col2, col3 = st.columns(3)
  col1.metric("Total Filtered Movies", f"{len(filtered_movies):,}")
  col2.metric("Selected Genres Count", len(selected_genres) if selected_genres else "All")
  col3.metric("Minimum Rating Threshold", f"{min_rating} / 10")

  st.subheader("📋 Sample of Filtered Records")
  st.dataframe(
      filtered_movies[[
          "title",
          "release_date",
          "original_language",
          "budget",
          "revenue",
          "vote_average",
      ]].head(15),
      use_container_width=True,
  )

# =============================================================
# PAGE 2: DASHBOARD
# =============================================================
elif page == "2. Dashboard":
  st.title("📊 Executive Movie Industry Dashboard")

  if filtered_movies.empty:
    st.warning("⚠️ No movies match your current filter criteria. Please broaden your selection.")
  else:
    # KPI Calculations for Filtered Selection
    total_movies = len(filtered_movies)
    
    filtered_movie_ids = filtered_movies["movie_id"].tolist()
    filtered_mg = movie_genres_df[movie_genres_df["movie_id"].isin(filtered_movie_ids)]
    unique_genres_count = filtered_mg["genre_id"].nunique()
    
    filtered_cast = cast_df[cast_df["movie_id"].isin(filtered_movie_ids)]
    unique_actors_count = filtered_cast["person_id"].nunique()
    
    avg_rating = filtered_movies["vote_average"].mean()

    # Display KPI Cards
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Filtered Movies", f"{total_movies:,}")
    kpi2.metric("Genres Represented", f"{unique_genres_count:,}")
    kpi3.metric("Unique Actors", f"{unique_actors_count:,}")
    kpi4.metric("Average Rating", f"{avg_rating:.2f} / 10")

    st.markdown("---")

    # Layout Row 1: Top 10 Revenue Bar Chart & Genre Distribution Donut
    col_a, col_b = st.columns(2)

    with col_a:
      st.subheader("💰 Top 10 Movies by Revenue")
      top_rev = filtered_movies.sort_values(by="revenue", ascending=False).head(10)
      if top_rev.empty or top_rev["revenue"].max() == 0:
        st.info("No revenue data available for this filter selection.")
      else:
        fig_rev = px.bar(
            top_rev,
            x="revenue",
            y="title",
            orientation="h",
            color="revenue",
            color_continuous_scale="Viridis",
            labels={"revenue": "Box Office Revenue ($)", "title": "Movie Title"},
        )
        fig_rev.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig_rev, use_container_width=True)

    with col_b:
      st.subheader("🍩 Genre Distribution")
      genre_merged = filtered_mg.merge(genres_df, on="genre_id")
      genre_dist = genre_merged["genre_name"].value_counts().reset_index()
      genre_dist.columns = ["genre_name", "count"]

      if genre_dist.empty:
        st.info("No genre data available.")
      else:
        fig_genre = px.pie(
            genre_dist,
            names="genre_name",
            values="count",
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Prism,
        )
        st.plotly_chart(fig_genre, use_container_width=True)

    # Layout Row 2: Budget vs Revenue Scatter Plot
    st.subheader("📈 Budget vs. Box-Office Revenue Analysis")
    valid_scat = filtered_movies[
        (filtered_movies["budget"] > 0) & (filtered_movies["revenue"] > 0)
    ]
    if valid_scat.empty:
      st.info("Insufficient financial records for scatter plot visualization.")
    else:
      fig_scat = px.scatter(
          valid_scat,
          x="budget",
          y="revenue",
          size="vote_count",
          color="vote_average",
          hover_name="title",
          color_continuous_scale="Plasma",
          labels={
              "budget": "Production Budget ($)",
              "revenue": "Box Office Revenue ($)",
          },
      )
      st.plotly_chart(fig_scat, use_container_width=True)

    # Auto-generated Text Insight Box
    st.markdown("---")
    st.subheader("📝 Automated View Insight")
    if not valid_scat.empty:
      highest_earner = filtered_movies.loc[filtered_movies["revenue"].idxmax()]
      st.success(
          f"**Market Highlight:** Within the current filtered view containing"
          f" {total_movies} titles, the highest-grossing film is"
          f" **{highest_earner['title']}** generating"
          f" **${highest_earner['revenue']:,}** with an average user score of"
          f" **{highest_earner['vote_average']}/10**."
      )
    else:
      st.info(
          f"The filtered dataset contains {total_movies} titles meeting your"
          " threshold constraints."
      )

# =============================================================
# PAGE 3: QUERY EXPLORER
# =============================================================
elif page == "3. Query Explorer":
  st.title("🔍 SQL Query Explorer & Analytics")
  st.markdown(
      "Execute and inspect predefined project analytical queries against your"
      " underlying MySQL database."
  )

  # Dictionary of Saved Project Queries
  saved_queries = {
      "1. Action Movies Released Post-2015": """
            SELECT m.title, m.release_date, m.vote_average
            FROM movies m
            JOIN movie_genres mg ON m.movie_id = mg.movie_id
            JOIN genres g ON mg.genre_id = g.genre_id
            WHERE g.genre_name = 'Action' AND m.release_date > '2015-12-31'
            ORDER BY m.release_date DESC LIMIT 50;
        """,
      "2. Top 10 Highest-Grossing Movies": """
            SELECT title, budget, revenue, vote_average
            FROM movies WHERE revenue > 0
            ORDER BY revenue DESC LIMIT 10;
        """,
      "3. Average Budget & Revenue by Genre": """
            SELECT g.genre_name, 
                   AVG(CASE WHEN m.budget > 0 THEN m.budget END) AS avg_budget,
                   AVG(CASE WHEN m.revenue > 0 THEN m.revenue END) AS avg_revenue
            FROM genres g
            JOIN movie_genres mg ON g.genre_id = mg.genre_id
            JOIN movies m ON mg.movie_id = m.movie_id
            GROUP BY g.genre_name ORDER BY avg_revenue DESC;
        """,
      "4. Top 10 Most Prolific Actors": """
            SELECT actor_name, COUNT(DISTINCT movie_id) AS movie_count
            FROM `cast` GROUP BY actor_name ORDER BY movie_count DESC LIMIT 10;
        """,
      "5. Directors with > 3 Movies": """
            SELECT person_name AS director_name, COUNT(DISTINCT movie_id) AS movie_count
            FROM crew WHERE job = 'Director'
            GROUP BY person_id, person_name HAVING movie_count > 3 ORDER BY movie_count DESC;
        """,
  }

  selected_query_name = st.selectbox(
      "Choose a Saved Analytical Query", list(saved_queries.keys())
  )
  chosen_sql = saved_queries[selected_query_name]

  with st.expander("View Raw SQL Query"):
    st.code(chosen_sql, language="sql")

  # Run Query and Display Results
  try:
    query_df = pd.read_sql(chosen_sql, engine)

    st.subheader("📋 Query Result Dataset")
    st.dataframe(query_df, use_container_width=True)

    st.subheader("📊 Visual Output")
    if query_df.shape[1] >= 2:
      numeric_cols = query_df.select_dtypes(
          include=[np.number]
      ).columns.tolist()

      if len(query_df) > 0 and len(query_df.columns) >= 2:
        x_col = query_df.columns[0]
        y_col = numeric_cols[0] if numeric_cols else query_df.columns[1]

        fig_query = px.bar(
            query_df.head(15),
            x=x_col,
            y=y_col,
            color=y_col,
            color_continuous_scale="Teal",
        )
        st.plotly_chart(fig_query, use_container_width=True)
    else:
      st.info("Dataset has insufficient dimensions for automated charting.")

    st.markdown("---")
    st.markdown("### 💡 Analytical Interpretation")
    st.info(
        f"Query executed successfully, returning **{len(query_df)}** records."
        " This analytical view extracts structured relational insights to aid"
        " studio decision-making, content licensing, and talent scouting."
    )

  except Exception as e:
    st.error(f"Error executing query: {e}")