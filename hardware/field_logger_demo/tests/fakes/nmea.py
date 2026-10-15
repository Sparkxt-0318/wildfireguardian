"""NMEA sentences for the host fake device's '!NMEA' input (one GNSS epoch = GGA, RMC and GSA, then GSV)."""


def ck(body):
    c = 0
    for ch in body:
        c ^= ord(ch)
    return "$%s*%02X" % (body, c)


def _ll(lat, lon):
    la, lo = abs(lat), abs(lon)
    return ("%02d%07.4f,%s" % (int(la), (la - int(la)) * 60, "N" if lat >= 0 else "S"),
            "%03d%07.4f,%s" % (int(lo), (lo - int(lo)) * 60, "E" if lon >= 0 else "W"))


def epoch(t_s, lat=None, lon=None, speed_mps=0.0, course=90.0, date="131026"):
    """Sentences of one epoch at t_s seconds after 00:00 UTC; no position when lat is None."""
    hms = "%02d%02d%06.3f" % (int(t_s // 3600) % 24, int(t_s // 60) % 60, t_s % 60)
    if lat is None:
        return [ck("GNGGA,%s,,,,,0,03,,,M,,M,," % hms), ck("GNRMC,%s,V,,,,,,,%s,,,N,V" % (hms, date)),
                ck("GNGSA,A,1,,,,,,,,,,,,,99.99,99.99,99.99,1"), ck("GPGSV,1,1,03,05,41,140,,12,22,301,,21,63,040,")]
    a, b = _ll(lat, lon)
    return [ck("GNGGA,%s,%s,%s,1,10,0.9,31.0,M,8.9,M,," % (hms, a, b)),
            ck("GNRMC,%s,A,%s,%s,%.3f,%.1f,%s,,,A,V" % (hms, a, b, speed_mps / 0.514444, course, date)),
            ck("GNGSA,A,3,01,02,03,04,05,06,,,,,,,1.8,0.9,1.4,1"),
            ck("GPGSV,2,1,07,05,41,140,38,12,22,301,31,21,63,040,42,25,15,210,27"),
            ck("GPGSV,2,2,07,29,55,095,40,31,08,330,,32,33,260,35")]
