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
            recv = _receiver_type(s["node"])
            owner = types.get(recv)
            if owner is not None:
                s["parent_override"] = owner
            else:
                s["unresolved_receiver"] = recv  # resolved across files by cd_extract
    # multi-name fields (X, Y float64): one symbol per name
    have = {(s["node"].start_byte, s["name"]) for s in symbols if s["kind"] == "field"}
    extra = []
    for s in symbols:
        if s["kind"] != "field" or s["node"].type != "field_declaration":
            continue
        for n in s["node"].children_by_field_name("name"):
            name = n.text.decode("utf-8", errors="replace")
            if (s["node"].start_byte, name) in have:
                continue
            have.add((s["node"].start_byte, name))
            c = dict(s)
            c["name"] = name
            extra.append(c)
    symbols.extend(extra)
