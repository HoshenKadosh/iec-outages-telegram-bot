from datetime import datetime
from tortoise.models import Model
from tortoise import fields


class City(Model):
    class Meta:
        table = "city"

    id: int = fields.BigIntField(pk=True, null=False)
    name: str = fields.CharField(max_length=100, null=False, index=True)
    district_id: int = fields.IntField(null=True)
    streets: fields.ReverseRelation["Street"]


class Street(Model):
    class Meta:
        table = "street"

    id: int = fields.IntField(pk=True)
    name: str = fields.CharField(max_length=100, null=False, index=True)
    city: fields.ForeignKeyRelation[City] = fields.ForeignKeyField(
        "models.City", related_name="streets"
    )


class User(Model):
    class Meta:
        table = "user"

    id: int = fields.BigIntField(pk=True)
    started_at: datetime = fields.DatetimeField(auto_now_add=True)
    addresses: fields.ReverseRelation["Address"]


class Address(Model):
    class Meta:
        table = "address"

    id: int = fields.IntField(pk=True)
    city: fields.ForeignKeyRelation[City] = fields.ForeignKeyField("models.City")
    street: fields.ForeignKeyRelation[Street] = fields.ForeignKeyField("models.Street")
    home_num: int = fields.IntField(null=False)
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="addresses"
    )


class Outage(Model):
    class Meta:
        table = "outage"

    id: int = fields.IntField(pk=True)
    city: fields.ForeignKeyRelation[City] = fields.ForeignKeyField("models.City")
    street: fields.ForeignKeyRelation[Street] = fields.ForeignKeyField("models.Street")
    home_num: int = fields.IntField(null=False)

    start_time: datetime = fields.DateField(auto_now_add=True, null=False)
    end_time: datetime = fields.DateField(null=True)
    # planned outage for maintenance
    is_planned: bool = fields.BooleanField(default=False, null=False)
    # incident in iec system
    incident_id: int = fields.IntField(null=True)
    incident_status_code: int = fields.IntField(null=True)
    # the source is what reported the outage probably
    incident_source_code: int = fields.IntField(null=True)
    incident_source_desc: str = fields.TextField(null=True)
    # trouble is the issue that caused the outage probably
    incident_trouble_code: int = fields.IntField(null=True)
    incident_trouble_desc: str = fields.TextField(null=True)
    # fixing outage delay cause
    delay_cause_code: int = fields.IntField(null=True)
    delay_cause_desc: str = fields.TextField(null=True)
    # crew that is assined and working to fix the outage
    crew_name: str = fields.TextField(null=True)
    crew_assigned_time: datetime = fields.DateField(null=True)
    restore_est: datetime = fields.DateField(null=True)
