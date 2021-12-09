from dataclasses import dataclass
import re
import aiohttp
import asyncio
import time
from datetime import datetime
import json5
from bot.db.models import Outage
from bot.config import config

__all__ = ("iec_api", "IECOutageStatus", "IECStreet", "IECCity")


@dataclass
class IECOutageStatus:
    """
    Represents get_outage_for_address response
    """

    is_active_incident: bool
    is_planned_outage: bool
    outage_time: datetime
    incident_id: int
    incident_source_code: int
    incident_source_desc: str
    incident_status_code: int
    incident_status_name: str
    incident_trouble_code: int
    incident_trouble_desc: str
    delay_cause_code: int
    delay_cause_desc: str
    crew_name: str
    last_crew_assignment_time: datetime
    restore_est: datetime

    def get_outage_model(self) -> Outage:
        """
        Makes a db model
        from partial outage response

        :return: db Outage model
        :rtype: Outage
        """
        return Outage(
            is_planned=self.is_planned_outage,
            start_time=self.outage_time,
            incident_id=self.incident_id,
            incident_source_code=self.incident_source_code,
            incident_source_desc=self.incident_source_desc,
            incident_status_code=self.incident_status_code,
            incident_trouble_code=self.incident_trouble_code,
            incident_trouble_desc=self.incident_trouble_desc,
            delay_cause_code=self.delay_cause_code,
            delay_cause_desc=self.delay_cause_desc,
            crew_name=self.crew_name,
            crew_assigned_time=self.last_crew_assignment_time,
            restore_est=self.restore_est,
        )


@dataclass
class IECStreet:
    """
    Represents get_streets_for_city response
    """

    id: int
    name: str


@dataclass
class IECCity:
    """
    Represents get_cities response
    """

    id: int
    name: str
    mahoz_id: int
    mahoz_name: str
    distinct_name: int
    distinct_id: str
    loaded_streets: list[IECStreet]


