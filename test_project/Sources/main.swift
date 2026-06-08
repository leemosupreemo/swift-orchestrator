import Foundation

print("Hello, Test Project!")

func add(_ a: Int, _ b: Int) -> Int {
    return a + b
}

func greeting() {
    print("Hello, Orchestrator!")
}

/// Divides two integers.
/// - Parameters:
///   - a: The dividend.
///   - b: The divisor.
/// - Returns: The quotient of the division.
func divide(_ a: Int, _ b: Int) -> Int {
    return a / b
}

print(divide(10, 2))
