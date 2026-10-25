(class_declaration
  name: (identifier) @type.name
  (base_list)? @type.supers) @type.class

(interface_declaration
  name: (identifier) @type.name
  (base_list)? @type.supers) @type.interface

(struct_declaration
  name: (identifier) @type.name
  (base_list)? @type.supers) @type.struct

(enum_declaration
  name: (identifier) @type.name) @type.enum

(record_declaration
  name: (identifier) @type.name
  (base_list)? @type.supers) @type.record

(method_declaration
  name: (identifier) @method.name) @method

(constructor_declaration
  name: (identifier) @constructor.name) @constructor

(field_declaration
  (variable_declaration
    type: (_) @field.type
    (variable_declarator name: (identifier) @field.name))) @field

(property_declaration
  type: (_) @field.type
  name: (identifier) @field.name) @field
