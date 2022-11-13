from upnpclient.ssdp import (
    ST_ALL, ST_ROOTDEVICE, SSDP_MX, SSDP_TARGET,
    ssdp_request, 
    datetime, timedelta,
    get_addresses_ipv4,
    socket,
    select,
    _getLogger,
    re,
    Device as _Device,
)


class Entry(object):
    def __init__(self, location, iface_ip):
        self.location = location
        self.iface_ip = iface_ip

class Device(_Device):
    def __init__(self, location, device_name=None, ignore_urlbase=False, http_auth=None, http_headers=None, iface_ip=None):
        super().__init__(location, device_name, ignore_urlbase, http_auth, http_headers) 
        self.iface_ip = iface_ip


def scan(timeout=5):
    urls = []
    sockets = []
    ssdp_requests = [ssdp_request(ST_ALL), ssdp_request(ST_ROOTDEVICE)]
    stop_wait = datetime.now() + timedelta(seconds=timeout)

    for addr in get_addresses_ipv4():
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, SSDP_MX)
            sock.bind((addr, 0))
            sockets.append(sock)
        except socket.error:
            pass

    for sock in [s for s in sockets]:
        try:
            for req in ssdp_requests:
                sock.sendto(req, SSDP_TARGET)
            sock.setblocking(False)
        except socket.error:
            sockets.remove(sock)
            sock.close()
    try:
        while sockets:
            time_diff = stop_wait - datetime.now()
            seconds_left = time_diff.total_seconds()
            if seconds_left <= 0:
                break

            ready = select.select(sockets, [], [], seconds_left)[0]

            for sock in ready:
                try:
                    data, address = sock.recvfrom(1024)
                    response = data.decode("utf-8")
                except UnicodeDecodeError:
                    _getLogger(__name__).debug(
                        "Ignoring invalid unicode response from %s", address
                    )
                    continue
                except socket.error:
                    _getLogger(__name__).exception(
                        "Socket error while discovering SSDP devices"
                    )
                    sockets.remove(sock)
                    sock.close()
                    continue
                locations = re.findall(
                    r"LOCATION: *(?P<url>\S+)\s+", response, re.IGNORECASE
                )
                if locations and len(locations) > 0:
                    urls.append(Entry(locations[0], sock.getsockname()[0]))

    finally:
        for s in sockets:
            s.close()

    return set(urls)


def discover(timeout=5):
    """
    Convenience method to discover UPnP devices on the network. Returns a
    list of `upnp.Device` instances. Any invalid servers are silently
    ignored.
    """
    devices = {}
    for entry in scan(timeout):
        if entry.location in devices:
            continue
        try:
            devices[entry.location] = Device(entry.location, iface_ip=entry.iface_ip)
        except Exception as exc:
            log = _getLogger("ssdp")
            log.error("Error '%s' for %s", exc, entry)
    return list(devices.values())