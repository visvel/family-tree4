import streamlit as st
import sqlite3
import json
from collections import deque

DEBUG = True  # Set to False to disable debug logs

def debug_log(msg):
    if DEBUG:
        st.write(msg)

def normalize_id(raw_id):
    try:
        return str(int(float(raw_id)))
    except:
        return str(raw_id).strip()

def fetch_person_record(cursor, pid):
    debug_log(f"🔎 Querying DB for person: {pid}")
    cursor.execute("SELECT * FROM people WHERE id = ?", (pid,))
    row = cursor.fetchone()
    if not row:
        debug_log(f"⚠️ Person not found: {pid}")
        return None
    columns = [desc[0] for desc in cursor.description]
    return dict(zip(columns, row))

def load_family_tree_from_db(root_id="1"):
    debug_log("📥 Starting family tree loading...")
    conn = sqlite3.connect("family_tree.db")
    cursor = conn.cursor()

    visited = set()
    queue = deque()
    nodes = {}
    couple_links = {}

    root_id = normalize_id(root_id)
    queue.append(root_id)

    while queue:
        debug_log(f"📬 Queue: {[x for x in queue]}")
        pid = normalize_id(queue.popleft())
        if pid in visited:
            debug_log(f"🔁 Skipping already visited person: {pid} to avoid cycles")
            continue

        data = fetch_person_record(cursor, pid)
        if not data:
            continue

        spouse_ids = [normalize_id(sid) for sid in str(data.get("spouse_id", "")).split(";") if sid.strip() and sid.lower() != "nan"]
        children_ids = [normalize_id(cid) for cid in str(data.get("children_ids", "")).split(";") if cid.strip() and cid.lower() != "nan"]

        if spouse_ids:
            spouse_id = spouse_ids[0]
            spouse_data = fetch_person_record(cursor, spouse_id)
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

            debug_log(f"💍 Creating couple node for: {husband['name']} and {wife['name']}")
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
            debug_log(f"👤 Creating individual node for: {data['name']}")
            person_node = {
                "id": normalize_id(data["id"]),
                "name": data["name"],
                "dob": data["dob"],
                "valavu": data["valavu"],
                "is_alive": data["alive"] == "Yes",
                "url": f"https://500-family-tree4.streamlit.app/?id={normalize_id(data['id'])}",
                "gender": data.get("gender", "")
            }
            visited.add(person_node["id"])
            nodes[person_node["id"]] = person_node

        # Process parents
        father_id = normalize_id(data.get("father_id", ""))
        mother_id = normalize_id(data.get("mother_id", ""))
        if father_id and father_id.lower() != "nan" and father_id not in visited:
            debug_log(f"👨‍👩‍👧 Creating parent couple for: {father_id} and {mother_id}")
            parent_data = fetch_person_record(cursor, father_id)
            mother_data = fetch_person_record(cursor, mother_id) if mother_id else None
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
                debug_log(f"🧩 Created parent couple node: {parent_couple_id}")
                nodes[parent_couple_id] = parent_couple
                couple_links[father_id] = parent_couple_id
                couple_links[mother_id] = parent_couple_id
                queue.append(father_id)

    # Resolve children links
    for node in nodes.values():
        if node.get("type") == "couple":
            resolved_children = []
            for child_stub in node.get("children", []):
                cid = child_stub.get("id")
                full = nodes.get(couple_links.get(cid, cid))
                if full:
                    debug_log(f"✅ Resolved child ID {cid} → {full.get('id', 'unknown')}")
                    resolved_children.append(full)
                else:
                    debug_log(f"⚠️ Child ID {cid} could not be resolved in nodes")
            node["children"] = resolved_children

    debug_log(f"✅ Total nodes created: {len(nodes)}")
    conn.close()

    # Re-root to highest ancestor
    root_key = couple_links.get(root_id, root_id)
    current_root_id = root_key
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

    debug_log(f"🔼 Re-rooting to ancestor couple: {current_root_id}")
    return build_subtree(nodes.get(current_root_id), set())

def build_subtree(node, seen):
    if not node or node.get("id") in seen:
        return None
    seen.add(node["id"])
    debug_log(f"🌳 Rendering node: {node.get('name', node.get('id'))}")
    children = []
    for child in node.get("children", []):
        subtree = build_subtree(child, seen)
        if subtree:
            children.append(subtree)
    new_node = dict(node)
    if node.get("type") == "couple":
        new_node["name"] = f"{node['husband']['name']} + {node['wife']['name']}"
    else:
        new_node["name"] = node.get("name", node.get("id"))
    if children:
        new_node["children"] = children
    return new_node

# Streamlit UI
st.set_page_config(layout="wide")
st.title("Interactive Family Tree")

params = st.query_params
query_id = str(params.get("id", ["1"])[0]).strip()
st.write(f"📌 Selected Root ID: {query_id}")

tree_data = load_family_tree_from_db(query_id)

if tree_data:
    with open("public/tree.html", "r") as f:
        html = f.read().replace("__TREE_DATA__", json.dumps(tree_data))
    st.components.v1.html(html, height=800, scrolling=True)
else:
    st.warning("⚠️ No data found or failed to generate tree.")
