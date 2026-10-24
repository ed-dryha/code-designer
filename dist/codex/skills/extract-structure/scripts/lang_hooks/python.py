"""Python tweaks: __init__ is a constructor; self.x assignments in __init__ are heuristic fields."""


def _text(node):
    return node.text.decode("utf-8", errors="replace")


def _class_of(node):
    n = node.parent
    while n is not None and n.type != "class_definition":
        n = n.parent
    return n.start_byte if n is not None else None


def post_process(symbols, root_node, source_bytes):
    seen_fields = set()
    extra = []
    for s in symbols:
        if s["kind"] == "method" and s["name"] == "__init__":
            s["kind"] = "constructor"
            body = s["node"].child_by_field_name("body")
            stack = [body] if body is not None else []
            while stack:
                n = stack.pop()
                if n.type in ("function_definition", "class_definition", "lambda"):
                    continue
                if n.type == "assignment":
                    left = n.child_by_field_name("left")
                    if left is not None and left.type == "attribute":
                        obj = left.child_by_field_name("object")
                        attr = left.child_by_field_name("attribute")
                        if obj is not None and attr is not None and _text(obj) == "self":
                            key = (s["node"].start_byte, _text(attr))
                            if key not in seen_fields:
                                seen_fields.add(key)
                                extra.append({"kind": "field", "name": _text(attr), "node": n,
                                              "typeText": None, "heuristic": True})
                stack.extend(reversed(n.children))
    # Drop heuristic self.x that duplicates a class-level field of the same class.
    class_fields = {(_class_of(f["node"]), f["name"]) for f in symbols if f["kind"] == "field"}
    for e in extra:
        if (_class_of(e["node"]), e["name"]) not in class_fields:
            symbols.append(e)
