"""Builder for schema-2 triage fixtures: one tiny tree plus model.json per shape and trigger.

make_fixture(tmp_path, name) writes tmp_path/name/{spec.md, model.json, sources...} and returns the
root. CASES[name] holds the declared edits, fresh new paths and the expected routing.
"""
import json
from pathlib import Path

SPEC_NEUTRAL = "# Feature\n- first item\n- second item\n- third item\n"

CASES = {
    "add-member": {"edits": ["add-member:AppState=extraFlag+state"], "new_paths": [],
                   "uncapped": "skip", "verdict": "skip"},
    "add-case-default": {"edits": ["add-case:Kind=delta"], "new_paths": [],
                         "uncapped": "light", "verdict": "light"},
    "add-case-exhaustive": {"edits": ["add-case:Kind=delta"], "new_paths": [],
                            "uncapped": "skip", "verdict": "skip"},
    "add-param": {"edits": ["add-param:AppState.load=force"], "new_paths": [],
                  "uncapped": "skip", "verdict": "skip"},
    "add-variant": {"edits": ["add-variant:Shape=Triangle@spec:2"], "new_paths": [],
                    "uncapped": "full", "verdict": "full"},
    "body-new-inputs": {"edits": ["body-new-inputs:AppState.load@mapCoverage"], "new_paths": [],
                        "uncapped": "skip", "verdict": "skip"},
    "change-contract-hot": {"edits": ["change-contract:Svc.resolve@spec:2"], "new_paths": [],
                            "uncapped": "light", "verdict": "light"},
    "change-contract-cold": {"edits": ["change-contract:Svc.resolve@spec:2"], "new_paths": [],
                             "uncapped": "skip", "verdict": "skip"},
    "change-assumption": {"edits": ["change-assumption:bundled@spec:2"], "new_paths": [],
                          "uncapped": "full", "verdict": "light"},
    "variation-2-subtypes": {"edits": ["add-member:Base=extra"], "new_paths": [],
                             "uncapped": "full", "verdict": "full"},
    "backlog-hit": {"edits": ["add-member:Widget=extra"], "new_paths": [],
                    "uncapped": "full", "verdict": "full", "backlog": "backlog.md"},
    "plan-overlap": {"edits": ["add-member:Widget=extra"], "new_paths": [],
                     "uncapped": "full", "verdict": "full", "futures": "futures.md"},
    "none": {"edits": [], "new_paths": ["Sources/New.swift"], "uncapped": "skip", "verdict": "skip"},
}


def _write(root, rel, text):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return rel


def _base_model(files, unavailable, symbols):
    return {
        "schemaVersion": 1,
        "generator": {"name": "cd-extract", "version": "0.0.0-test", "pack": None, "source": "tree-sitter"},
        "root": ".", "generatedAt": "2026-10-27T00:00:00Z", "status": "partial",
        "coverage": {"files": files, "unavailable": unavailable, "skipped": []},
        "symbols": symbols,
    }


def swift_model(files):
    un = [{"language": "swift", "files": sorted(files), "reason": "no-grammar"}]
    return _base_model([], un, [])


def _py_cov(path, nsyms):
    return {"path": path, "language": "python", "parsed": True, "symbols": nsyms, "hasErrors": False,
            "sha256": "0" * 64, "provenance": "tree-sitter"}


def _py_class(path, name, start, end, supertypes=()):
    return {"id": "%s#%s" % (path, name), "kind": "class", "name": name, "parent": None, "file": path,
            "span": {"startLine": start, "endLine": end}, "signature": None, "visibility": None,
            "static": False, "supertypes": [{"relation": "extends", "name": s} for s in supertypes],
            "typeText": None, "provenance": "tree-sitter", "inferred": False, "hash": "h-" + name}


def py_model(classes):
    """classes: [(path, name, start, end, supertypes)] one class per file."""
    cov = [_py_cov(p, 1) for p, *_ in classes]
    syms = [_py_class(*c) for c in classes]
    return _base_model(cov, [], syms)


def _dump(root, model):
    _write(root, "model.json", json.dumps(model, indent=2, sort_keys=True) + "\n")


def _swift_hub(root, n_callers):
    files = [_write(root, "App/AppState.swift",
                    "final class AppState {\n    var placeResolver: Int = 0\n"
                    "    var mapCoverage: Bool = false\n    func load() {}\n}\n")]
    for i in range(n_callers):
        files.append(_write(root, "App/V%d.swift" % i,
                            "func show%d(s: AppState) { s.placeResolver = %d }\n" % (i, i)))
    return files


