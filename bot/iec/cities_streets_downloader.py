import asyncio
from bot.db.models import City, Street
from bot.iec.api import IECCity, iec_api


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


async def download_and_fill_db_cities_streets() -> tuple:
    """
    Downloads all cities and streets
    and fills database if not already
    in it

    :return: (added_cities_count, added_streets_count)
    :rtype: tuple
    """
    cities = await get_all_cities_with_streets()

    added_cities_count = 0
    added_streets_count = 0

    for city in cities:
        db_city, added_city = await City.get_or_create(
            name=city.name, id=city.id, district_id=city.distinct_id
        )
        if added_city:
            added_cities_count += 1

        for street in city.loaded_streets:
            db_street, added_street = await Street.get_or_create(
                name=street.name, id=street.id, city=db_city
            )
            if added_street:
                added_streets_count += 1

    return (added_cities_count, added_streets_count)
