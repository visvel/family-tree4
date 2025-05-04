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
        st.write(f"🧩 Node created: {person['name']}")
        nodes[person["id"]] = person

    conn.close()
    return nodes.get(root_id) or list(nodes.values())[0]

# HTML + JS for D3 Tree Rendering
def get_d3_tree_html(tree_data):
    return f"""
    <div id='tree'></div>
    <style>
        .node rect {{ stroke: #333; stroke-width: 1.5px; }}
        .node text {{ font: 12px sans-serif; pointer-events: none; }}
        .link {{ fill: none; stroke: #ccc; stroke-width: 1.5px; }}
    </style>
    <script src=\"https://d3js.org/d3.v7.min.js\"></script>
    <script>
        const treeData = JSON.parse(`{json.dumps(tree_data)}`);
        console.log("📦 Rendering treeData:", treeData);

        const width = 1000, height = 600;
        const svg = d3.select("#tree")
            .append("svg")
            .attr("width", width)
            .attr("height", height)
            .append("g")
            .attr("transform", "translate(50,50)");

        const treeLayout = d3.tree().size([width - 100, height - 100]);
        const root = d3.hierarchy(treeData, function(d) {{ return d.children; }});
        treeLayout(root);

        svg.selectAll('path.link')
            .data(root.links())
            .enter()
            .append('path')
            .attr('class', 'link')
            .attr('d', d3.linkVertical()
                .x(function(d) {{ return d.x; }})
                .y(function(d) {{ return d.y; }}));

        const node = svg.selectAll('g.node')
            .data(root.descendants())
            .enter()
            .append('g')
            .attr('class', 'node')
            .attr('transform', function(d) {{ return 'translate(' + d.x + ',' + d.y + ')'; }});

        node.each(function(d) {{
            const g = d3.select(this);
            if (d.data.type === 'couple') {{
                console.log("👫 Rendering couple:", d.data.husband.name, "+", d.data.wife.name);
                g.append('rect')
                    .attr('x', -70).attr('y', -50).attr('width', 140).attr('height', 30)
                    .style('fill', '#d0e1f9');
                g.append('text')
                    .attr('x', 0).attr('y', -30)
                    .attr('text-anchor', 'middle')
                    .text(d.data.husband.name);

                g.append('rect')
                    .attr('x', -70).attr('y', -20).attr('width', 140).attr('height', 30)
                    .style('fill', '#f9d0f0');
                g.append('text')
                    .attr('x', 0).attr('y', 0)
                    .attr('text-anchor', 'middle')
                    .text(d.data.wife.name);
            }} else {{
                g.append('rect')
                    .attr('width', 140)
                    .attr('height', 60)
                    .attr('x', -70)
                    .attr('y', -30)
                    .style('fill', '#f9f9f9')
                    .style('stroke', '#333');

                g.append('a')
                    .attr('xlink:href', function(d) {{ return d.data.url; }})
                    .append('text')
                    .attr('text-anchor', 'middle')
                    .attr('dy', '-0.5em')
                    .text(function(d) {{ return d.data.name; }});

                g.append('text')
                    .attr('text-anchor', 'middle')
                    .attr('dy', '1.2em')
                    .text(function(d) {{ return (d.data.dob || '') + ' ' + (d.data.valavu || ''); }});
            }}
        }});
    </script>
    """

# Streamlit UI
st.set_page_config(layout="wide")
st.title("Interactive Family Tree")

params = st.query_params
query_id = params.get("id", ["P1"])[0]
tree_data = load_family_tree_from_db(query_id)

if tree_data:
    d3_html = get_d3_tree_html(tree_data)
    st.components.v1.html(d3_html, height=700, scrolling=True)
else:
    st.warning("No data found for the given ID.")
