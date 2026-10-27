import Foundation

struct RegionPack {
    let url: URL?

    static func bundled() -> RegionPack {
        RegionPack(url: nil)
    }
}
