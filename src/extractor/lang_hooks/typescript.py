"""TypeScript/TSX/JavaScript tweaks: constructors, arrow-function members, modifiers, type text."""

_MODS = ("accessibility_modifier", "static", "abstract", "readonly", "override")


def _modifiers(node):
    out = []
    for c in node.children:
        if c.type in _MODS:
            out.append(c.text.decode("utf-8", errors="replace"))
        elif c.type == "private_property_identifier":
            out.append("private")
    name = node.child_by_field_name("name") or node.child_by_field_name("property")
    if name is not None and name.type == "private_property_identifier":
        out.append("private")
    return " ".join(out)


def post_process(symbols, root_node, source_bytes):
    for s in symbols:
        node = s["node"]
        if s["kind"] in ("method", "field"):
            mods = _modifiers(node)
            if mods:
                s["modifiers"] = mods
        if s["kind"] == "method" and s["name"] == "constructor":
            s["kind"] = "constructor"
        if s["kind"] == "field":
            value = node.child_by_field_name("value")
            if value is not None and value.type in ("arrow_function", "function_expression", "function"):
                s["kind"] = "method"
        t = s.get("typeText")
        if t:
            t = t.lstrip(":").strip()
            s["typeText"] = t or None
