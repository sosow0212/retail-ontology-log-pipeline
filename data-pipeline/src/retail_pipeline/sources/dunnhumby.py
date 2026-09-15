"""Table specifications of the dunnhumby "The Complete Journey" dataset."""

from retail_pipeline.sources.table_spec import ColumnType, SourceColumn, SourceTable

DUNNHUMBY_SOURCE = "dunnhumby"

_INTEGER = ColumnType.INTEGER
_FLOAT = ColumnType.FLOAT
_STRING = ColumnType.STRING


def _table(name: str, *columns: tuple[str, ColumnType]) -> SourceTable:
    return SourceTable(
        source=DUNNHUMBY_SOURCE,
        name=name,
        columns=tuple(SourceColumn.of(header, column_type) for header, column_type in columns),
    )


PRODUCT = _table(
    "product",
    ("PRODUCT_ID", _INTEGER),
    ("MANUFACTURER", _INTEGER),
    ("DEPARTMENT", _STRING),
    ("BRAND", _STRING),
    ("COMMODITY_DESC", _STRING),
    ("SUB_COMMODITY_DESC", _STRING),
    ("CURR_SIZE_OF_PRODUCT", _STRING),
)

HH_DEMOGRAPHIC = _table(
    "hh_demographic",
    ("AGE_DESC", _STRING),
    ("MARITAL_STATUS_CODE", _STRING),
    ("INCOME_DESC", _STRING),
    ("HOMEOWNER_DESC", _STRING),
    ("HH_COMP_DESC", _STRING),
    ("HOUSEHOLD_SIZE_DESC", _STRING),
    ("KID_CATEGORY_DESC", _STRING),
    ("household_key", _INTEGER),
)

CAMPAIGN_DESC = _table(
    "campaign_desc",
    ("DESCRIPTION", _STRING),
    ("CAMPAIGN", _INTEGER),
    ("START_DAY", _INTEGER),
    ("END_DAY", _INTEGER),
)

CAMPAIGN_TABLE = _table(
    "campaign_table",
    ("DESCRIPTION", _STRING),
    ("household_key", _INTEGER),
    ("CAMPAIGN", _INTEGER),
)

COUPON = _table(
    "coupon",
    ("COUPON_UPC", _INTEGER),
    ("PRODUCT_ID", _INTEGER),
    ("CAMPAIGN", _INTEGER),
)

COUPON_REDEMPT = _table(
    "coupon_redempt",
    ("household_key", _INTEGER),
    ("DAY", _INTEGER),
    ("COUPON_UPC", _INTEGER),
    ("CAMPAIGN", _INTEGER),
)

TRANSACTION_DATA = _table(
    "transaction_data",
    ("household_key", _INTEGER),
    ("BASKET_ID", _INTEGER),
    ("DAY", _INTEGER),
    ("PRODUCT_ID", _INTEGER),
    ("QUANTITY", _INTEGER),
    ("SALES_VALUE", _FLOAT),
    ("STORE_ID", _INTEGER),
    ("RETAIL_DISC", _FLOAT),
    ("TRANS_TIME", _INTEGER),
    ("WEEK_NO", _INTEGER),
    ("COUPON_DISC", _FLOAT),
    ("COUPON_MATCH_DISC", _FLOAT),
)

CAUSAL_DATA = _table(
    "causal_data",
    ("PRODUCT_ID", _INTEGER),
    ("STORE_ID", _INTEGER),
    ("WEEK_NO", _INTEGER),
    ("display", _STRING),
    ("mailer", _STRING),
)

# Small reference tables first so a failure on a large file is found after the cheap checks.
DUNNHUMBY_TABLES: tuple[SourceTable, ...] = (
    PRODUCT,
    HH_DEMOGRAPHIC,
    CAMPAIGN_DESC,
    CAMPAIGN_TABLE,
    COUPON,
    COUPON_REDEMPT,
    TRANSACTION_DATA,
    CAUSAL_DATA,
)
