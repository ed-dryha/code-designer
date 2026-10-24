pub trait Shape {
    fn area(&self) -> f64;
}

pub struct Circle {
    pub radius: f64,
    name: String,
}

pub enum Color {
    Red,
    Green,
}

impl Circle {
    pub fn new(radius: f64) -> Circle {
        Circle { radius, name: String::new() }
    }

    pub fn grow(&mut self, by: f64) {
        self.radius += by;
    }
}

impl Shape for Circle {
    fn area(&self) -> f64 {
        3.14 * self.radius * self.radius
    }
}

pub fn helper(a: i32) -> i32 {
    a
}
