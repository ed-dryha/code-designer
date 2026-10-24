module Geometry
  class Shape
    attr_accessor :label, :color
    attr_reader :id

    def initialize(label)
      @label = label
      @area = 0
    end

    def area
      @area
    end

    def self.build(label)
      new(label)
    end

    class Inner
      def depth
        1
      end
    end
  end

  class Circle < Shape
    def radius
      2
    end
  end
end

def top_helper(x)
  x
end
