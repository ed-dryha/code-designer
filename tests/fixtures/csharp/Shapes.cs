namespace Demo
{
    public interface IShape
    {
        double Area();
    }

    public class Base : IShape
    {
        private string label;
        public static int Count;
        public string Name { get; set; }

        public Base(string label)
        {
            this.label = label;
        }

        public double Area() { return 0.0; }

        public int Scale(int factor) { return factor; }

        public double Scale(double factor, string mode) { return factor; }

        public static void Reset() {}

        public class Inner
        {
            public int Depth;
        }
    }

    public record Point(int X, int Y);
}
