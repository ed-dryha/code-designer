(class_declaration
  name: (name) @type.name) @type.class

(interface_declaration
  name: (name) @type.name) @type.interface

(trait_declaration
  name: (name) @type.name) @type.trait

(enum_declaration
  name: (name) @type.name) @type.enum

(method_declaration
  name: (name) @method.name) @method

(function_definition
  name: (name) @function.name) @function

(property_declaration
  type: (_)? @field.type
  (property_element
    name: (variable_name (name) @field.name))) @field
