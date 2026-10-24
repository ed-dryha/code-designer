(class_declaration
  name: (identifier) @type.name
  (class_heritage)? @type.supers) @type.class

(class_body
  (method_definition name: (_) @method.name) @method)

(class_body
  (field_definition property: (_) @field.name) @field)

(program
  (function_declaration name: (identifier) @function.name) @function)

(program
  (export_statement
    declaration: (function_declaration name: (identifier) @function.name) @function))
