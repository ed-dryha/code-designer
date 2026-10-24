package demo

interface Shape {
    fun area(): Double
}

open class Base(val label: String, var count: Int, size: Int) : Shape {
    private val tag: String = "t"
    var extra: Int = 0

    override fun area(): Double = 0.0

    fun scale(factor: Int): Int {
        return factor
    }
}

data class Point(val x: Int, val y: Int)

object Registry {
    fun register() {}
}

fun helper(a: Int): Int {
    return a
}
