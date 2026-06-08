import XCTest
@testable import TestProject

final class TestProjectTests: XCTestCase {
    func testExample() throws {
        XCTAssertEqual(2 + 2, 4)
    }

    func testGreeting() throws {
        // Just calling it to ensure it doesn't crash, since capturing print is complex
        greeting()
    }

    func testDivide() throws {
        XCTAssertEqual(divide(10, 2), 5)
        XCTAssertEqual(divide(9, 3), 3)
        XCTAssertEqual(divide(-10, 2), -5)
        XCTAssertEqual(divide(10, -2), -5)
        XCTAssertEqual(divide(-10, -2), 5)
        XCTAssertEqual(divide(0, 5), 0)
        XCTAssertEqual(divide(7, 2), 3)
        XCTAssertEqual(divide(100, 10), 10)
    }

    func testDivisionDemoOutput() throws {
        XCTAssertEqual(divisionDemoOutput(), "10 / 2 = 5")
    }
}
