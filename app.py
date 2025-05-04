import streamlit as st
import sqlite3
import json
from collections import deque

# Debug toggle
DEBUG = False

MAX_NODES = 50

def load_family_tree_from_db(root_id="1"):
    if DEBUG: st.write("\U0001F4E5 Starting family tree loading...")
    conn = sqlite3.connect("family_tree.db")
    cursor = conn.cursor()

    def normalize_id(raw_id):
        try:
            return str(int(float(raw_id)))
        except:
            return str(raw_id).strip()

    def fetch_person_record(pid):
        if DEBUG: st.write(f"\U0001F50E Querying DB for person: {pid}")
        cursor.execute("SELECT * FROM people WHERE id = ?", (pid,))
        row = cursor.fetchone()
        if not row:
            if DEBUG: st.warning(f"⚠️ Person not found: {pid}")
            return None
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))

    visited = set()
    queue = deque()
    nodes = {}
    couple_links = {}

    root_id = normalize_id(root_id)
    queue.append(root_id)

    while queue:
        if len(nodes) >= MAX_NODES:
            if DEBUG: st.warning(f"🚨 Node limit of {MAX_NODES} reached. Stopping further expansion.")
            break

        if DEBUG: st.write(f"\U0001F4EC Queue: {[x for x in queue]}")
        pid = normalize_id(queue.popleft())

        if pid in visited:
            if DEBUG: st.write(f"\U0001F501 Skipping already visited person: {pid}")
            continue

        data = fetch_person_record(pid)
        if not data:
            continue

        spouse_ids = [normalize_id(sid) for sid in str(data.get("spouse_id", "")).split(";") if sid.strip() and sid.lower() != "nan"]
        children_ids = [normalize_id(cid) for cid in str(data.get("children_ids", "")).split(";") if cid.strip() and cid.lower() != "nan"]

        if spouse_ids:
            spouse_id = spouse_ids[0]
            spouse_data = fetch_person_record(spouse_id)
            if not spouse_data:
                continue

            husband = {
                "id": normalize_id(data["id"]),
                "name": data["name"],
                "dob": data["dob"],
                "valavu": data["valavu"],
                "is_alive": data["alive"] == "Yes",
                "url": f"https://500-family-tree4.streamlit.app/?id={normalize_id(data['id'])}",
                "gender": data.get("gender", "M")
            }

            wife = {
                "id": normalize_id(spouse_data["id"]),
                "name": spouse_data["name"],
                "dob": spouse_data["dob"],
                "valavu": spouse_data["valavu"],
                "is_alive": spouse_data["alive"] == "Yes",
                "url": f"https://500-family-tree4.streamlit.app/?id={normalize_id(spouse_data['id'])}",
                "gender": spouse_data.get("gender", "F")
            }

            if DEBUG: st.write(f"\U0001F48D Creating couple node for: {husband['name']} and {wife['name']}")
            couple_node_id = f"{husband['id']}_couple"
            couple_node = {
                "id": couple_node_id,
                "type": "couple",
                "husband": husband,
                "wife": wife,
                "children": []
            }
            nodes[couple_node_id] = couple_node
            couple_links[husband["id"]] = couple_node_id
            couple_links[wife["id"]] = couple_node_id

            visited.add(husband["id"])
            visited.add(wife["id"])

            for child_id in children_ids:
                if child_id not in visited and child_id not in queue:
                    queue.append(child_id)
                couple_node["children"].append({"id": child_id})

        else:
            if DEBUG: st.write(f"\U0001F464 Creating individual node for: {data['name']}")
            person_node = {
                "id": normalize_id(data["id"]),
                "name": data["name"],
                "dob": data["dob"],
                "valavu": data["valavu"],
                "is_alive": data["alive"] == "Yes",
                "gender": data.get("gender", ""),
                "url": f"https://500-family-tree4.streamlit.app/?id={normalize_id(data['id'])}"
            }
            visited.add(person_node["id"])
            nodes[person_node["id"]] = person_node

        father_id = normalize_id(data.get("father_id", ""))
        mother_id = normalize_id(data.get("mother_id", ""))
        if father_id and father_id not in visited and father_id not in queue:
            if DEBUG: st.write(f"\U0001F468‍\U0001F469‍\U0001F467 Creating parent couple for: {father_id} and {mother_id}")
            parent_data = fetch_person_record(father_id)
            mother_data = fetch_person_record(mother_id) if mother_id else None
            if parent_data:
                father = {
                    "id": father_id,
                    "name": parent_data["name"],
                    "dob": parent_data["dob"],
                    "valavu": parent_data["valavu"],
                    "is_alive": parent_data["alive"] == "Yes",
                    "url": f"https://500-family-tree4.streamlit.app/?id={father_id}",
                    "gender": parent_data.get("gender", "M")
                }
                mother = {
                    "id": mother_id,
                    "name": mother_data["name"] if mother_data else "",
                    "dob": mother_data["dob"] if mother_data else "",
                    "valavu": mother_data["valavu"] if mother_data else "",
                    "is_alive": mother_data["alive"] == "Yes" if mother_data else False,
                    "url": f"https://500-family-tree4.streamlit.app/?id={mother_id}" if mother_data else "",
                    "gender": mother_data.get("gender", "F") if mother_data else "F"
                }
                parent_couple_id = f"{father_id}_couple"
                child_ref_id = couple_links.get(pid, pid)
                child_node = nodes.get(child_ref_id)
                parent_couple = {
                    "id": parent_couple_id,
                    "type": "couple",
                    "husband": father,
                    "wife": mother,
                    "children": [child_node] if child_node else []
                }
                if DEBUG: st.write(f"\U0001F9E9 Created parent couple node: {parent_couple_id}")
                nodes[parent_couple_id] = parent_couple
                couple_links[father_id] = parent_couple_id
                couple_links[mother_id] = parent_couple_id
                queue.append(father_id)

    for node in nodes.values():
        if node.get("type") == "couple":
            resolved_children = []
            for child_stub in node.get("children", []):
                cid = child_stub.get("id")
                full = nodes.get(couple_links.get(cid, cid))
                if full:
                    if DEBUG: st.write(f"✅ Resolved child ID {cid} → {full.get('id', 'unknown')}")
                    resolved_children.append(full)
                else:
                    if DEBUG: st.warning(f"⚠️ Child ID {cid} could not be resolved")
            node["children"] = resolved_children

    if DEBUG: st.write(f"✅ Total nodes created: {len(nodes)}")
    conn.close()

    tree_root_id = couple_links.get(root_id, root_id)
    current_root_id = tree_root_id
    while True:
        parent_found = False
        for node in nodes.values():
            if node.get("type") == "couple":
                for child in node.get("children", []):
                    if child.get("id") == current_root_id:
                        current_root_id = node["id"]
                        parent_found = True
                        break
            if parent_found:
                break
        if not parent_found:
            break

    tree_root = nodes.get(current_root_id)
    if DEBUG: st.write(f"\U0001F53C Re-rooting to ancestor couple: {current_root_id}")

    def build_subtree(node, seen):
        if not node or node.get("id") in seen:
            return None
        seen.add(node["id"])
        if DEBUG: st.write(f"🌳 Rendering node: {node.get('name', node.get('id'))}")
        children = []
        for child in node.get("children", []):
            child_subtree = build_subtree(child, seen)
            if child_subtree:
                children.append(child_subtree)
        new_node = dict(node)
        new_node["children"] = children
        return new_node

    return build_subtree(tree_root, set())

# Streamlit Setup
st.set_page_config(layout="wide")
st.title("Interactive Family Tree")

params = st.query_params
query_id = params.get("id", ["1"])
if isinstance(query_id, list):
    query_id = query_id[0]
query_id = str(query_id).strip()
st.write(f"📌 Selected Root ID: {query_id}")

tree_data = load_family_tree_from_db(query_id)

if tree_data:
    with open("public/tree.html", "r") as f:
        html = f.read().replace("__TREE_DATA__", json.dumps(tree_data))
    st.components.v1.html(html, height=1000, scrolling=True)
else:
    st.warning("⚠️ No data found or failed to generate tree.")
