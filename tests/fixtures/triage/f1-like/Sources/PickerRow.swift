func rowLabel(for k: Place.Kind) -> String {
    switch k {
    case .city: return "c"
    case .region: return "r"
    }
}
