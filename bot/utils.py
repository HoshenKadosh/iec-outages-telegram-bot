from datetime import datetime
from bot.db.models import City, Outage, Street
from bot.iec.api import IECOutageStatus


def time_diff_between_two_dates_text(d1: datetime, d2: datetime) -> str:
    """
    Relative time from 2 dates

    :param d1: date 1
    :type d1: datetime
    :param d2: date 2
    :type d2: datetime
    :return: exmple: 3 שעות ו22 דקות
    :rtype: str
    """

    def get_min(m):
        return "דקה" if m <= 2 else f"{int(m)} דקות"

    def get_hours(h):
        return "שעה" if h < 2 else f"{int(h)} שעות"

    diff = round((d1 - d2).seconds / 60)
    if diff < 60:
        return get_min(diff)

    has_m = diff % 60 != 0
    if has_m:
        return get_hours(diff / 60) + " ו" + get_min(diff % 60)

    return get_hours(diff / 60)


def detail_text_from_outage(outage: Outage, full_address_name: str) -> str:
    """
    Construct a detail outage text from outage
    and full address.

    example with all fields:
    '
    הפסקת חשמל בבר כוכבא 5, אשקלון

    התחילה ב: 05/12 11:19
    צפי לסיום: 05/12 14:19
    מקור מדווח: DMS (מערכת ניתור אוט')
    התקלה: מנגנון גיבוי
    צוות מטפל: איציק, שי (05/12 11:54)
    סיבת עיכוב: עומס תקלות חריג
    '

    :param outage: db outage model
    :type outage: Outage
    :param full_address_name: full address formated
    :type full_address_name: str
    :return: [description]
    :rtype: str
    """
    planned = "<b>מתוכננת </b>" if outage.is_planned else ""

    text = f"הפסקת חשמל {planned}ב{full_address_name}"
    text += "\n\n"

    text += (
        "<b>התחילה ב:</b> " + datetime.strftime(outage.start_time, "%d/%m %H:%M") + "\n"
    )

    if outage.restore_est:
        text += (
            "<b>צפי לסיום:</b> "
            + datetime.strftime(outage.restore_est, "%d/%m %H:%M")
            + "\n"
        )

    if outage.incident_source_desc:
        text += (
            "<b>מקור מדווח:</b> "
            + outage.incident_source_desc.replace("DMS", "DMS (מערכת ניתור אוט')")
            + "\n"
        )

    if outage.incident_trouble_desc != "אחר":
        text += "<b>התקלה:</b> " + outage.incident_trouble_desc + "\n"

    if outage.crew_name:
        crew_assigned_time = (
            " (" + datetime.strftime(outage.crew_assigned_time, "%d/%m %H:%M") + ")"
            if outage.crew_assigned_time
            else ""
        )
        text += "<b>צוות מטפל:</b> " + outage.crew_name + crew_assigned_time + "\n"

    if outage.delay_cause_desc:
        text += "<b>סיבת עיכוב:</b> " + outage.delay_cause_desc

    return text


def compare_db_outage_outage_status(
    db_outage: Outage, outage_status: IECOutageStatus
) -> bool:
    """
    Compares all attributes between
    IECOutageStatus and a db Outage model

    :param db_outage: db Outage model
    :type db_outage: Outage
    :param outage_status: iec outage status resp
    :type outage_status: IECOutageStatus
    :return: True if all attributes are the same else False
    :rtype: bool
    """
    return (
        db_outage.is_planned == outage_status.is_planned_outage
        and db_outage.start_time == outage_status.outage_time
        and db_outage.incident_id == outage_status.incident_id
        and db_outage.incident_source_code == outage_status.incident_source_code
        and db_outage.incident_source_desc == outage_status.incident_source_desc
        and db_outage.incident_status_code == outage_status.incident_status_code
        and db_outage.incident_trouble_code == outage_status.incident_trouble_code
        and db_outage.incident_trouble_desc == outage_status.incident_trouble_desc
        and db_outage.delay_cause_code == outage_status.delay_cause_code
        and db_outage.delay_cause_desc == outage_status.delay_cause_desc
        and db_outage.crew_name == outage_status.crew_name
        and db_outage.crew_assigned_time == outage_status.last_crew_assignment_time
        and db_outage.restore_est == outage_status.restore_est
    )


async def get_full_address_formated(city_id: int, street_id: int, home_num: str) -> str:
    """
    Formats an address string from city,street ids and home
    example: בר כוכבא 5, אשקלון

    :param city_id: [description]
    :type city_id: int
    :param street_id: [description]
    :type street_id: int
    :param home_num: [description]
    :type home_num: str
    :return: '{street.name} {home_num}, {city.name}'
    :rtype: str
    """
    city = await City.filter(id=city_id).first()
    street = await Street.filter(id=street_id).first()
    return f"{street.name} {home_num}, {city.name}"