class IECApi:
    """
    IEC Api client.
    Only one intance since it manges and
    slows down requests to mit the iec
    rate limiting (IP)
    """

    def __init__(self) -> None:
        self.session: aiohttp.ClientSession = None
        self._rbzid: str = None
        self._rbzid_updated_time: int = None
        self._rate_limit_next_req_ts = time.time()
        self.max_rqps = 1.1
        pass

    async def _delay_if_needed(self):
        """
        Sleep until a req can be made
        keeps track of the requests times and
        sleeps if needed to comply with the
        max req per sec that can be made
        """
        now = time.time()
        if now >= self._rate_limit_next_req_ts:
            self._rate_limit_next_req_ts = now + self.max_rqps
            return

        self._rate_limit_next_req_ts = self._rate_limit_next_req_ts + self.max_rqps
        diff = self._rate_limit_next_req_ts - now
        return await asyncio.sleep(diff)

    async def __create_session(self):
        """
        Creates an aiohttp session
        """
        self.session = aiohttp.ClientSession(
            base_url=config.iec.base_url,
            connector=aiohttp.TCPConnector(ssl=False),
        )

    async def request(self, method: str, path: str, **kwargs) -> aiohttp.ClientResponse:
        """ """
        """
        Request the api

        :param method: HTTP method (GET,POST,DELETE, etc..) 
        :type method: str
        :param path: path not including base
        :type path: str

        :return: the request response
        :rtype: ClientResponse
        """
        await self._delay_if_needed()
        if not self.session:
            await self.__create_session()
        return await self.session.request(method, path, **kwargs)

    async def __req_rbzid_cookie(self) -> str:
        """
        Gets rbzid from IEC server
        used to send other requests

        :return: rbzid
        :rtype: str
        """
        resp = await self.request(
            "GET",
            "/IecServicesHandler.ashx?allRes=true&a=FindStreets",
        )
        raw = await resp.text()
        js_obj = "{" + re.search("(?<=window\.rbzns={)(.*)(?=};)", raw)[0] + "}"
        return json5.loads(js_obj)["seed"]

    async def get_rbzid(self) -> str:
        """
        Gets rbzid cookie from cache
        or requests a new one

        :return: rbzid
        :rtype: str
        """
        update_every = 30 * 60
        if not self._rbzid or self._rbzid_updated_time - time.time() > update_every:
            self._rbzid = await self.__req_rbzid_cookie()
            self._rbzid_updated_time = time.time()
        return self._rbzid

    @staticmethod
    def is_unknown_name_id(id: int, name: str):
        return id == 999 or name == "לא ידוע"

    async def get_cities(self, q="") -> list[IECCity]:
        """
        Gets cities from IEC Database

        :param q: query to search by name, defaults to ""
        :type q: str, optional
        :return: list of IECCity
        :rtype: list[IECCity]
        """

        def normilize_city(city: dict) -> IECCity:
            return IECCity(
                id=city["K_YESHUV"],
                name=city["YESHUV"],
                mahoz_id=city["K_MAHOZ"],
                mahoz_name=city["MAHOZ"],
                distinct_id=city["K_EZOR"],
                distinct_name=city["EZOR"],
                loaded_streets=[],
            )

        params = {"a": "RetrieveCitiesEx", "city": q}
        resp = await self.request(
            "GET", "/pages/IecServicesHandler.ashx", params=params
        )
        raw_cities = await resp.json()
        return [
            normilize_city(c)
            for c in raw_cities[:1500]
            if not self.is_unknown_name_id(c["K_YESHUV"], c["YESHUV"])
            and "רמת גן" in c["YESHUV"]
        ]

    async def get_streets_for_city(self, city_id: int, q="") -> list[IECStreet]:
        """
        Gets streets for city
        from IEC Database

        :param city_id: the iec city id
        :type city_id: int
        :param q: query to search by name, defaults to ""
        :type q: str, optional
        :return: list of IECStreet
        :rtype: list[IECStreet]
        """

        def normilize_street(street: dict) -> IECStreet:
            return IECStreet(id=street["K_REHOV"], name=street["REHOV"])

        rbzid = await self.get_rbzid()
        params = {"a": "FindStreets", "allRes": "true", "cityID": city_id, "street": q}
        resp = await self.request(
            "GET",
            "/pages/IecServicesHandler.ashx",
            params=params,
            headers={"cookie": "rbzid=" + rbzid},
        )
        raw_streets = await resp.json()
        return [
            normilize_street(s)
            for s in raw_streets
            if not self.is_unknown_name_id(s["K_REHOV"], s["REHOV"])
        ]

    async def get_outage_for_address(
        self, city_id: int, district_id: int, street_id: int, home_num: int
    ) -> IECOutageStatus:
        """
        Gets outage status from IEC
        database

        :param city_id: the iec city id
        :type city_id: int
        :param district_id: the iec city district id
        :type district_id: int
        :param street_id: the iec street id
        :type street_id: int
        :param home_num: the house number
        :type home_num: int
        :return: the outage status
        :rtype: IECOutageStatus
        """
        params = {
            "a": "CheckInterruptByAddress",
            "cityID": city_id,
            # "Districtid": district_id,
            "streetID": street_id,
            "homeNum": home_num,
            "guid": int(time.time()),
        }
        if district_id:
            params["Districtid"] = district_id

        def normilize_outage(outage: dict):
            restore_est_matches = re.search(
                r"\d{2}:\d{2}[ X]\d{2}\/\d{2}\/\d{4}",
                outage.get("IncidentStatusName", ""),
            )
            restore_est = (
                datetime.strptime(restore_est_matches[0], "%H:%M %d/%m/%Y")
                if restore_est_matches
                else None
            )

            return IECOutageStatus(
                is_active_incident=outage.get("IsActiveIncident"),
                is_planned_outage=outage.get("IsPlannedOutage"),
                outage_time=datetime.strptime(
                    outage["Time_Outage"], "%Y-%m-%dT%H:%M:%S"
                )
                if outage["Time_OutageSpecified"]
                else None,
                incident_id=outage.get("IncidentID") or None,
                incident_source_code=outage.get("IncidentSourceCode") or None,
                incident_source_desc=outage.get("IncidentSourceDesc"),
                incident_status_code=outage.get("IncidentStatusCode") or None,
                incident_status_name=outage.get("IncidentStatusName"),
                incident_trouble_code=outage.get("IncidentTroubleCode") or None,
                incident_trouble_desc=outage.get("IncidentTroubleDesc"),
                delay_cause_code=outage.get("DelayCauseCode") or None,
                delay_cause_desc=outage.get("DelayCauseDesc"),
                crew_name=outage.get("CrewName"),
                last_crew_assignment_time=datetime.strptime(
                    outage["LastCrewAssignment"], "%Y-%m-%dT%H:%M:%S"
                )
                if outage["LastCrewAssignmentSpecified"]
                else None,
                restore_est=restore_est,
            )

        resp = await self.request(
            "GET", "/pages/IecServicesHandler.ashx", params=params, timeout=20
        )
        raw_outage = await resp.json()
        return normilize_outage(raw_outage)


iec_api = IECApi()
