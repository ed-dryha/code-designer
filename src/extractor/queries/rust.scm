(struct_item
  name: (type_identifier) @type.name) @type.struct

(enum_item
  name: (type_identifier) @type.name) @type.enum

(trait_item
  name: (type_identifier) @type.name) @type.trait

(impl_item
  body: (declaration_list
    (function_item
      name: (identifier) @method.name) @method))

(trait_item
  body: (declaration_list
    [(function_item name: (identifier) @method.name)
     (function_signature_item name: (identifier) @method.name)] @method))

(source_file
  (function_item
    name: (identifier) @function.name) @function)

(struct_item
  body: (field_declaration_list
    (field_declaration
      name: (field_identifier) @field.name
      type: (_) @field.type) @field))
