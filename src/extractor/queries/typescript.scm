(class_declaration
  name: (type_identifier) @type.name
  (class_heritage (extends_clause)? @type.supers)?) @type.class

(abstract_class_declaration
  name: (type_identifier) @type.name
  (class_heritage (extends_clause)? @type.supers)?) @type.class

(interface_declaration
  name: (type_identifier) @type.name
  (extends_type_clause)? @type.supers) @type.interface

(enum_declaration
  name: (identifier) @type.name) @type.enum

(class_body
  (method_definition name: (_) @method.name) @method)

(class_body
  (method_signature name: (_) @method.name) @method)

(class_body
  (abstract_method_signature name: (_) @method.name) @method)

(interface_body
  (method_signature name: (_) @method.name) @method)

(class_body
  (public_field_definition
    name: (_) @field.name
    type: (type_annotation)? @field.type) @field)

(interface_body
  (property_signature
    name: (_) @field.name
    type: (type_annotation)? @field.type) @field)

(program
  (function_declaration name: (identifier) @function.name) @function)

(program
  (export_statement
    declaration: (function_declaration name: (identifier) @function.name) @function))
