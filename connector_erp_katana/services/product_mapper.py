from ..schema.product import ProductProduct, ProductVariant


class KatanaProductMapper:
    def __init__(self, backend):
        self.backend = backend

    def build_variant_dict(self, products: list[ProductProduct]) -> list[dict]:
        name_lookup: dict[int, str] = {
            product.record_id: product.name for product in products
        }

        variants: list[ProductVariant] = [
            variant for product in products for variant in product.variants
        ]

        data = [
            {
                "backend_id": self.backend.id,
                "external_id": variant.record_id,
                "external_name": f"[{variant.sku}] {name_lookup[variant.product_id]}",
            }
            for variant in variants
        ]

        return data
