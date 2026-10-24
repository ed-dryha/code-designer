class Shape:
    def area(self):
        return 0


class Circle(Shape):
    radius: float = 1.0

    def __init__(self, radius):
        self.center = (0, 0)

    def scaled(self, k):
        def helper(x):
            return x * k
        return Circle(helper(self.radius))


def make_circle(r):
    return Circle(r)
