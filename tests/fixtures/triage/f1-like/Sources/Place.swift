struct Place {
    enum Kind: String {
        case city
        case region
    }
    var kind: Kind
}
