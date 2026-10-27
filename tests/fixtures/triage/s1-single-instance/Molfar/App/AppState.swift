import Foundation

final class AppState {
    var pack = RegionPack.bundled()

    func reload() {
        pack = RegionPack.bundled()
    }

    func viewpointSearch() -> RegionPack? {
        if let url = Bundle.main.url(forResource: "RegionPack", withExtension: "json") {
            return RegionPack(url: url)
        }
        return nil
    }
}
