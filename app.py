# app.py

try:
    import streamlit as st
    import sqlite3
    import json
    from collections import deque
except ModuleNotFoundError as e:
    raise ImportError("This script must be run in a Streamlit environment where the 'streamlit' module is available.") from e

# Load data from SQLite
def load_family_tree_from_db(root_id="P1"):
    st.write("📥 Starting family tree loading...")
    conn = sqlite3.connect("family_tree.db")
    cursor = conn.cursor()

    def normalize_id(raw_id):
        try:
            return str(int(float(raw_id)))
        except:
            return str(raw_id).strip()

    def fetch_person_record(pid):
        st.write(f"🔎 Querying DB for person: {pid}")
        cursor.execute("SELECT * FROM people WHERE id = ?", (pid,))
        row = cursor.fetchone()
        if not row:
            st.warning(f"⚠️ Person not found: {pid}")
            return None
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))

    visited = set()
    nodes = {}
    couple_links = {}
    queue = deque([normalize_id(root_id)])

    while queue:
        st.write(f"📬 Queue: {[x for x in queue]}")
        pid = queue.popleft()
        pid = normalize_id(pid)
        if pid in visited:
            st.write(f"🔁 Skipping already visited person: {pid} to avoid cycles")
            continue
        visited.add(pid)

        st.write(f"🔍 Fetching person: {pid}")
        data = fetch_person_record(pid)
        if not data:
            continue

        person = {
            "id": normalize_id(data["id"]),
            "name": data["name"],
            "dob": data["dob"],
            "valavu": data["valavu"],
            "is_alive": data["alive"] == "Yes",
            "url": f"https://abc.com?id={normalize_id(data['id'])}"
        }

        spouse_ids = [normalize_id(sid) for sid in str(data.get("spouse_id", "")).split(";") if sid.strip() and sid.lower() != "nan"]
        children_ids = [normalize_id(cid) for cid in str(data.get("children_ids", "")).split(";") if cid.strip() and cid.lower() != "nan"]

        st.write(f"👫 Spouse IDs: {spouse_ids} | 👶 Children IDs: {children_ids}")

        if spouse_ids:
            spouse_id = spouse_ids[0]  # Support one spouse for now
            spouse_data = fetch_person_record(spouse_id)
            if spouse_data:
                spouse = {
                    "id": normalize_id(spouse_data["id"]),
                    "name": spouse_data["name"],
                    "dob": spouse_data["dob"],
                    "valavu": spouse_data["valavu"],
                    "is_alive": spouse_data["alive"] == "Yes",
                    "url": f"https://abc.com?id={normalize_id(spouse_data['id'])}"
                }
                st.write(f"💍 {person['name']} is married to {spouse['name']}")
                couple_id = f"{person['id']}_couple"
                couple_node = {
                    "id": couple_id,
                    "type": "couple",
                    "husband": person if data.get("gender") == "M" else spouse,
                    "wife": spouse if data.get("gender") == "M" else person,
                    "children": []
                }
                nodes[couple_id] = couple_node
                couple_links[person["id"]] = couple_id
                couple_links[spouse["id"]] = couple_id

                for cid in children_ids:
                    if cid not in visited:
                        queue.append(cid)

        if children_ids:
            person["children"] = []
            for cid in children_ids:
                if cid not in visited:
                    queue.append(cid)

        if person["id"] in couple_links:
            # Attach children to couple
            couple_node = nodes[couple_links[person["id"]]]
            for cid in children_ids:
                child_id = normalize_id(cid)
                child_node = nodes.get(couple_links.get(child_id), None)
                if not child_node:
                    child_data = fetch_person_record(child_id)
                    if child_data:
                        child_node = {
                            "id": child_id,
                            "name": child_data["name"],
                            "dob": child_data["dob"],
                            "valavu": child_data["valavu"],
                            "is_alive": child_data["alive"] == "Yes",
                            "url": f"https://abc.com?id={child_id}"
                        }
                if child_node:
                    st.write(f"👶 Adding child {child_node['name']} to couple {couple_node['id']}")
                    couple_node["children"].append(child_node)
        else:
            for cid in children_ids:
                child_id = normalize_id(cid)
                child_node = nodes.get(couple_links.get(child_id), None)
                if not child_node:
                    child_data = fetch_person_record(child_id)
                    if child_data:
                        child_node = {
                            "id": child_id,
                            "name": child_data["name"],
                            "dob": child_data["dob"],
                            "valavu": child_data["valavu"],
                            "is_alive": child_data["alive"] == "Yes",
                            "url": f"https://abc.com?id={child_id}"
                        }
                if child_node:
                    person.setdefault("children", []).append(child_node)

        if person["id"] not in couple_links:
            st.write(f"🧩 Node created: {person['id']} ({person['name']})")
            nodes[person["id"]] = person

    st.write(f"✅ Total nodes created: {len(nodes)}")
    conn.close()
    return nodes.get(root_id) or list(nodes.values())[0]

# Inject HTML from external file
def get_html():
    with open("public/tree.html") as f:
        return f.read()

# Streamlit app
st.set_page_config(layout="wide")
st.title("Interactive Family Tree")

params = st.query_params
query_id = params.get("id", ["1"])[0]
st.write(f"📌 Selected Root ID: {query_id}")

tree_data = load_family_tree_from_db(query_id)

if tree_data:
    with open("public/tree.html", "r") as f:
        html = f.read().replace("__TREE_DATA__", json.dumps(tree_data))
    st.components.v1.html(html, height=700, scrolling=True)
else:
    st.warning("⚠️ No data found or failed to generate tree.")
