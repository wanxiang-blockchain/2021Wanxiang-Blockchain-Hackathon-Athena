from base.db.mongo import MongoBaseModel, Decimal2Field
import mongoengine.fields as fields


class Wallets(MongoBaseModel):
    address = fields.StringField()
    id = fields.StringField()
    wallet_type = fields.StringField(help_text="钱包类型")  # account:普通账户  multisig 多重签名账户
    value = Decimal2Field(help_text="余额", precision=0, default=0)
    update_height = fields.IntField()
    update_height_time = fields.DateTimeField()
    create_height = fields.IntField()
    create_height_time = fields.DateTimeField()
    available_balance = Decimal2Field(help_text="多重签名账户", db_field="avaliable_balance", precision=0, default=0)
    initial_balance = Decimal2Field(help_text="多重签名账户", precision=0, default=0)
    start_epoch = fields.IntField(help_text="多重签名账户")
    unlock_duration = fields.IntField(help_text="多重签名账户", )
    locking_balance = Decimal2Field(help_text="多重签名账户", precision=0, default=0)
    signers = fields.ListField(fields.StringField(), help_text="多重签名账户")
    approval_threshold = fields.IntField(help_text="多重签名账户")
    synced_at_str = fields.DateTimeField()
    synced_at = fields.IntField()

    meta = {
        "db_alias": "base",
        "strict": False,
        'indexes': [
            {"fields": ("address",)},
            # {"fields": ("id",)},
            {"fields": ("-value", "wallet_type")},
        ]
    }


class WalletRecords(MongoBaseModel):
    address_id = fields.StringField()
    address = fields.StringField()
    value = Decimal2Field(help_text="余额", precision=2, default=0)
    height = fields.IntField()
    height_time = fields.DateTimeField()
    meta = {
        "db_alias": "base",
        "strict": False,
        'indexes': [
            {"fields": ("address", "height")},
            {"fields": ("address_id", "height")},
        ]
    }
