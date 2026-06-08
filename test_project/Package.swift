// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "TestProject",
    targets: [
        .executableTarget(
            name: "TestProject",
            path: "Sources"),
        .testTarget(
            name: "TestProjectTests",
            dependencies: ["TestProject"],
            path: "Tests"),
    ]
)
