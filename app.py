import streamlit as st
import sqlite3
import json
from collections import deque

st.set_page_config(layout="wide")
st.title("Interactive Family Tree")

params = st.query_params
query_id = params.get("id", ["1"])
if isinstance(query_id, list):
    query_id = query_id[0]
query_id = str(query_id).strip()
st.write(f"📌 Selected Root ID: {query_id}")

def load_family_tree_from_db(root_id):
    conn = sqlite3.connect("family_tree.db")
    cursor = conn.cursor()

    def normalize_id(val):
        try:
            return str(int(float(val)))
        except:
            return str(val).strip()

    def fetch(pid):
        cursor.execute("SELECT * FROM people WHERE id = ?", (pid,))
        row = cursor.fetchone()
        if not row:
            return None
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))

    visited, queue = set(), deque([normalize_id(root_id)])
    nodes, couple_links = {}, {}

    while queue:
        pid = normalize_id(queue.popleft())
        if pid in visited:
            continue
        data = fetch(pid)
        if not data:
            continue

        spouse_ids = [normalize_id(s) for s in str(data.get("spouse_id", "")).split(";") if s and s.lower() != "nan"]
        child_ids = [normalize_id(c) for c in str(data.get("children_ids", "")).split(";") if c and c.lower() != "nan"]

        def person_dict(d):
            return {
                "id": normalize_id(d["id"]),
                "name": d["name"],
                "dob": d["dob"],
                "valavu": d["valavu"],
                "is_alive": d["alive"] == "Yes",
                "url": f"https://500-family-tree4.streamlit.app/?id={normalize_id(d['id'])}",
                "gender": d.get("gender", "")
            }

        if spouse_ids:
            spouse = fetch(spouse_ids[0])
            if not spouse:
                continue
            husband = person_dict(data)
            wife = person_dict(spouse)
            couple_id = f"{husband['id']}_couple"
            couple = {
                "id": couple_id,
                "type": "couple",
                "husband": husband,
                "wife": wife,
                "children": [{"id": c} for c in child_ids]
            }
            nodes[couple_id] = couple
            couple_links[husband["id"]] = couple_id
            couple_links[wife["id"]] = couple_id
            visited.update([husband["id"], wife["id"]])
            for cid in child_ids:
                if cid not in visited:
                    queue.append(cid)
        else:
            person = person_dict(data)
            nodes[person["id"]] = person
            visited.add(person["id"])

        father = normalize_id(data.get("father_id", ""))
        mother = normalize_id(data.get("mother_id", ""))
        if father and father.lower() != "nan" and father not in visited:
            pf = fetch(father)
            pm = fetch(mother) if mother else {}
            if pf:
                fdict = person_dict(pf)
                mdict = person_dict(pm) if pm else {"id": mother, "name": "", "url": "", "dob": "", "valavu": "", "is_alive": False, "gender": "F"}
                couple_id = f"{father}_couple"
                ref_id = couple_links.get(pid, pid)
                couple = {
                    "id": couple_id,
                    "type": "couple",
                    "husband": fdict,
                    "wife": mdict,
                    "children": [nodes.get(ref_id)] if ref_id in nodes else []
                }
                nodes[couple_id] = couple
                couple_links[father] = couple_id
                couple_links[mother] = couple_id
                queue.append(father)

    for node in nodes.values():
        if node.get("type") == "couple":
            resolved = []
            for c in node.get("children", []):
                ref = couple_links.get(c["id"], c["id"])
                if ref in nodes:
                    resolved.append(nodes[ref])
            node["children"] = resolved

    root_key = couple_links.get(root_id, root_id)
    root = nodes.get(root_key)
    while True:
        parent = None
        for n in nodes.values():
            if n.get("type") == "couple":
                if any(child.get("id") == root_key for child in n.get("children", [])):
                    root_key = n["id"]
                    parent = n
                    break
        if not parent:
            break
    def build(node, seen):
        if not node or node["id"] in seen:
            return None
        seen.add(node["id"])
        children = []
        for c in node.get("children", []):
            sub = build(c, seen)
            if sub: children.append(sub)
        node_copy = dict(node)
        node_copy["name"] = node.get("name", f"{node.get('husband', {}).get('name', '')} + {node.get('wife', {}).get('name', '')}")
        if children: node_copy["children"] = children
        return node_copy

    return build(nodes.get(root_key), set())

tree_data = load_family_tree_from_db(query_id)

if tree_data:
    with open("public/tree.html") as f:
        html = f.read().replace("__TREE_DATA__", json.dumps(json.dumps(tree_data)))
    st.components.v1.html(html, height=800, scrolling=True)
else:
    st.warning("⚠️ No data available.")
