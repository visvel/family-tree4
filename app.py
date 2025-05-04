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
    queue = deque()
    nodes = {}
    couple_links = {}

    root_id = normalize_id(root_id)
    queue.append(root_id)

    while queue:
        st.write(f"📬 Queue: {[x for x in queue]}")
        pid = queue.popleft()
        pid = normalize_id(pid)

        if pid in visited:
            st.write(f"🔁 Skipping already visited person: {pid} to avoid cycles")
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
                "url": f"https://abc.com?id={normalize_id(data['id'])}",
                "gender": data.get("gender", "M")
            }

            wife = {
                "id": normalize_id(spouse_data["id"]),
                "name": spouse_data["name"],
                "dob": spouse_data["dob"],
                "valavu": spouse_data["valavu"],
                "is_alive": spouse_data["alive"] == "Yes",
                "url": f"https://abc.com?id={normalize_id(spouse_data['id'])}",
                "gender": spouse_data.get("gender", "F")
            }

            st.write(f"💍 Creating couple node for: {husband['name']} and {wife['name']}")
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
            st.write(f"👤 Creating individual node for: {data['name']}")
            person_node = {
                "id": normalize_id(data["id"]),
                "name": data["name"],
                "dob": data["dob"],
                "valavu": data["valavu"],
                "is_alive": data["alive"] == "Yes",
                "url": f"https://abc.com?id={normalize_id(data['id'])}"
            }
            visited.add(person_node["id"])
            nodes[person_node["id"]] = person_node

        # Parents
        father_id = normalize_id(data.get("father_id", ""))
        mother_id = normalize_id(data.get("mother_id", ""))
        if father_id and father_id not in visited and father_id not in queue:
            st.write(f"👨‍👩‍👧 Creating parent couple for: {father_id} and {mother_id}")
            parent_data = fetch_person_record(father_id)
            mother_data = fetch_person_record(mother_id) if mother_id else None
            if parent_data:
                father = {
                    "id": father_id,
                    "name": parent_data["name"],
                    "dob": parent_data["dob"],
                    "valavu": parent_data["valavu"],
                    "is_alive": parent_data["alive"] == "Yes",
                    "url": f"https://abc.com?id={father_id}",
                    "gender": parent_data.get("gender", "M")
                }
                mother = {
                    "id": mother_id,
                    "name": mother_data["name"] if mother_data else "",
                    "dob": mother_data["dob"] if mother_data else "",
                    "valavu": mother_data["valavu"] if mother_data else "",
                    "is_alive": mother_data["alive"] == "Yes" if mother_data else False,
                    "url": f"https://abc.com?id={mother_id}" if mother_data else "",
                    "gender": mother_data.get("gender", "F") if mother_data else "F"
                }
                parent_couple_id = f"{father_id}_couple"
                parent_couple = {
                    "id": parent_couple_id,
                    "type": "couple",
                    "husband": father,
                    "wife": mother,
                    "children": [nodes.get(couple_links.get(pid, pid)) for pid in [pid] if pid in visited]
                }
                st.write(f"🧩 Created parent couple node: {parent_couple_id}")
                nodes[parent_couple_id] = parent_couple
                couple_links[father_id] = parent_couple_id
                couple_links[mother_id] = parent_couple_id
                queue.append(father_id)

    # ✅ Final pass: resolve full child nodes
    for node in nodes.values():
        if node.get("type") == "couple":
            resolved_children = []
            for child_stub in node.get("children", []):
                cid = child_stub.get("id")
                full = nodes.get(couple_links.get(cid, cid))
                if full:
                    st.write(f"✅ Resolved child ID {cid} → {full.get('id', 'unknown')}")
                    resolved_children.append(full)
                else:
                    st.warning(f"⚠️ Child ID {cid} could not be resolved in nodes")
            node["children"] = resolved_children

    st.write(f"✅ Total nodes created: {len(nodes)}")
    conn.close()

    root_key = couple_links.get(root_id, root_id)
    tree_root_id = couple_links.get(root_id, root_id)
    tree_root = nodes.get(tree_root_id)

    # 🔄 Patch: If the root node is actually a child in another couple node, walk up to that parent
    for node in nodes.values():
        if node.get("type") == "couple" and any(child.get("id") == tree_root_id for child in node.get("children", [])):
            st.write(f"🔼 Re-rooting to ancestor couple: {node['id']}")
            tree_root = node
            break

    # Filter to only include nodes directly reachable from the root
    def build_subtree(node, seen):
        if not node or node.get("id") in seen:
            return None
        seen.add(node["id"])
        st.write(f"🌳 Rendering node: {node.get('name', node.get('id'))}")
        children = []
        for child in node.get("children", []):
            child_subtree = build_subtree(child, seen)
            if child_subtree:
                children.append(child_subtree)
        new_node = dict(node)
        if node.get("type") == "couple":
            husband_name = node.get("husband", {}).get("name", "")
            wife_name = node.get("wife", {}).get("name", "")
            new_node["name"] = f"{husband_name} + {wife_name}"
        else:
            new_node["name"] = node.get("name", node.get("id"))
        if children:
            new_node["children"] = children
        return new_node

    tree = build_subtree(tree_root, set())
    return tree

# Inject HTML from external file
def get_html():
    with open("public/tree.html") as f:
        return f.read()

# Streamlit app
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
    st.components.v1.html(html, height=700, scrolling=True)
else:
    st.warning("⚠️ No data found or failed to generate tree.")
