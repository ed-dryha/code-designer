<?php
namespace Demo;

interface Shape {
    public function area(): float;
}

trait Loggable {
    public function log(string $m): void {}
}

abstract class Base implements Shape {
    const PI = 3.14;
    protected string $label;
    public static int $count = 0;

    public function __construct(string $label) {
        $this->label = $label;
    }

    abstract public function area(): float;

    public static function reset(): void {}
}

function helper(int $a): int {
    return $a;
}
