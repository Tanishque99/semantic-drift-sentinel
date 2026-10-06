"""Consumer-goods sample dataset: two deployment versions of a product catalog.

The story: an upstream pipeline tags each product with a `category`. Between v1
and v2 a miscategorisation crept in -- e.g. the iPhone moved from `Mobile` to
`Home Appliances`. The drifted category is still a VALID category string (it is
in the allowed enum), the product name and description are untouched, so every
deterministic check passes. Only the *meaning* of the category is now wrong.

That is the same failure class as the support-ticket dataset, but localized to a
single enum column: the string is well-formed, the meaning is not.

No randomness: the dataset is identical on every machine so the demo is
reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

VALID_CATEGORIES_GOODS = [
    "Mobile",
    "Computers",
    "Audio",
    "Wearables",
    "Television",
    "Home Appliances",
    "Accessories",
]


@dataclass
class Product:
    row_id: str
    deployment_version: str
    product_name: str
    category: str
    description: str
    created_at: str  # ISO date; all recent so freshness passes


# For each product: the CORRECT category (v1) and a plausible-but-wrong category
# (v2) that is still a valid enum value. The description never changes -- only
# the category's meaning drifts.
_BASE = [
    (
        "iPhone 15 Pro",
        "Mobile",
        "Apple flagship smartphone with the A17 Pro chip, 6.1-inch display, "
        "and a triple-camera system.",
        "Home Appliances",
    ),
    (
        "Samsung Galaxy S24 Ultra",
        "Mobile",
        "Android smartphone with a built-in S Pen, 200MP camera, and a 6.8-inch "
        "AMOLED display.",
        "Television",
    ),
    (
        "MacBook Air M3",
        "Computers",
        "Thin and light laptop with the Apple M3 chip and a 13-inch Liquid "
        "Retina display.",
        "Audio",
    ),
    (
        "Dell XPS 15 Laptop",
        "Computers",
        "Windows creator laptop with Intel Core Ultra and a 15-inch OLED "
        "touchscreen.",
        "Accessories",
    ),
    (
        "Sony WH-1000XM5 Headphones",
        "Audio",
        "Wireless over-ear noise-cancelling headphones with up to 30 hours of "
        "battery life.",
        "Mobile",
    ),
    (
        "Bose SoundLink Flex Speaker",
        "Audio",
        "Portable Bluetooth speaker with deep bass and a waterproof, rugged "
        "design.",
        "Home Appliances",
    ),
    (
        "Apple Watch Series 9",
        "Wearables",
        "Smartwatch with heart-rate and blood-oxygen sensors, an always-on "
        "Retina display, and GPS.",
        "Home Appliances",
    ),
    (
        "Fitbit Charge 6 Band",
        "Wearables",
        "Fitness band that tracks heart rate, steps, and sleep with a seven-day "
        "battery.",
        "Mobile",
    ),
    (
        "LG C3 65-inch OLED TV",
        "Television",
        "4K OLED smart TV with webOS, Dolby Vision, and a 120Hz panel for "
        "gaming.",
        "Mobile",
    ),
    (
        "Dyson V15 Detect Vacuum",
        "Home Appliances",
        "Cordless stick vacuum with laser dust detection and whole-machine HEPA "
        "filtration.",
        "Computers",
    ),
    (
        "Instant Pot Duo 7-in-1",
        "Home Appliances",
        "Electric pressure cooker that pressure-cooks, slow-cooks, steams, and "
        "sautes in one pot.",
        "Audio",
    ),
    (
        "Anker 65W USB-C Charger",
        "Accessories",
        "Compact 65W GaN fast charger with two USB-C ports for laptops and "
        "phones.",
        "Wearables",
    ),
]


def generate(version: str) -> list[Product]:
    """Return the products for a deployment version ('v1' or 'v2')."""
    use_good = version == "v1"
    rows: list[Product] = []
    for i, (name, correct, desc, drifted) in enumerate(_BASE):
        rows.append(
            Product(
                row_id=f"SKU-{i:03d}",
                deployment_version=version,
                product_name=name,
                category=correct if use_good else drifted,
                description=desc,  # description is unchanged across versions
                created_at="2026-10-05",
            )
        )
    return rows


def all_rows() -> list[dict]:
    return [asdict(p) for p in (generate("v1") + generate("v2"))]
