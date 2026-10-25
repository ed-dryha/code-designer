"""Ruby tweaks. All fields are heuristic: attr_accessor/attr_reader/attr_writer symbols and @ivar assignments
in initialize. initialize is a constructor, `def self.x` is static, top-level def is a function. Modules map to kind object."""

ATTR = ("attr_accessor", "attr_reader", "attr_writer")


def _text(node):
    return node.text.decode("utf-8", errors="replace")


def _in_type_body(node):
    p = node.parent
    return p is not None and p.type == "body_statement" and p.parent is not None and p.parent.type in ("class", "module")


def _walk(node):
    stack = [node]
    while stack:
        n = stack.pop()
        yield n
        stack.extend(reversed(n.children))


def post_process(symbols, root_node, source_bytes):
    for s in symbols:
        n = s["node"]
        if n.type == "singleton_method":
            s["modifiers"] = "static"
        if s["kind"] == "method":
            if s["name"] == "initialize" and n.type == "method":
                s["kind"] = "constructor"
            elif n.parent is not None and n.parent.type == "program":
                s["kind"] = "function"
    extra, attr_names = [], set()
    for n in _walk(root_node):
        if n.type == "call" and _in_type_body(n):
            m = n.child_by_field_name("method")
            args = n.child_by_field_name("arguments")
            if m is not None and _text(m) in ATTR and args is not None:
                for a in args.named_children:
                    if a.type in ("simple_symbol", "string"):
                        name = _text(a).lstrip(":").strip("\"'")
                        attr_names.add((n.parent.parent.start_byte, name))
                        extra.append({"kind": "field", "name": name, "node": a, "typeText": None, "heuristic": True})
    seen = set()
    for s in symbols:
        if s["kind"] == "constructor" and s["node"].type == "method":
            cls = s["node"].parent.parent if s["node"].parent is not None else None
            if cls is None:
                continue
            for n in _walk(s["node"]):
                if n.type == "assignment":
                    left = n.child_by_field_name("left")
                    if left is not None and left.type == "instance_variable":
                        raw = _text(left)
                        key = (cls.start_byte, raw)
                        if key in seen or (cls.start_byte, raw.lstrip("@")) in attr_names:
                            continue
                        seen.add(key)
                        extra.append({"kind": "field", "name": raw, "node": n, "typeText": None, "heuristic": True})
    symbols.extend(extra)
