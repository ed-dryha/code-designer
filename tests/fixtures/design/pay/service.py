class PaymentService:
    def charge(self, provider, amount):
        if provider == "stripe":
            return stripe_charge(amount)
        elif provider == "paypal":
            return paypal_charge(amount)
        elif provider == "adyen":
            return adyen_charge(amount)
        raise ValueError(provider)

    def refund(self, provider, amount):
        if provider == "stripe":
            return stripe_refund(amount)
        elif provider == "paypal":
            return paypal_refund(amount)
        elif provider == "adyen":
            return adyen_refund(amount)
        raise ValueError(provider)


def helper(x):
    return x
