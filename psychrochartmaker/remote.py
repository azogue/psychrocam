"""
Support for an interface to work with a remote instance of Home Assistant.

If a connection error occurs while communicating with the API a
HomeAssistantError will be raised.

For more details about the Python API, please refer to the documentation at
https://home-assistant.io/developers/python_api/
"""
import datetime as dt
import enum
import json
import logging
import pytz
import re

from types import MappingProxyType
from typing import Optional, Dict, Any, List
import urllib.parse

# from aiohttp.hdrs import METH_GET, METH_POST, METH_DELETE, CONTENT_TYPE
from aiohttp.hdrs import METH_GET, CONTENT_TYPE
import requests


UTC = DEFAULT_TIME_ZONE = pytz.utc  # type: dt.tzinfo

ATTR_FRIENDLY_NAME = 'friendly_name'

CONTENT_TYPE_JSON = 'application/json'
HTTP_HEADER_HA_AUTH = 'X-HA-access'
SERVER_PORT = 8123

URL_API = '/api/'
URL_API_CONFIG = '/api/config'
URL_API_STATES = '/api/states'
URL_API_STATES_ENTITY = '/api/states/{}'
URL_API_EVENTS = '/api/events'
URL_API_EVENTS_EVENT = '/api/events/{}'
URL_API_SERVICES = '/api/services'
URL_API_SERVICES_SERVICE = '/api/services/{}/{}'


_LOGGER = logging.getLogger(__name__)

# Pattern for validating entity IDs (format: <domain>.<entity>)
ENTITY_ID_PATTERN = re.compile(r"^(\w+)\.(\w+)$")

# Copyright (c) Django Software Foundation and individual contributors.
# All rights reserved.
# https://github.com/django/django/blob/master/LICENSE
DATETIME_RE = re.compile(
    r'(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})'
    r'[T ](?P<hour>\d{1,2}):(?P<minute>\d{1,2})'
    r'(?::(?P<second>\d{1,2})(?:\.(?P<microsecond>\d{1,6})\d{0,6})?)?'
    r'(?P<tzinfo>Z|[+-]\d{2}(?::?\d{2})?)?$')


def parse_datetime(dt_str: str) -> Optional[dt.datetime]:
    """Parse a string and return a datetime.datetime.

    This function supports time zone offsets. When the input contains one,
    the output uses a timezone with a fixed offset from UTC.
    Raises ValueError if the input is well formatted but not a valid datetime.
    Returns None if the input isn't well formatted.
    """
    match = DATETIME_RE.match(dt_str)
    if not match:
        return None
    kws = match.groupdict()  # type: Dict[str, Any]
    if kws['microsecond']:
        kws['microsecond'] = kws['microsecond'].ljust(6, '0')
    tzinfo_str = kws.pop('tzinfo')

    # tzinfo = None  # type: # Optional[dt.tzinfo]
    if tzinfo_str == 'Z':
        tzinfo = UTC
    elif tzinfo_str is not None:
        offset_mins = int(tzinfo_str[-2:]) if len(tzinfo_str) > 3 else 0
        offset_hours = int(tzinfo_str[1:3])
        offset = dt.timedelta(hours=offset_hours, minutes=offset_mins)
        if tzinfo_str[0] == '-':
            offset = -offset
        tzinfo = dt.timezone(offset)
    else:
        tzinfo = None
    kws = {k: int(v) for k, v in kws.items() if v is not None}
    kws['tzinfo'] = tzinfo
    return dt.datetime(**kws)


def split_entity_id(entity_id: str) -> List[str]:
    """Split a state entity_id into domain, object_id."""
    return entity_id.split(".", 1)


def valid_entity_id(entity_id: str) -> bool:
    """Test if an entity ID is a valid format."""
    return ENTITY_ID_PATTERN.match(entity_id) is not None


def valid_state(state: str) -> bool:
    """Test if a state is valid."""
    return len(state) < 256


