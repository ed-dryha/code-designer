package demo;

public interface Shapes {
    double area();
}

abstract class Base implements Shapes {
    protected String label;
    public static int count = 0;

    Base(String label) {
        this.label = label;
    }

    public void scale(int factor) {
    }

    public void scale(double factor, String mode) {
    }

    static class Inner {
        private int depth;
    }
}

enum Color {
    RED,
    GREEN
}
