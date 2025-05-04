# app.py

try:
    import streamlit as st
    import sqlite3
    import json
except ModuleNotFoundError as e:
    raise ImportError("This script must be run in a Streamlit environment where the 'streamlit' module is available.") from e

# Load data from SQLite
def load_family_tree_from_db(root_id="P1"):
    conn = sqlite3.connect("family_tree.db")
    cursor = conn.cursor()

    def get_person(pid):
        st.write(f"🔍 Fetching person: {pid}")
        cursor.execute("SELECT * FROM people WHERE id = ?", (pid,))
        row = cursor.fetchone()
        if not row:
            st.warning(f"⚠️ Person not found: {pid}")
            return None

        columns = [desc[0] for desc in cursor.description]
        data = dict(zip(columns, row))
        person = {
            "id": data["id"],
            "name": data["name"],
            "dob": data["dob"],
            "valavu": data["valavu"],
            "is_alive": data["alive"] == "Yes",
            "url": f"https://abc.com?id={data['id']}"
        }

        spouse_id = data.get("spouse_id")
        if spouse_id:
            spouse = get_person(spouse_id)
            if spouse:
                st.write(f"💍 {data['name']} is married to {spouse['name']}")
                couple_node = {
                    "id": f"{data['id']}_couple",
                    "type": "couple",
                    "husband": person if data.get("gender") == "M" else spouse,
                    "wife": spouse if data.get("gender") == "M" else person,
                    "children": []
                }
                # Children are assigned to couple node
                children_str = data.get("children_ids", "")
                for cid in children_str.split(";"):
                    cid = cid.strip()
                    if cid:
                        child = get_person(cid)
                        if child:
                            couple_node["children"].append(child)
                return couple_node

        children_str = data.get("children_ids", "")
        children = []
        for cid in children_str.split(";"):
            cid = cid.strip()
            if cid:
                child = get_person(cid)
                if child:
                    children.append(child)
        if children:
            person["children"] = children

        return person

    result = get_person(root_id)
    conn.close()
    return result

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
