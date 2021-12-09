import asyncio
from bot.db.models import City, Street
from bot.iec.api import IECCity, iec_api
import aiofiles
import json
from dacite import from_dict


async def get_all_cities_with_streets() -> list[IECCity]:
    """
    Gets all cities with all streets
    loadad at city.loaded_streets

    :return: cities with all streets loaded
    :rtype: list[IECCity]
    """
    all_cities = await iec_api.get_cities()

    for city in all_cities:
        city: IECCity

        for retry_num in range(3):
            try:
                city.loaded_streets = await iec_api.get_streets_for_city(city.id)
                break
            except Exception as e:
                if retry_num == 3:
                    print("canot load streets in to city", city.id, e)

        # to not hit rate limit
        await asyncio.sleep(1.2)

    return all_cities


async def get_all_cities_and_streets_file() -> list[IECCity]:
    """
    Loads cities and streets from
    local file

    :return: IECCity with loaded_cities
    :rtype: list[IECCity]
    """
    async with aiofiles.open("bot/iec/cities_streets.json", mode="r") as f:
        raw = await f.read()
        cities = json.loads(raw)
        return [from_dict(data_class=IECCity, data=c) for c in cities]


async def fill_db_cities_streets(download: bool) -> tuple:
    """
    Downloads all cities and streets
    and fills database if not already
    in it

    :return: (added_cities_count, added_streets_count)
    :rtype: tuple
    """
    cities = (
        await get_all_cities_with_streets()
        if download
        else await get_all_cities_and_streets_file()
    )

    added_cities_count = 0
    added_streets_count = 0

    for city in cities:
        db_city, added_city = await City.get_or_create(
            name=city.name, id=city.id, district_id=city.distinct_id
        )
        if added_city:
            added_cities_count += 1

        for street in city.loaded_streets:
            if not await Street.exists(id=street.id):
                await Street.create(name=street.name, id=street.id, city=db_city)
                added_streets_count += 1

    return (added_cities_count, added_streets_count)
