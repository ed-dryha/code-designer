"""Go tweaks: receiver methods are not lexically inside their type, so parent them by receiver type name."""


def _receiver_type(method_node):
    recv = method_node.child_by_field_name("receiver")
    if recv is None:
        return None
    for n in recv.named_children:
        t = n.child_by_field_name("type")
        while t is not None and t.type in ("pointer_type", "generic_type", "parenthesized_type"):
            inner = t.child_by_field_name("type") if t.type == "generic_type" else None
            t = inner if inner is not None else (t.named_children[0] if t.named_children else None)
        if t is not None:
            return t.text.decode("utf-8", errors="replace")
    return None


def post_process(symbols, root_node, source_bytes):
    types = {s["name"]: s for s in symbols if s["kind"] in ("struct", "interface")}
    for s in symbols:
        if s["kind"] == "method" and s["node"].type == "method_declaration":
            owner = types.get(_receiver_type(s["node"]))
            if owner is not None:
                s["parent_override"] = owner
