(class
  name: (_) @type.name
  superclass: (superclass)? @type.supers) @type.class

(module
  name: (_) @type.name) @type.object

(method
  name: (identifier) @method.name) @method

(singleton_method
  name: (identifier) @method.name) @method
