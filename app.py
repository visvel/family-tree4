# app.py

import streamlit as st
import sqlite3
import json
from collections import deque

DEBUG_MODE = False  # Toggle for logs

# Load family tree from SQLite DB
def load_family_tree_from_db(root_id="1"):
    if DEBUG_MODE: st.write("📥 Starting family tree loading...")
    conn = sqlite3.connect("family_tree.db")
    cursor = conn.cursor()

    def normalize_id(raw_id):
        try:
            return str(int(float(raw_id)))
        except:
            return str(raw_id).strip()

    def fetch_person(pid):
        pid = normalize_id(pid)
        if DEBUG_MODE: st.write(f"🔎 Querying DB for person: {pid}")
        cursor.execute("SELECT * FROM people WHERE id = ?", (pid,))
        row = cursor.fetchone()
        if not row:
            if DEBUG_MODE: st.warning(f"⚠️ Person not found: {pid}")
            return None
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))

    queue = deque()
    visited = set()
    nodes = {}
    couple_links = {}

    root_id = normalize_id(root_id)
    queue.append(root_id)

    while queue:
        pid = normalize_id(queue.popleft())
        if DEBUG_MODE: st.write(f"📬 Queue: {[pid]}")

        if pid in visited:
            continue
        visited.add(pid)

        person = fetch_person(pid)
        if not person:
            continue

        spouse_ids = [normalize_id(sid) for sid in str(person.get("spouse_id", "")).split(";") if sid.strip() and sid.lower() != "nan"]
        children_ids = [normalize_id(cid) for cid in str(person.get("children_ids", "")).split(";") if cid.strip() and cid.lower() != "nan"]

        if spouse_ids:
            spouse_id = spouse_ids[0]
            spouse = fetch_person(spouse_id)
            if not spouse:
                continue

            husband, wife = (person, spouse) if person.get("gender", "M") == "M" else (spouse, person)
            couple_id = f"{normalize_id(husband['id'])}_couple"

            if DEBUG_MODE: st.write(f"💍 Creating couple node for: {husband['name']} and {wife['name']}")

            couple_node = {
                "id": couple_id,
                "type": "couple",
                "husband": {
                    "id": normalize_id(husband["id"]),
                    "name": husband["name"],
                    "dob": husband["dob"],
                    "valavu": husband["valavu"],
                    "is_alive": husband["alive"] == "Yes",
                    "gender": husband.get("gender", "M"),
                    "url": f"https://500-family-tree4.streamlit.app/?id={normalize_id(husband['id'])}"
                },
                "wife": {
                    "id": normalize_id(wife["id"]),
                    "name": wife["name"],
                    "dob": wife["dob"],
                    "valavu": wife["valavu"],
                    "is_alive": wife["alive"] == "Yes",
                    "gender": wife.get("gender", "F"),
                    "url": f"https://500-family-tree4.streamlit.app/?id={normalize_id(wife['id'])}"
                },
                "children": [{"id": cid} for cid in children_ids]
            }

            nodes[couple_id] = couple_node
            couple_links[normalize_id(husband["id"])] = couple_id
            couple_links[normalize_id(wife["id"])] = couple_id

            for cid in children_ids:
                if cid not in visited:
                    queue.append(cid)

        else:
            if DEBUG_MODE: st.write(f"👤 Creating individual node for: {person['name']}")
            node_id = normalize_id(person["id"])
            nodes[node_id] = {
                "id": node_id,
                "name": person["name"],
                "dob": person["dob"],
                "valavu": person["valavu"],
                "is_alive": person["alive"] == "Yes",
                "gender": person.get("gender", ""),
                "url": f"https://500-family-tree4.streamlit.app/?id={node_id}"
            }

        father_id = normalize_id(person.get("father_id", ""))
        mother_id = normalize_id(person.get("mother_id", ""))
        if father_id and father_id not in visited:
            father = fetch_person(father_id)
            mother = fetch_person(mother_id) if mother_id else None
            if father:
                if DEBUG_MODE: st.write(f"👨‍👩‍👧 Creating parent couple for: {father_id} and {mother_id}")
                parent_couple_id = f"{father_id}_couple"
                child_ref = couple_links.get(pid, pid)
                child_node = nodes.get(child_ref)
                parent_couple = {
                    "id": parent_couple_id,
                    "type": "couple",
                    "husband": {
                        "id": father_id,
                        "name": father["name"],
                        "dob": father["dob"],
                        "valavu": father["valavu"],
                        "is_alive": father["alive"] == "Yes",
                        "gender": father.get("gender", "M"),
                        "url": f"https://500-family-tree4.streamlit.app/?id={father_id}"
                    },
                    "wife": {
                        "id": mother_id,
                        "name": mother["name"] if mother else "",
                        "dob": mother["dob"] if mother else "",
                        "valavu": mother["valavu"] if mother else "",
                        "is_alive": mother["alive"] == "Yes" if mother else False,
                        "gender": mother.get("gender", "F") if mother else "F",
                        "url": f"https://500-family-tree4.streamlit.app/?id={mother_id}" if mother else ""
                    },
                    "children": [child_node] if child_node else []
                }
                if DEBUG_MODE: st.write(f"🧩 Created parent couple node: {parent_couple_id}")
                nodes[parent_couple_id] = parent_couple
                couple_links[father_id] = parent_couple_id
                couple_links[mother_id] = parent_couple_id
                queue.append(father_id)

    # Resolve children references
    for node in nodes.values():
        if node.get("type") == "couple":
            resolved = []
            for c in node.get("children", []):
                resolved_child = nodes.get(couple_links.get(c["id"], c["id"]))
                if resolved_child:
                    if DEBUG_MODE: st.write(f"✅ Resolved child ID {c['id']} → {resolved_child['id']}")
                    resolved.append(resolved_child)
            node["children"] = resolved

    conn.close()
    if DEBUG_MODE: st.write(f"✅ Total nodes created: {len(nodes)}")

    root_node_id = couple_links.get(root_id, root_id)
    current = root_node_id
    while True:
        parent = None
        for node in nodes.values():
            for c in node.get("children", []):
                if c.get("id") == current:
                    current = node["id"]
                    parent = current
                    break
            if parent:
                break
        if not parent:
            break
    root_node_id = current
    tree_root = nodes.get(root_node_id)
    if DEBUG_MODE: st.write(f"🔼 Re-rooting to ancestor couple: {root_node_id}")

    def build_tree(node, seen):
        if not node or node["id"] in seen:
            return None
        seen.add(node["id"])
        children = []
        for c in node.get("children", []):
            subtree = build_tree(c, seen)
            if subtree:
                children.append(subtree)
        result = dict(node)
        result["children"] = children
        return result

    return build_tree(tree_root, set())

# Streamlit app logic
st.set_page_config(layout="wide")
st.title("Interactive Family Tree")

params = st.query_params
query_id = params.get("id", ["1"])
if isinstance(query_id, list): query_id = query_id[0]
query_id = str(query_id).strip()

st.write(f"📌 Selected Root ID: {query_id}")
tree_data = load_family_tree_from_db(query_id)

if tree_data:
    with open("public/tree.html", "r") as f:
        html = f.read().replace("__TREE_DATA__", json.dumps(tree_data)).replace("__QUERY_ID__", json.dumps(query_id))
    st.components.v1.html(html, height=1000, scrolling=True)
else:
    st.warning("⚠️ No tree found for given ID.")
