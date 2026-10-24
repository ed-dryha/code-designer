"""Kotlin tweaks: supertypes come from delegation_specifier children (no field names in the grammar)."""


def _text(node):
    return node.text.decode("utf-8", errors="replace")


def _supers(type_node):
    out = []
    for c in type_node.named_children:
        if c.type != "delegation_specifier":
            continue
        t = c.named_children[0] if c.named_children else None
        if t is not None and t.type == "constructor_invocation" and t.named_children:
            t = t.named_children[0]
        if t is not None:
            out.append(_text(t))
    return out


def post_process(symbols, root_node, source_bytes):
    for s in symbols:
        n = s["node"]
        if s["kind"] in ("class", "interface"):
            sup = _supers(n)
            if sup:
                s["supers"] = sup
            if s["kind"] == "class" and "enum" in (s.get("modifiers") or "").split():
                s["kind"] = "enum"
        # primary-constructor val/var params are real fields (not heuristic)
