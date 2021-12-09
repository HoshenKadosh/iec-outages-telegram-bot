import asyncio
from asyncio.tasks import Task
from dataclasses import dataclass
import logging
from typing import Union
from aiogram.bot.bot import Bot
from aiogram.types.message import Message
from datetime import datetime
from bot.db.models import Address, Outage
from bot.utils import (
    compare_db_outage_outage_status,
    detail_text_from_outage,
    get_full_address_formated,
    time_diff_between_two_dates_text,
)
from bot.iec.api import IECOutageStatus, iec_api


@dataclass
class ActiveOutageData:
    db_outage: Outage
    telegram_last_sent_text: str
    telegram_last_msg_ids: dict[int:int]
    full_address_name: str
    city_id: int
    street_id: int
    home_num: int
    district_id: int


# @dataclass
# class AddressIds:
#     city_id: int
#     street_id: int
#     home_num: int
#     city_district_id: int


# TODO - LOAD ACTIVE DATA FROM DB WHEN STARTING


class OutagesMonitor:
    """
    Monitors outages from addresses
    and sends message to the users
    with the info.

    also saves to the db.
    """

    @staticmethod
    def gen_outage_key(city_id: int, street_id: int, home_num: int) -> str:
        """
        Genrates a key based on city_id,street_id,home_num
        {city_id}-{street_id}-{home_num}

        :param city_id: iec city id
        :type city_id: int
        :param street_id: iec street id
        :type street_id: int
        :param home_num: the home number
        :type home_num: int
        :return: {city_id}-{street_id}-{home_num}
        :rtype: str
        """
        return f"{city_id}-{street_id}-{home_num}"

    async def get_addresses_to_check(self) -> set[tuple[int, int, int, int]]:
        """
        Gets from the db unique addresses
        for checking their status, and all the
        active outages to know when they end.

        :return: set[(city_id, district_id,street_id,home_num)]
        :rtype: set[tuple[int, int, int, int]]
        """
        raw = (
            await Address.all()
            .select_related(
                "city",
            )
            .distinct()
            .values("city_id", "street_id", "home_num", district_id="city__district_id")
        )
        set = {
            (a["city_id"], a["district_id"], a["street_id"], a["home_num"]) for a in raw
        }
        for outage_data in self.active_outages.values():
            outage_data: ActiveOutageData
            set.add(
                (
                    outage_data.city_id,
                    outage_data.district_id,
                    outage_data.street_id,
                    outage_data.home_num,
                )
            )
        return set

    async def get_registered_user_ids_for_addresses(
        self, city_id: int, street_id: int, home_num: int
    ) -> list[int]:
        """
        Gets from the db all telegram user ids
        that registred for a specific address

        :param city_id: iec city id
        :type city_id: int
        :param street_id: iec street id
        :type street_id: int
        :param home_num: home number
        :type home_num: int
        :return: list of telegram user ids
        :rtype: list[int]
        """
        return [
            a["user_id"]
            for a in (
                await Address.filter(
                    city_id=city_id, street_id=street_id, home_num=home_num
                )
                .all()
                .values("user_id")
            )
        ]

    async def send_telegram_outage_msg(
        self,
        user_ids: int,
        active_outage_data: ActiveOutageData,
    ):
        """
        Send a telegram messsage with the
        outage details.
        Allways deletes the last msg and
        sends new one insted, in case of
        an update.

        :param user_ids: telegram user ids
        :type user_ids: int
        :param active_outage_data: saved outage data
        :type active_outage_data: ActiveOutageData
        """
        if len(user_ids) == 0:
            return

        outage = active_outage_data.db_outage
        add_name = active_outage_data.full_address_name
        text = detail_text_from_outage(outage, add_name)

        if active_outage_data.telegram_last_sent_text == text:
            return

        active_outage_data.telegram_last_sent_text = text

        # delete
        delete_tasks = [
            self.telegram_bot.delete_message(
                uid, active_outage_data.telegram_last_msg_ids.get(uid, "-1")
            )
            for uid in user_ids
        ]
        await asyncio.gather(*delete_tasks, return_exceptions=True)
        # delete

        tasks = [self.telegram_bot.send_message(uid, text) for uid in user_ids]
        msgs_results: Union[Message, Exception] = await asyncio.gather(
            *tasks, return_exceptions=True
        )

        active_outage_data.telegram_last_msg_ids = {
            m.chat.id: m.message_id for m in msgs_results if type(m) == Message
        }

    async def send_telegram_end_msg(
        self, user_ids: list[int], active_outage_data: ActiveOutageData
    ):
        """
        Sends a telegram message with
        the outage total time and start, end
        times.

        :param user_ids: telegram user ids
        :type user_ids: list[int]
        :param active_outage_data: saved outage data
        :type active_outage_data: ActiveOutageData
        """

        outage = active_outage_data.db_outage
        total_time = time_diff_between_two_dates_text(
            outage.end_time, outage.start_time
        )
        start = datetime.strftime(outage.start_time, "%H:%M %d/%m/%y")
        end = datetime.strftime(outage.end_time, "%H:%M %d/%m/%y")
        text = f"החשמל חזר ב{active_outage_data.full_address_name}\n\n"
        text += f"<b>משך:</b> {total_time}\n"
        text += f"<b>התחלה:</b> {start}\n"
        text += f"<b>סיום:</b> {end}"

        tasks = [self.telegram_bot.send_message(uid, text) for uid in user_ids]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def check_and_process(
        self, city_id: int, district_id: int, street_id: int, home_num: int
    ):
        """
        Checks for outage at a specific address,
        and creates, updates, or ends it

        :param city_id: iec city id
        :type city_id: int
        :param district_id: iec city district id
        :type district_id: int
        :param street_id: iec street id
        :type street_id: int
        :param home_num: home number
        :type home_num: int
        """
        outage = await iec_api.get_outage_for_address(
            city_id, district_id, street_id, home_num
        )
        ongoing_power_outage = outage.is_active_incident or outage.is_planned_outage

        outage_key = self.gen_outage_key(city_id, street_id, home_num)

        # no outage, we dont have to do anything
        if not ongoing_power_outage and outage_key not in self.active_outages:
            return

        # outage allready, check for update
        if ongoing_power_outage and outage_key in self.active_outages:
            active_outage_data: ActiveOutageData = self.active_outages[outage_key]
            await self._process_outage_update_if_needed(
                outage, active_outage_data, city_id, street_id, home_num
            )

        # first time seen outage
        if ongoing_power_outage and outage_key not in self.active_outages:
            await self._process_new_outage(
                outage, outage_key, city_id, district_id, street_id, home_num
            )
            self.logger.info("New outage detected: ",outage_key)

        # outage ended
        if not ongoing_power_outage and outage_key in self.active_outages:
            await self._process_outage_ended(outage_key, city_id, street_id, home_num)
            self.logger.info("Outage end detected: ",outage_key)

    async def _process_outage_update_if_needed(
        self,
        outage: IECOutageStatus,
        active_outage_data: ActiveOutageData,
        city_id: int,
        street_id: int,
        home_num: int,
    ):
        """
        Checks if outage has been updated
        and saves to db and sends msg

        :param outage: outage status iec
        :type outage: IECOutageStatus
        :param active_outage_data: active outage data
        :type active_outage_data: ActiveOutageData
        :param city_id: iec city id
        :type city_id: int
        :param street_id: iec street id
        :type street_id: int
        :param home_num: iec home number
        :type home_num: int
        """
        db_outage = active_outage_data.db_outage
        if compare_db_outage_outage_status(db_outage, outage):
            return
        db_outage.is_planned = outage.is_planned_outage
        db_outage.start_time = outage.outage_time
        db_outage.incident_id = outage.incident_id
        db_outage.incident_source_code = outage.incident_source_code
        db_outage.incident_source_desc = outage.incident_source_desc
        db_outage.incident_status_code = outage.incident_status_code
        db_outage.incident_trouble_code = outage.incident_trouble_code
        db_outage.incident_trouble_desc = outage.incident_trouble_desc
        db_outage.delay_cause_code = outage.delay_cause_code
        db_outage.delay_cause_desc = outage.delay_cause_desc
        db_outage.crew_name = outage.crew_name
        db_outage.crew_assigned_time = outage.last_crew_assignment_time
        db_outage.restore_est = outage.restore_est
        await db_outage.save()

        user_ids = await self.get_registered_user_ids_for_addresses(
            city_id, street_id, home_num
        )

        await self.send_telegram_outage_msg(user_ids, active_outage_data)

    async def _process_new_outage(
        self,
        outage: IECOutageStatus,
        outage_key: str,
        city_id: int,
        district_id: int,
        street_id: int,
        home_num: int,
    ):
        """
        Procsesses a new outage.
        Creates a db model,
        addes to active_outages
        sends telegram outage msg

        :param outage: outage status iec
        :type outage: IECOutageStatus
        :param outage_key: gen outage key
        :type outage_key: str
        :param city_id: iec city id
        :type city_id: int
        :param district_id: iec city district id
        :type district_id: int
        :param street_id: iec street id
        :type street_id: int
        :param home_num: home number
        :type home_num: int
        """
        db_outage = await Outage.create(
            city_id=city_id,
            street_id=street_id,
            home_num=home_num,
            is_planned=outage.is_planned_outage,
            start_time=outage.outage_time,
            incident_id=outage.incident_id,
            incident_source_code=outage.incident_source_code,
            incident_source_desc=outage.incident_source_desc,
            incident_status_code=outage.incident_status_code,
            incident_trouble_code=outage.incident_trouble_code,
            incident_trouble_desc=outage.incident_trouble_desc,
            delay_cause_code=outage.delay_cause_code,
            delay_cause_desc=outage.delay_cause_desc,
            crew_name=outage.crew_name,
            crew_assigned_time=outage.last_crew_assignment_time,
            restore_est=outage.restore_est,
        )
        self.active_outages[outage_key] = ActiveOutageData(
            db_outage=db_outage,
            telegram_last_msg_ids={},
            telegram_last_sent_text="",
            full_address_name=await get_full_address_formated(
                city_id, street_id, home_num
            ),
            city_id=city_id,
            street_id=street_id,
            home_num=home_num,
            district_id=district_id,
        )

        user_ids = await self.get_registered_user_ids_for_addresses(
            city_id, street_id, home_num
        )

        await self.send_telegram_outage_msg(
            user_ids,
            self.active_outages[outage_key],
        )

    async def _process_outage_ended(
        self, outage_key: str, city_id: int, street_id: int, home_num: int
    ):
        """
        Processes an outage that ended.
        updates end time
        Calles telegram send end msg,
        removes from active_outages_data

        :param outage_key: a generated outage key
        :type outage_key: str
        :param city_id: iec city id
        :type city_id: int
        :param street_id: iec street id
        :type street_id: int
        :param home_num: home number
        :type home_num: int
        """
        active_outage_data: ActiveOutageData = self.active_outages[outage_key]
        active_outage_data.db_outage.end_time = datetime.now().replace(microsecond=0)
        await active_outage_data.db_outage.save()

        user_ids = await self.get_registered_user_ids_for_addresses(
            city_id, street_id, home_num
        )

        await self.send_telegram_end_msg(user_ids, active_outage_data)
        del self.active_outages[outage_key]

    def __init__(self, telegram_bot: Bot) -> None:
        self.active_outages: dict[str:ActiveOutageData] = dict()
        self.telegram_bot: Bot = telegram_bot
        self.monitor = False
        self.logger = logging.getLogger(__name__)
        pass

    async def start_monitoring(self):
        """
        Starts monitoring and checking all
        addresses in the background, and processes
        them
        """
        self.monitor = True
        self.logger.info("Started monitoring")
        while self.monitor:
            addresses = await self.get_addresses_to_check()
            self.logger.info(f"Checking {len(addresses)} addresses")
            tasks: list[Task] = []
            for add in addresses:
                city_id, district_id, street_id, home_num = add
                task = asyncio.ensure_future(
                    self.check_and_process(
                        city_id,
                        district_id,
                        street_id,
                        home_num,
                    )
                )
                tasks.append(task)
                await asyncio.sleep(1.2)

                if not self.monitor:
                    break

            await asyncio.gather(*tasks, return_exceptions=True)
            await asyncio.sleep(2)

    def stop_monitoring(self):
        """
        Stops addresses monitoring
        note: this can take some time
        """
        self.logger.info("Stoped monitoring")
        self.monitor = False
