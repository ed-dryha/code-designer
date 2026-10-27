func describe(k: Place.Kind) -> String {
    switch k {
    case .city: return "city"
    default: return "other"
    }
}
