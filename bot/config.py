from dataclasses import dataclass
from envparse import env
from dotenv import load_dotenv

load_dotenv()

# import envparse
# import json

# envparse.read_env()


@dataclass
class Bot:
    token: str
    max_addresses_for_user: int
    admin_user_ids: list[int]


@dataclass
class IEC:
    base_url: str


@dataclass
class Config:
    is_production: bool
    bot: Bot
    iec: IEC


config = Config(
    is_production=env.str("MODE").upper() == "PRUDUCTION",
    bot=Bot(
        token=env.str("BOT_TOKEN"),
        max_addresses_for_user=env.int("MAX_ADDRESSES_FOR_USER"),
        admin_user_ids=env.list("ADMIN_USER_IDS", subcast=int),
    ),
    iec=IEC(
        base_url=env.str("IEC_BASE_URL"),
    ),
)
