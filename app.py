import streamlit as st
import sqlite3
import json
from collections import deque

DEBUG_MODE = False

def normalize_id(raw_id):
    try:
        return str(int(float(raw_id)))
    except:
        return str(raw_id).strip()

def fetch_person(cursor, pid):
    if DEBUG_MODE:
        st.write(f"🔎 Querying DB for person: {pid}")
    cursor.execute("SELECT * FROM people WHERE id = ?", (pid,))
    row = cursor.fetchone()
    if not row:
        if DEBUG_MODE:
            st.warning(f"⚠️ Person not found: {pid}")
        return None
    columns = [desc[0] for desc in cursor.description]
    return dict(zip(columns, row))

def load_family_tree_from_db(root_id):
    conn = sqlite3.connect("family_tree.db")
    cursor = conn.cursor()

    visited = set()
    queue = deque()
    nodes = {}
    couple_links = {}

    root_id = normalize_id(root_id)
    queue.append(root_id)

    while queue:
        pid = normalize_id(queue.popleft())
        if pid in visited:
            continue

        data = fetch_person(cursor, pid)
        if not data:
            continue

        spouse_ids = [normalize_id(sid) for sid in str(data.get("spouse_id", "")).split(";") if sid.strip() and sid.lower() != "nan"]
        children_ids = [normalize_id(cid) for cid in str(data.get("children_ids", "")).split(";") if cid.strip() and cid.lower() != "nan"]

        if spouse_ids:
            spouse_id = spouse_ids[0]
            spouse_data = fetch_person(cursor, spouse_id)
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

            if DEBUG_MODE:
                st.write(f"💍 Creating couple node for: {husband['name']} and {wife['name']}")

            cid = f"{husband['id']}_couple"
            couple_node = {
                "id": cid,
                "type": "couple",
                "husband": husband,
                "wife": wife,
                "children": [{"id": c} for c in children_ids]
            }
            nodes[cid] = couple_node
            couple_links[husband["id"]] = cid
            couple_links[wife["id"]] = cid
            visited.update([husband["id"], wife["id"]])

            for child_id in children_ids:
                if child_id not in visited and child_id not in queue:
                    queue.append(child_id)
        else:
            person_node = {
                "id": normalize_id(data["id"]),
                "name": data["name"],
                "dob": data["dob"],
                "valavu": data["valavu"],
                "is_alive": data["alive"] == "Yes",
                "url": f"https://500-family-tree4.streamlit.app/?id={normalize_id(data['id'])}",
                "gender": data.get("gender", "")
            }
            nodes[person_node["id"]] = person_node
            visited.add(person_node["id"])

        # parents
        father_id = normalize_id(data.get("father_id", ""))
        mother_id = normalize_id(data.get("mother_id", ""))
        if father_id and father_id not in visited and father_id not in queue:
            father_data = fetch_person(cursor, father_id)
            mother_data = fetch_person(cursor, mother_id) if mother_id else None
            if father_data:
                father = {
                    "id": father_id,
                    "name": father_data["name"],
                    "dob": father_data["dob"],
                    "valavu": father_data["valavu"],
                    "is_alive": father_data["alive"] == "Yes",
                    "url": f"https://500-family-tree4.streamlit.app/?id={father_id}",
                    "gender": father_data.get("gender", "M")
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

                child_ref = couple_links.get(pid, pid)
                child_node = nodes.get(child_ref)
                couple_id = f"{father_id}_couple"
                parent_couple = {
                    "id": couple_id,
                    "type": "couple",
                    "husband": father,
                    "wife": mother,
                    "children": [child_node] if child_node else []
                }
                nodes[couple_id] = parent_couple
                couple_links[father_id] = couple_id
                couple_links[mother_id] = couple_id
                queue.append(father_id)

    for node in nodes.values():
        if node.get("type") == "couple":
            resolved_children = []
            for stub in node.get("children", []):
                cid = stub.get("id")
                full = nodes.get(couple_links.get(cid, cid))
                if full:
                    resolved_children.append(full)
            node["children"] = resolved_children

    root_ref = couple_links.get(root_id, root_id)
    current_root = root_ref
    while True:
        parent = None
        for n in nodes.values():
            if n.get("type") == "couple":
                for c in n.get("children", []):
                    if c.get("id") == current_root:
                        current_root = n["id"]
                        parent = n
                        break
            if parent:
                break
        if not parent:
            break
    root = nodes.get(current_root)
    def build(node, seen):
        if not node or node["id"] in seen:
            return None
        seen.add(node["id"])
        children = []
        for c in node.get("children", []):
            child = build(c, seen)
            if child:
                children.append(child)
        out = dict(node)
        out["children"] = children
        return out

    return build(root, set())

# --- Streamlit Frontend ---
st.set_page_config(layout="wide")
st.title("Interactive Family Tree")

query_id = st.query_params.get("id", "1")
if isinstance(query_id, list):
    query_id = query_id[0]
query_id = str(query_id).strip()
st.write(f"📌 Selected Root ID: {query_id}")

tree_data = load_family_tree_from_db(query_id)

if tree_data:
    with open("public/tree.html", "r") as f:
        raw_html = f.read()
        html_filled = raw_html.replace("__TREE_DATA__", json.dumps(json.dumps(tree_data)))
    st.components.v1.html(html_filled, height=800, scrolling=True)
else:
    st.warning("⚠️ Tree data could not be generated.")