class HomeAssistantError(Exception):
    """General Home Assistant exception occurred."""

    pass


class InvalidEntityFormatError(HomeAssistantError):
    """When an invalid formatted entity is encountered."""

    pass


class InvalidStateError(HomeAssistantError):
    """When an invalid state is encountered."""

    pass


def as_local(dattim: dt.datetime) -> dt.datetime:
    """Convert a UTC datetime object to local time zone."""
    if dattim.tzinfo == DEFAULT_TIME_ZONE:
        return dattim
    elif dattim.tzinfo is None:
        dattim = UTC.localize(dattim)

    return dattim.astimezone(DEFAULT_TIME_ZONE)


def repr_helper(inp: Any) -> str:
    """Help creating a more readable string representation of objects."""
    if isinstance(inp, (dict, MappingProxyType)):
        return ", ".join(
            repr_helper(key)+"="+repr_helper(item) for key, item
            in inp.items())
    elif isinstance(inp, dt.datetime):
        return as_local(inp).isoformat()

    return str(inp)


class State(object):
    """Object to represent a state within the state machine.

    entity_id: the entity that is represented.
    state: the state of the entity
    attributes: extra information on entity and state
    last_changed: last time the state was changed, not the attributes.
    last_updated: last time this object was updated.
    """

    __slots__ = ['entity_id', 'state', 'attributes',
                 'last_changed', 'last_updated']

    def __init__(self, entity_id, state, attributes=None, last_changed=None,
                 last_updated=None):
        """Initialize a new state."""
        state = str(state)

        if not valid_entity_id(entity_id):
            raise InvalidEntityFormatError((
                "Invalid entity id encountered: {}. "
                "Format should be <domain>.<object_id>").format(entity_id))

        if not valid_state(state):
            raise InvalidStateError((
                "Invalid state encountered for entity id: {}. "
                "State max length is 255 characters.").format(entity_id))

        self.entity_id = entity_id.lower()
        self.state = state
        self.attributes = MappingProxyType(attributes or {})
        self.last_updated = last_updated or dt.datetime.now(UTC)
        self.last_changed = last_changed or self.last_updated

    @property
    def domain(self):
        """Domain of this state."""
        return split_entity_id(self.entity_id)[0]

    @property
    def object_id(self):
        """Object id of this state."""
        return split_entity_id(self.entity_id)[1]

    @property
    def name(self):
        """Name of this state."""
        return (
            self.attributes.get(ATTR_FRIENDLY_NAME) or
            self.object_id.replace('_', ' '))

    def as_dict(self):
        """Return a dict representation of the State.

        Async friendly.

        To be used for JSON serialization.
        Ensures: state == State.from_dict(state.as_dict())
        """
        return {'entity_id': self.entity_id,
                'state': self.state,
                'attributes': dict(self.attributes),
                'last_changed': self.last_changed,
                'last_updated': self.last_updated}

    @classmethod
    def from_dict(cls, json_dict):
        """Initialize a state from a dict.

        Async friendly.

        Ensures: state == State.from_json_dict(state.to_json_dict())
        """
        if not (json_dict and 'entity_id' in json_dict and
                'state' in json_dict):
            return None

        last_changed = json_dict.get('last_changed')

        if isinstance(last_changed, str):
            last_changed = parse_datetime(last_changed)

        last_updated = json_dict.get('last_updated')

        if isinstance(last_updated, str):
            last_updated = parse_datetime(last_updated)

        return cls(json_dict['entity_id'], json_dict['state'],
                   json_dict.get('attributes'), last_changed, last_updated)

    def __eq__(self, other):
        """Return the comparison of the state."""
        return (self.__class__ == other.__class__ and
                self.entity_id == other.entity_id and
                self.state == other.state and
                self.attributes == other.attributes)

    def __repr__(self):
        """Return the representation of the states."""
        attr = "; {}".format(repr_helper(self.attributes)) \
               if self.attributes else ""

        return "<state {}={}{} @ {}>".format(
            self.entity_id, self.state, attr,
            as_local(self.last_changed).isoformat())


