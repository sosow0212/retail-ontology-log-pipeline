"""Deterministic sample files shaped exactly like the dunnhumby Complete Journey dataset.

Values are synthetic, but headers, value formats, and references between tables follow the
real files so that loading and joining behave the same way on the sample.
"""

import csv
import random
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from retail_pipeline.sources.dunnhumby import (
    CAMPAIGN_DESC,
    CAMPAIGN_TABLE,
    CAUSAL_DATA,
    COUPON,
    COUPON_REDEMPT,
    HH_DEMOGRAPHIC,
    PRODUCT,
    TRANSACTION_DATA,
)
from retail_pipeline.sources.table_spec import SourceTable

type CsvValue = int | str
type CsvRow = tuple[CsvValue, ...]

PRIVATE_LABEL_MANUFACTURER = 69
_CATALOG: dict[str, dict[str, tuple[str, ...]]] = {
    "GROCERY": {
        "SOFT DRINKS": ("SOFT DRINKS 12/18&15PK CAN CAR", "SFT DRNK 2 LITER BTL CARB INCL"),
        "FLUID MILK PRODUCTS": ("FLUID MILK WHITE ONLY", "MILK BY-PRODUCTS"),
        "BAKED BREAD/BUNS/ROLLS": ("MAINSTREAM WHITE BREAD", "HOT DOG BUNS"),
        "CHEESE": ("SHREDDED CHEESE", "STRING CHEESE"),
        "BAG SNACKS": ("POTATO CHIPS", "TORTILLA/NACHO CHIPS"),
    },
    "PRODUCE": {
        "TROPICAL FRUIT": ("BANANAS",),
        "VEGETABLES - ALL OTHERS": ("CUCUMBERS", "PEPPERS-ALL"),
    },
    "MEAT": {"BEEF": ("PRIMAL",), "CHICKEN": ("CHICKEN BREAST BONELESS",)},
    "DRUG GM": {"COLD AND FLU": ("COLD REMEDIES",), "VITAMINS": ("VITAMINS - MULTI",)},
    "DELI": {"DELI MEATS": ("MEAT: HAM BULK",)},
}
_PRODUCT_SIZES = ("12 OZ", "16 OZ", "1 GA", "2 LTR", "5 LB", "")
_AGE_GROUPS = ("19-24", "25-34", "35-44", "45-54", "55-64", "65+")
_MARITAL_STATUS_CODES = ("A", "B", "U")
_INCOME_GROUPS = ("Under 15K", "15-24K", "25-34K", "35-49K", "50-74K", "75-99K", "100-124K")
_HOMEOWNER_GROUPS = ("Homeowner", "Renter", "Probable Owner", "Unknown")
_HOUSEHOLD_COMPOSITIONS = ("Single Female", "Single Male", "2 Adults No Kids", "2 Adults Kids")
_HOUSEHOLD_SIZES = ("1", "2", "3", "4", "5+")
_KID_CATEGORIES = ("None/Unknown", "1", "2", "3+")
_CAMPAIGN_TYPES = ("TypeA", "TypeB", "TypeC")
_DISPLAY_CODES = ("0", "1", "2", "3", "4", "5", "6", "7", "9", "A")
_MAILER_CODES = ("0", "A", "C", "D", "F", "H", "J", "L", "P", "X", "Z")


@dataclass(frozen=True, slots=True)
class SampleSize:
    households: int = 120
    demographic_households: int = 60
    products: int = 400
    manufacturers: int = 40
    stores: int = 12
    weeks: int = 12
    baskets: int = 900
    campaigns: int = 6
    coupons_per_campaign: int = 8
    causal_rows: int = 1_500

    @property
    def days(self) -> int:
        return self.weeks * 7


@dataclass(frozen=True, slots=True)
class _Campaign:
    campaign_id: int
    description: str
    start_day: int
    end_day: int

    def is_active_on(self, day: int) -> bool:
        return self.start_day <= day <= self.end_day


