"""Shabbat scheduler for trading pause.

Calculates sunset times and manages trading pauses from
Friday sunset to Saturday sunset.
"""

from datetime import datetime, timedelta
from typing import Optional

import pytz
from astral import LocationInfo
from astral.sun import sun
import structlog

logger = structlog.get_logger()


class ShabbatScheduler:
    """Scheduler for Shabbat trading pause.

    Calculates sunset times based on geographic location and determines
    when to pause and resume trading.
    """

    def __init__(
        self,
        latitude: float = -23.5505,  # São Paulo default
        longitude: float = -46.6333,
        timezone: str = "America/Sao_Paulo",
        buffer_minutes: int = 18,  # Start pause 18 minutes before sunset
    ) -> None:
        """Initialize the scheduler.

        Args:
            latitude: Geographic latitude
            longitude: Geographic longitude
            timezone: Timezone name
            buffer_minutes: Minutes before sunset to start pause
        """
        self.location = LocationInfo(
            name="Trading Location",
            region="",
            timezone=timezone,
            latitude=latitude,
            longitude=longitude,
        )
        self.tz = pytz.timezone(timezone)
        self.buffer = timedelta(minutes=buffer_minutes)

        logger.info(
            "shabbat_scheduler_initialized",
            latitude=latitude,
            longitude=longitude,
            timezone=timezone,
        )

    def _get_sun_times(self, date: datetime) -> dict:
        """Get sun times for a specific date."""
        return sun(self.location.observer, date=date.date(), tzinfo=self.tz)

    def _get_friday_sunset(self, reference: Optional[datetime] = None) -> datetime:
        """Get the sunset time for the current or next Friday."""
        now = reference or datetime.now(self.tz)

        # Find the current or next Friday
        days_until_friday = (4 - now.weekday()) % 7
        if days_until_friday == 0 and now.hour >= 12:
            # It's Friday afternoon, use today
            friday = now.date()
        else:
            friday = now.date() + timedelta(days=days_until_friday)

        sun_times = sun(self.location.observer, date=friday, tzinfo=self.tz)
        return sun_times["sunset"] - self.buffer

    def _get_saturday_sunset(self, reference: Optional[datetime] = None) -> datetime:
        """Get the sunset time for the current or next Saturday."""
        now = reference or datetime.now(self.tz)

        # Find the current or next Saturday
        days_until_saturday = (5 - now.weekday()) % 7
        saturday = now.date() + timedelta(days=days_until_saturday)

        sun_times = sun(self.location.observer, date=saturday, tzinfo=self.tz)
        return sun_times["sunset"]

    def is_shabbat(self, reference: Optional[datetime] = None) -> bool:
        """Check if we are currently in the Shabbat pause period.

        Args:
            reference: Reference time (defaults to now)

        Returns:
            True if currently in Shabbat period
        """
        now = reference or datetime.now(self.tz)

        # Get this week's Friday and Saturday sunsets
        friday_sunset = self._get_friday_sunset(now)
        saturday_sunset = self._get_saturday_sunset(now)

        # Handle week transition
        if now.weekday() == 6:  # Sunday
            # Check if we're still in last week's Shabbat
            last_saturday = now - timedelta(days=1)
            last_saturday_sunset = self._get_saturday_sunset(last_saturday - timedelta(days=6))
            if now < last_saturday_sunset:
                return True
            return False

        # Check if we're in the Shabbat window
        is_in_shabbat = friday_sunset <= now <= saturday_sunset

        if is_in_shabbat:
            logger.debug(
                "currently_in_shabbat",
                now=now.isoformat(),
                friday_sunset=friday_sunset.isoformat(),
                saturday_sunset=saturday_sunset.isoformat(),
            )

        return is_in_shabbat

    def next_pause_time(self, reference: Optional[datetime] = None) -> datetime:
        """Get the next Shabbat pause start time (Friday sunset).

        Args:
            reference: Reference time (defaults to now)

        Returns:
            Datetime of next pause start
        """
        now = reference or datetime.now(self.tz)
        friday_sunset = self._get_friday_sunset(now)

        if now >= friday_sunset:
            # Already past this Friday's sunset, get next Friday
            next_friday = now + timedelta(days=(7 - now.weekday() + 4) % 7 + 1)
            return self._get_friday_sunset(next_friday)

        return friday_sunset

    def next_resume_time(self, reference: Optional[datetime] = None) -> datetime:
        """Get the next trading resume time (Saturday sunset).

        Args:
            reference: Reference time (defaults to now)

        Returns:
            Datetime of next resume time
        """
        now = reference or datetime.now(self.tz)
        saturday_sunset = self._get_saturday_sunset(now)

        if now >= saturday_sunset:
            # Already past this Saturday's sunset, get next Saturday
            next_saturday = now + timedelta(days=(7 - now.weekday() + 5) % 7 + 1)
            return self._get_saturday_sunset(next_saturday)

        return saturday_sunset

    def next_event(self, reference: Optional[datetime] = None) -> datetime:
        """Get the next scheduler event (either pause or resume).

        Args:
            reference: Reference time (defaults to now)

        Returns:
            Datetime of next event
        """
        now = reference or datetime.now(self.tz)

        if self.is_shabbat(now):
            return self.next_resume_time(now)
        else:
            return self.next_pause_time(now)

    def time_until_next_event(self, reference: Optional[datetime] = None) -> timedelta:
        """Get time remaining until next event.

        Args:
            reference: Reference time (defaults to now)

        Returns:
            Timedelta until next event
        """
        now = reference or datetime.now(self.tz)
        return self.next_event(now) - now

    def get_schedule_info(self, reference: Optional[datetime] = None) -> dict:
        """Get detailed schedule information.

        Args:
            reference: Reference time (defaults to now)

        Returns:
            Dictionary with schedule details
        """
        now = reference or datetime.now(self.tz)

        return {
            "current_time": now.isoformat(),
            "is_shabbat": self.is_shabbat(now),
            "next_pause": self.next_pause_time(now).isoformat(),
            "next_resume": self.next_resume_time(now).isoformat(),
            "next_event": self.next_event(now).isoformat(),
            "time_until_next_event": str(self.time_until_next_event(now)),
        }
