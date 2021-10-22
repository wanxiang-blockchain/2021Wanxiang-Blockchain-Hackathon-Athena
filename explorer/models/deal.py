import mongoengine.fields as fields
from base.db.mongo import MongoBaseModel, Decimal2Field


class Deal(MongoBaseModel):
    deal_id = fields.IntField(help_text="订单id")
    piece_cid = fields.StringField(help_text="文件cid")
    piece_size = Decimal2Field(help_text="文件大小", precision=0, default=0)
    is_verified = fields.BooleanField(help_text="是否已验证")
    client = fields.StringField(help_text="客户")
    provider = fields.StringField(help_text="托管矿工")
    start_epoch = fields.IntField(help_text="存储开始高度")
    end_epoch = fields.IntField(help_text="存储结束高度")
    storage_price_per_epoch = Decimal2Field(help_text="每高度每byte单价", precision=0, default=0)
    provider_collateral = Decimal2Field(help_text="托管矿工抵押", precision=0, default=0)
    client_collateral = Decimal2Field(help_text="客户抵押", precision=0, default=0)
    msg_id = fields.StringField(help_text="消息msg_cid")
    height = fields.IntField()
    height_time = fields.DateTimeField()

    meta = {
        "db_alias": "base",
        "strict": False,
        'indexes': [
            {"fields": ("-height",)},
            {"fields": ("deal_id", "-height")},
            {"fields": ("client", "-height")},
            {"fields": ("provider", "-height")}
        ]
    }
