(class_declaration
  "class"
  (modifiers)? @modifiers
  (type_identifier) @type.name) @type.class

(class_declaration
  "interface"
  (modifiers)? @modifiers
  (type_identifier) @type.name) @type.interface

(object_declaration
  (modifiers)? @modifiers
  (type_identifier) @type.name) @type.object

(class_body
  (function_declaration
    (modifiers)? @modifiers
    (simple_identifier) @method.name) @method)

(source_file
  (function_declaration
    (modifiers)? @modifiers
    (simple_identifier) @function.name) @function)

(class_body
  (property_declaration
    (modifiers)? @modifiers
    (variable_declaration
      (simple_identifier) @field.name
      (user_type)? @field.type)) @field)

(primary_constructor
  (class_parameter
    (modifiers)? @modifiers
    (binding_pattern_kind)
    (simple_identifier) @field.name
    (user_type)? @field.type) @field)
