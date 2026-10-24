(type_spec
  name: (type_identifier) @type.name
  type: (struct_type)) @type.struct

(type_spec
  name: (type_identifier) @type.name
  type: (interface_type)) @type.interface

(interface_type
  (method_elem name: (field_identifier) @method.name) @method)

(method_declaration
  name: (field_identifier) @method.name) @method

(function_declaration
  name: (identifier) @function.name) @function

(struct_type
  (field_declaration_list
    (field_declaration
      name: (field_identifier) @field.name
      type: (_) @field.type) @field))
