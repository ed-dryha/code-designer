package shapes

type Shape interface {
	Area() float64
}

type Circle struct {
	Radius float64
	Name   string
}

func (c Circle) Area() float64 {
	return c.Radius * c.Radius
}

func (c *Circle) Scale(f float64) {
	c.Radius *= f
}

func NewCircle(r float64) *Circle {
	return &Circle{Radius: r}
}
