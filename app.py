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
    conn = sqlite3.connect("family_tree.db")
    cursor = conn.cursor()

    def normalize_id(raw_id):
        try:
            return str(int(float(raw_id)))
        except:
            return str(raw_id).strip()

    def fetch_person_record(pid):
        cursor.execute("SELECT * FROM people WHERE id = ?", (pid,))
        row = cursor.fetchone()
        if not row:
            st.warning(f"⚠️ Person not found: {pid}")
            return None
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))

    visited = set()
    nodes = {}
    queue = deque([normalize_id(root_id)])

    while queue:
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

        spouse_ids = [normalize_id(sid) for sid in str(data.get("spouse_id", "")).split(";") if sid.strip()]
        children_ids = [normalize_id(cid) for cid in str(data.get("children_ids", "")).split(";") if cid.strip()]

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
                couple_node = {
                    "id": f"{person['id']}_couple",
                    "type": "couple",
                    "husband": person if data.get("gender") == "M" else spouse,
                    "wife": spouse if data.get("gender") == "M" else person,
                    "children": []
                }
                for cid in children_ids:
                    if cid not in visited:
                        queue.append(cid)
                    child_data = fetch_person_record(cid)
                    if child_data:
                        child_node = {
                            "id": normalize_id(child_data["id"]),
                            "name": child_data["name"],
                            "dob": child_data["dob"],
                            "valavu": child_data["valavu"],
                            "is_alive": child_data["alive"] == "Yes",
                            "url": f"https://abc.com?id={normalize_id(child_data['id'])}"
                        }
                        st.write(f"👶 Adding child {child_node['name']} to couple {couple_node['id']}")
                        couple_node["children"].append(child_node)
                st.write(f"🧩 Node created: {couple_node['id']}")
                nodes[couple_node["id"]] = couple_node
                continue  # skip adding person directly if they form a couple

        for cid in children_ids:
            if cid not in visited:
                queue.append(cid)
        if children_ids:
            person["children"] = []
            for cid in children_ids:
                child_data = fetch_person_record(cid)
                if child_data:
                    child_node = {
                        "id": normalize_id(child_data["id"]),
                        "name": child_data["name"],
                        "dob": child_data["dob"],
                        "valavu": child_data["valavu"],
                        "is_alive": child_data["alive"] == "Yes",
                        "url": f"https://abc.com?id={normalize_id(child_data['id'])}"
                    }
                    st.write(f"👶 Adding child {child_node['name']} to {person['id']}")
                    person["children"].append(child_node)
        st.write(f"🧩 Node created: {person['id']} ({person['name']})")
        nodes[person["id"]] = person

    conn.close()
    return nodes.get(root_id) or list(nodes.values())[0]