class APIStatus(enum.Enum):
    """Representation of an API status."""

    OK = "ok"
    INVALID_PASSWORD = "invalid_password"
    CANNOT_CONNECT = "cannot_connect"
    UNKNOWN = "unknown"

    def __str__(self) -> str:
        """Return the state."""
        return self.value  # type: ignore


class API:
    """Object to pass around Home Assistant API location and credentials."""

    def __init__(self, host: str, api_password: Optional[str] = None,
                 port: Optional[int] = SERVER_PORT,
                 use_ssl: bool = False) -> None:
        """Init the API."""
        self.host = host
        self.port = port
        self.api_password = api_password

        if host.startswith(("http://", "https://")):
            self.base_url = host
        elif use_ssl:
            self.base_url = "https://{}".format(host)
        else:
            self.base_url = "http://{}".format(host)

        if port is not None:
            self.base_url += ':{}'.format(port)

        self.status = None  # type: Optional[APIStatus]
        self._headers = {CONTENT_TYPE: CONTENT_TYPE_JSON}

        if api_password is not None:
            self._headers[HTTP_HEADER_HA_AUTH] = api_password

    def validate_api(self, force_validate: bool = False) -> bool:
        """Test if we can communicate with the API."""
        if self.status is None or force_validate:
            self.status = validate_api(self)

        return self.status == APIStatus.OK

    def __call__(self, method: str, path: str, data: Optional[Dict] = None,
                 timeout: int = 5) -> requests.Response:
        """Make a call to the Home Assistant API."""
        if data is None:
            data_str = None
        else:
            data_str = json.dumps(data, cls=JSONEncoder)

        url = urllib.parse.urljoin(self.base_url, path)

        try:
            if method == METH_GET:
                return requests.get(
                    url, params=data_str, timeout=timeout,
                    headers=self._headers)

            return requests.request(
                method, url, data=data_str, timeout=timeout,
                headers=self._headers)

        except requests.exceptions.ConnectionError:
            _LOGGER.exception("Error connecting to server")
            raise HomeAssistantError("Error connecting to server")

        except requests.exceptions.Timeout:
            error = "Timeout when talking to {}".format(self.host)
            _LOGGER.error(error)
            raise HomeAssistantError(error)

    def __repr__(self) -> str:
        """Return the representation of the API."""
        return "<API({}, password: {})>".format(
            self.base_url, 'yes' if self.api_password is not None else 'no')


class JSONEncoder(json.JSONEncoder):
    """JSONEncoder that supports Home Assistant objects."""

    # pylint: disable=method-hidden
    def default(self, o: Any) -> Any:
        """Convert Home Assistant objects.

        Hand other objects to the original method.
        """
        if isinstance(o, dt.datetime):
            return o.isoformat()
        if isinstance(o, set):
            return list(o)
        if hasattr(o, 'as_dict'):
            return o.as_dict()

        return json.JSONEncoder.default(self, o)


def validate_api(api: API) -> APIStatus:
    """Make a call to validate API."""
    try:
        req = api(METH_GET, URL_API)

        if req.status_code == 200:
            return APIStatus.OK

        if req.status_code == 401:
            return APIStatus.INVALID_PASSWORD

        return APIStatus.UNKNOWN

    except HomeAssistantError:
        return APIStatus.CANNOT_CONNECT


def get_states(api: API) -> List[State]:
    """Query given API for all states."""
    try:
        req = api(METH_GET,
                  URL_API_STATES)

        return [State.from_dict(item) for
                item in req.json()]

    except (HomeAssistantError, ValueError, AttributeError):
        # ValueError if req.json() can't parse the json
        _LOGGER.error("Error fetching states")

        return []
