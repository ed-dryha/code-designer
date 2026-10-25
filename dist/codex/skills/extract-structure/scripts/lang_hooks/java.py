"""Java tweaks: interface methods are implicitly public."""


def post_process(symbols, root_node, source_bytes):
    for s in symbols:
        if s["kind"] == "method" and s["node"].parent is not None \
                and s["node"].parent.type == "interface_body" and not s.get("modifiers"):
            s["modifiers"] = "public"
