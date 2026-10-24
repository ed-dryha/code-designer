(class_definition
  name: (identifier) @type.name
  superclasses: (argument_list)? @type.supers) @type.class

(class_definition
  body: (block
    (function_definition name: (identifier) @method.name) @method))

(class_definition
  body: (block
    (decorated_definition
      (function_definition name: (identifier) @method.name) @method)))

(class_definition
  body: (block
    (assignment
      left: (identifier) @field.name
      type: (type)? @field.type) @field))

(module
  (function_definition name: (identifier) @function.name) @function)

(module
  (decorated_definition
    (function_definition name: (identifier) @function.name) @function))
