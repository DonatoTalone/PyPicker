"""
Parse datetime objects
"""

from __future__ import absolute_import, division, print_function, unicode_literals

import datetime
import numpy as np
from obspy import UTCDateTime

from hypo71py.model.type_check import is_string


__all__ = ['parse_datetime', 'UTCDateTime']


def parse_datetime(date_time):
	"""
	Convert different date-time specifications to obspy UTCDateTime

	:param date_time:
		str (ISO-formatted string or '(utc)now'),
		int or float(timestamp)
		instance of :class:`datetime.datetime`,
		instance of :class:`np.datetime64`,
		instance of :class:`obspy.UTCDateTime`

	:return:
		instance of :class:`obspy.UTCDateTime`
	"""
	if date_time in ('now', 'utcnow'):
		date_time = UTCDateTime()
	if isinstance(date_time, np.datetime64):
		date_time = str(date_time)
	if isinstance(date_time, (int, float, np.integer, np.floating)):
		## timestamp
		if not np.isnan(date_time):
			date_time = UTCDateTime(date_time)
	if is_string(date_time) or isinstance(date_time, (datetime.datetime, datetime.date)):
		date_time = UTCDateTime(date_time)
	if isinstance(date_time, UTCDateTime):
		return date_time
	else:
		raise Exception("Datetime %s not understood" % date_time)