def _kind_tree(root, default):
    files = [_write(root, "Sources/Kind.swift",
                    "enum Kind {\n    case alpha\n    case beta\n    case gamma\n}\n")]
    tail = "    default: return \"x\"\n" if default else "    case .gamma: return \"c\"\n"
    for i in range(3):
        files.append(_write(
            root, "Sources/S%d.swift" % i,
            "func describe%d(k: Kind) -> String {\n    switch k {\n    case .alpha: return \"a\"\n"
            "    case .beta: return \"b\"\n%s    }\n}\n" % (i, tail)))
    return files


def _svc_tree(root, n_callers):
    files = [_write(root, "Sources/Svc.swift",
                    "final class Svc {\n    func resolve(x: Int) -> Int { return x }\n}\n")]
    for i in range(n_callers):
        files.append(_write(root, "Sources/C%d.swift" % i,
                            "func use%d(svc: Svc) { let r = svc.resolve(x: %d) ; print(r) }\n" % (i, i)))
    return files


def make_fixture(tmp_path, name):
    if name not in CASES:
        raise KeyError(name)
    root = Path(tmp_path) / name
    root.mkdir(parents=True, exist_ok=True)
    spec = SPEC_NEUTRAL

    if name == "add-member":
        model = swift_model(_swift_hub(root, 10))
    elif name == "add-case-default":
        model = swift_model(_kind_tree(root, True))
    elif name == "add-case-exhaustive":
        model = swift_model(_kind_tree(root, False))
    elif name == "add-param":
        model = swift_model(_swift_hub(root, 3))
    elif name == "body-new-inputs":
        spec = "# Feature\n- show the map\n- mapCoverage gates the load\n"
        model = swift_model(_swift_hub(root, 3))
    elif name == "change-contract-hot":
        model = swift_model(_svc_tree(root, 5))
    elif name == "change-contract-cold":
        model = swift_model(_svc_tree(root, 2))
    elif name == "change-assumption":
        files = [_write(root, "Sources/Catalog.swift",
                        "enum Catalog {\n    static func bundled() -> Int { return 1 }\n}\n")]
        for i in range(4):
            files.append(_write(root, "Sources/R%d.swift" % i,
                                "func read%d() -> Int { return Catalog.bundled() }\n" % i))
        spec = "# Feature\n- load the catalog instead of always loading the bundled one\n"
        model = swift_model(files)
    elif name == "none":
        model = swift_model(_swift_hub(root, 1))
    elif name == "add-variant":
        _write(root, "pkg/shapes.py", "class Shape:\n    def area(self):\n        return 0\n")
        model = py_model([("pkg/shapes.py", "Shape", 1, 3, ())])
    elif name == "variation-2-subtypes":
        _write(root, "pkg/base.py", "class Base:\n    pass\n")
        _write(root, "pkg/a.py", "from pkg.base import Base\n\n\nclass A(Base):\n    pass\n")
        _write(root, "pkg/b.py", "from pkg.base import Base\n\n\nclass B(Base):\n    pass\n")
        model = py_model([("pkg/base.py", "Base", 1, 2, ()), ("pkg/a.py", "A", 4, 5, ("Base",)),
                          ("pkg/b.py", "B", 4, 5, ("Base",))])
    elif name in ("backlog-hit", "plan-overlap"):
        _write(root, "pkg/widget.py", "class Widget:\n    pass\n")
        model = py_model([("pkg/widget.py", "Widget", 1, 2, ())])
        if name == "backlog-hit":
            _write(root, "backlog.md",
                   "schema: 1\nkind: code-designer-backlog\n---\nid: F-god-class-abcdef\n"
                   "symbol: pkg/widget.py#Widget\nstatus: open\npriority: High\nrationale: r\n"
                   "evidence:\n- file: pkg/widget.py\n  startLine: 1\n  endLine: 1\n  quote: q\n")
        else:
            _write(root, "futures.md",
                   "schema: 1\nkind: code-designer-futures\n---\nid: P-views-abcdef\ntitle: Views\n"
                   "status: confirmed\naffected:\n- pkg/**\n")
    else:  # pragma: no cover
        raise KeyError(name)

    _write(root, "spec.md", spec)
    _dump(root, model)
    return root
