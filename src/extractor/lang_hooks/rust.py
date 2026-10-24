"""Rust tweaks: impl-block methods are parented to the struct/enum/trait named by the impl's type field.

`impl Trait for Type` also records Trait as a supertype of Type. `pub` maps to public, `pub(crate)` to internal;
associated functions without a self parameter are static.
"""


def _text(node):
    return node.text.decode("utf-8", errors="replace")


def _base_name(type_node):
    while type_node is not None and type_node.type in ("generic_type", "reference_type"):
        inner = type_node.child_by_field_name("type")
        type_node = inner if inner is not None else (type_node.named_children[0] if type_node.named_children else None)
    return _text(type_node) if type_node is not None else None


def post_process(symbols, root_node, source_bytes):
    types = {s["name"]: s for s in symbols if s["kind"] in ("struct", "enum", "trait")}
    for s in symbols:
        n = s["node"]
        vis = next((c for c in n.children if c.type == "visibility_modifier"), None)
        if vis is not None:
            s["modifiers"] = "internal" if "crate" in _text(vis) else ("public" if _text(vis) == "pub" else "private")
        if s["kind"] != "method":
            continue
        impl = n.parent.parent if n.parent is not None else None
        if impl is not None and impl.type == "impl_item":
            owner = types.get(_base_name(impl.child_by_field_name("type")))
            if owner is not None:
                s["parent_override"] = owner
                tr = impl.child_by_field_name("trait")
                if tr is not None:
                    name = _base_name(tr)
                    sup = owner.setdefault("supers", [])
                    if name and name not in sup:
                        sup.append(name)
            params = n.child_by_field_name("parameters")
            has_self = params is not None and any(c.type == "self_parameter" for c in params.named_children)
            if not has_self:
                s["modifiers"] = ((s.get("modifiers") or "") + " static").strip()