def write_dunnhumby_sample(
    output_dir: Path, seed: int, size: SampleSize | None = None
) -> dict[str, int]:
    """Write all eight dunnhumby files into output_dir and return the row count of each file."""
    size = size or SampleSize()
    generator = random.Random(seed)
    output_dir.mkdir(parents=True, exist_ok=True)

    product_ids = [25_000 + index * 37 for index in range(size.products)]
    household_keys = list(range(1, size.households + 1))
    store_ids = [300 + index * 7 for index in range(size.stores)]
    campaigns = _campaigns(generator, size)
    campaign_members = {
        campaign.campaign_id: sorted(generator.sample(household_keys, k=size.households // 4))
        for campaign in campaigns
    }
    coupons = _coupons(generator, size, campaigns, product_ids)
    transactions, redemptions = _transactions_and_redemptions(
        generator,
        size,
        product_ids,
        household_keys,
        store_ids,
        campaigns,
        campaign_members,
        coupons,
    )

    rows_by_table: dict[SourceTable, list[CsvRow]] = {
        PRODUCT: _products(generator, size, product_ids),
        HH_DEMOGRAPHIC: _demographics(generator, size, household_keys),
        CAMPAIGN_DESC: [
            (campaign.description, campaign.campaign_id, campaign.start_day, campaign.end_day)
            for campaign in campaigns
        ],
        CAMPAIGN_TABLE: [
            (campaign.description, household_key, campaign.campaign_id)
            for campaign in campaigns
            for household_key in campaign_members[campaign.campaign_id]
        ],
        COUPON: coupons,
        COUPON_REDEMPT: redemptions,
        TRANSACTION_DATA: transactions,
        CAUSAL_DATA: _causal_rows(generator, size, product_ids, store_ids),
    }
    for table, rows in rows_by_table.items():
        _write_csv(output_dir / table.file_name, table.source_headers, rows)
    return {table.file_name: len(rows) for table, rows in rows_by_table.items()}


def _campaigns(generator: random.Random, size: SampleSize) -> list[_Campaign]:
    campaigns = []
    for campaign_id in range(1, size.campaigns + 1):
        start_day = generator.randint(1, size.days - 14)
        end_day = min(start_day + generator.randint(14, 35), size.days)
        campaigns.append(
            _Campaign(campaign_id, generator.choice(_CAMPAIGN_TYPES), start_day, end_day)
        )
    return campaigns


def _coupons(
    generator: random.Random,
    size: SampleSize,
    campaigns: Sequence[_Campaign],
    product_ids: Sequence[int],
) -> list[CsvRow]:
    rows: list[CsvRow] = []
    for campaign in campaigns:
        for coupon_index in range(size.coupons_per_campaign):
            coupon_upc = 10_000_000_000 + campaign.campaign_id * 1_000 + coupon_index
            for product_id in sorted(generator.sample(product_ids, k=generator.randint(1, 5))):
                rows.append((coupon_upc, product_id, campaign.campaign_id))
    return rows


def _products(
    generator: random.Random, size: SampleSize, product_ids: Sequence[int]
) -> list[CsvRow]:
    rows: list[CsvRow] = []
    for product_id in product_ids:
        manufacturer = generator.randint(1, size.manufacturers)
        if generator.random() < 0.2:
            manufacturer = PRIVATE_LABEL_MANUFACTURER
        department = generator.choice(sorted(_CATALOG))
        commodity = generator.choice(sorted(_CATALOG[department]))
        rows.append(
            (
                product_id,
                manufacturer,
                department,
                "Private" if manufacturer == PRIVATE_LABEL_MANUFACTURER else "National",
                commodity,
                generator.choice(_CATALOG[department][commodity]),
                generator.choice(_PRODUCT_SIZES),
            )
        )
    return rows


def _demographics(
    generator: random.Random, size: SampleSize, household_keys: Sequence[int]
) -> list[CsvRow]:
    selected_households = sorted(generator.sample(household_keys, k=size.demographic_households))
    return [
        (
            generator.choice(_AGE_GROUPS),
            generator.choice(_MARITAL_STATUS_CODES),
            generator.choice(_INCOME_GROUPS),
            generator.choice(_HOMEOWNER_GROUPS),
            generator.choice(_HOUSEHOLD_COMPOSITIONS),
            generator.choice(_HOUSEHOLD_SIZES),
            generator.choice(_KID_CATEGORIES),
            household_key,
        )
        for household_key in selected_households
    ]


def _transactions_and_redemptions(
    generator: random.Random,
    size: SampleSize,
    product_ids: Sequence[int],
    household_keys: Sequence[int],
    store_ids: Sequence[int],
    campaigns: Sequence[_Campaign],
    campaign_members: dict[int, list[int]],
    coupons: Iterable[CsvRow],
) -> tuple[list[CsvRow], list[CsvRow]]:
    shelf_prices = {product_id: generator.uniform(0.5, 15.0) for product_id in product_ids}
    campaigns_by_id = {campaign.campaign_id: campaign for campaign in campaigns}
    coupons_by_product: dict[int, list[tuple[int, int]]] = {}
    for coupon_upc, product_id, campaign_id in coupons:
        coupons_by_product.setdefault(int(product_id), []).append(
            (int(coupon_upc), int(campaign_id))
        )

    transactions: list[CsvRow] = []
    redemptions: list[CsvRow] = []
    for basket_index in range(size.baskets):
        basket_id = 30_000_000_000 + basket_index
        household_key = generator.choice(household_keys)
        store_id = generator.choice(store_ids)
        day = generator.randint(1, size.days)
        trans_time = generator.randint(6, 22) * 100 + generator.randint(0, 59)
        week_no = (day - 1) // 7 + 1
        for product_id in generator.sample(product_ids, k=generator.randint(1, 8)):
            quantity = generator.randint(1, 3)
            retail_discount = -round(shelf_prices[product_id] * quantity * 0.2, 2)
            if generator.random() >= 0.3:
                retail_discount = 0.0
            coupon_discount = 0.0
            for coupon_upc, campaign_id in coupons_by_product.get(product_id, []):
                is_eligible = household_key in campaign_members[campaign_id]
                if is_eligible and campaigns_by_id[campaign_id].is_active_on(day):
                    coupon_discount = -1.0
                    redemptions.append((household_key, day, coupon_upc, campaign_id))
                    break
            sales_value = round(shelf_prices[product_id] * quantity + retail_discount, 2)
            transactions.append(
                (
                    household_key,
                    basket_id,
                    day,
                    product_id,
                    quantity,
                    f"{sales_value:.2f}",
                    store_id,
                    f"{retail_discount:.2f}",
                    trans_time,
                    week_no,
                    f"{coupon_discount:.2f}",
                    "0.00",
                )
            )
    return transactions, redemptions


def _causal_rows(
    generator: random.Random,
    size: SampleSize,
    product_ids: Sequence[int],
    store_ids: Sequence[int],
) -> list[CsvRow]:
    features: set[tuple[int, int, int]] = set()
    while len(features) < size.causal_rows:
        features.add(
            (
                generator.choice(product_ids),
                generator.choice(store_ids),
                generator.randint(1, size.weeks),
            )
        )
    rows: list[CsvRow] = []
    for product_id, store_id, week_no in sorted(features):
        display, mailer = "0", "0"
        # Every causal row marks a promotion, so at least one of the two codes is set.
        while display == "0" and mailer == "0":
            display, mailer = generator.choice(_DISPLAY_CODES), generator.choice(_MAILER_CODES)
        rows.append((product_id, store_id, week_no, display, mailer))
    return rows


def _write_csv(path: Path, headers: Sequence[str], rows: Iterable[CsvRow]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(headers)
        writer.writerows(rows)
