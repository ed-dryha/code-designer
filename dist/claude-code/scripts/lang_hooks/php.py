"""PHP tweaks: modifiers from visibility/static/abstract children, __construct, extends/implements supertypes."""

MOD_TYPES = ("visibility_modifier", "static_modifier", "abstract_modifier", "final_modifier", "readonly_modifier")


def _text(node):
    return node.text.decode("utf-8", errors="replace")


def post_process(symbols, root_node, source_bytes):
    for s in symbols:
        n = s["node"]
        mods = [_text(c) for c in n.children if c.type in MOD_TYPES]
        if mods:
            s["modifiers"] = " ".join(mods)
        if s["kind"] == "method" and s["name"] == "__construct":
            s["kind"] = "constructor"
        if s["kind"] in ("class", "interface", "enum"):
            sup = []
            for c in n.children:
                if c.type in ("base_clause", "class_interface_clause"):
                    sup.extend(_text(x) for x in c.named_children)
            if sup:
                s["supers"] = sup
