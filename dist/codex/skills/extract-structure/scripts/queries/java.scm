(class_declaration
  name: (identifier) @type.name
  superclass: (superclass (_) @type.supers)?
  (modifiers)? @modifiers) @type.class

(interface_declaration
  name: (identifier) @type.name
  (modifiers)? @modifiers) @type.interface

(enum_declaration
  name: (identifier) @type.name
  (modifiers)? @modifiers) @type.enum

(record_declaration
  name: (identifier) @type.name
  (modifiers)? @modifiers) @type.record

(method_declaration
  name: (identifier) @method.name
  (modifiers)? @modifiers) @method

(constructor_declaration
  name: (identifier) @constructor.name
  (modifiers)? @modifiers) @constructor

(field_declaration
  (modifiers)? @modifiers
  type: (_) @field.type
  declarator: (variable_declarator name: (identifier) @field.name)) @field
