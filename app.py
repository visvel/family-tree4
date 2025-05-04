import streamlit as st
import sqlite3
import json
import os

# --- Helper to load tree structure from DB (already implemented elsewhere) ---
from tree_utils import load_family_tree_from_db  # Ensure this exists or inline the logic here

# --- Read static HTML and inject tree data ---
def generate_tree_html(tree_data):
    html_path = os.path.join("public", "tree.html")
    if not os.path.exists(html_path):
        st.error("tree.html not found!")
        return ""
    with open(html_path, "r", encoding="utf-8") as f:
        html_template = f.read()
    injected = html_template.replace("__TREE_DATA__", json.dumps(tree_data))
    return injected

# --- Streamlit UI ---
st.set_page_config(layout="wide")
st.title("Interactive Family Tree")

# Get query param
params = st.query_params
query_id = params.get("id", ["1"])[0].strip()
st.write(f"📌 Selected Root ID: {query_id}")

# Load and process tree
tree_data = load_family_tree_from_db(query_id)
if not tree_data:
    st.error("Could not load tree for the given ID.")
else:
    html_content = generate_tree_html(tree_data)
    st.components.v1.html(html_content, height=1000, scrolling=True)
