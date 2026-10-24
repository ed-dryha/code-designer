"""C# tweaks: collect every `modifier` child, and report property_declaration as kind property."""


def post_process(symbols, root_node, source_bytes):
    for s in symbols:
        n = s["node"]
        mods = [c.text.decode("utf-8", errors="replace") for c in n.children if c.type == "modifier"]
        if mods:
            s["modifiers"] = " ".join(mods)
        if n.type == "property_declaration":
            s["kind"] = "property"
        if s["kind"] == "method" and n.parent is not None and n.parent.parent is not None \
                and n.parent.parent.type == "interface_declaration" and not s.get("modifiers"):
            s["modifiers"] = "public"
