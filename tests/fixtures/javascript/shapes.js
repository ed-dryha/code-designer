class Shape {
  name = "shape";
  static count = 0;

  constructor(name) {
    this.name = name;
  }

  area() {
    return 0;
  }
}

function makeShape(name) {
  return new Shape(name);
}
