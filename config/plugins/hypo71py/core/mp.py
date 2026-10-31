# -*- coding: utf-8 -*-
"""
Multiprocessing support for Hypo71

Created on Thu Dec 24 16:04:58 2020

@author: kris
"""

from itertools import repeat
import multiprocessing
import numpy as np



__all__ = ['hypo71_mp', 'hypo71_test_focal_depths', 'hypo71_mc',
			'hypo71_mc_initloc']


def apply_args_and_kwargs(func, args, kwargs):
	"""
	Wrapper function to be passed to pool.starmap, accepting both positional
	and keyword arguments
	"""
	return func(*args, **kwargs)


def hypo71_mp(arg_names_values, num_processes, use_fortran=False, **kwargs):
	"""
	Multiprocessing version of Hypo71 SINGLE function

	:param arg_name_values:
		dict, mapping arg_names (str, name of SINGLE argument for which multiple
		values are given) to arg_values (list containing multiple values to
		be used for arg_name)
		Note: If dict contains more than 1 arg_name, they all need to have the
		same number of values in arg_values
	:param num_processes:
		int, (max.) number of parallel processes to launch
	:param use_fortran:
		bool, whether or not to use the Fortran version of hypo71
		(default: False)
	**kwargs: further keyword arguments for SINGLE function

	:return:
		list of solutions (LONEP, LATEP, Z, ORG, SE, station_phases, QSD, NI)
	"""
	if use_fortran:
		from .fortran.single_wrapper import SINGLE
	else:
		from .single import SINGLE

	for i, arg_values in enumerate(arg_names_values.values()):
		if i == 0:
			num_jobs = len(arg_values)
		else:
			assert len(arg_values) == num_jobs

	num_processes = min(multiprocessing.cpu_count(), num_processes)
	num_processes = min(num_processes, num_jobs)
	if kwargs.get('verbose', True):
		print("Starting %d parallel hypo71_single processes" % num_processes)
	kwargs['verbose'] = 0

	job_kwargs_list = []
	for j in range(num_jobs):
		job_kwargs = kwargs.copy()
		for arg_name, arg_values in arg_names_values.items():
			job_kwargs[arg_name] = arg_values[j]
		job_kwargs_list.append(job_kwargs)

	pool = multiprocessing.Pool(processes=num_processes)

	args_for_starmap = zip(repeat(SINGLE), repeat([]), job_kwargs_list)
	solutions = pool.starmap(apply_args_and_kwargs, args_for_starmap, chunksize=1)

	## The following lines are necessary to prevent MemoryErrors
	## when running this function multiple times.
	pool.terminate()
	pool.close()
	multiprocessing.util._exit_function()

	return solutions


def hypo71_test_focal_depths(focal_depths, stations, pick_dict, velocity_model,
									num_processes=4, use_fortran=False, verbose=True,
									**kwargs):
	"""
	Run Hypo71 SINGLE function for multiple fixed focal depths, and return
	best solution (i.e. solution with lowest standard error), similar to
	what SeisComP does if depth is not fixed.
	This is useful to determine the best initial trial depth

	:param focal_depths:
		list of floats, fixed focal depths
	:param stations:
	:param pick_dict:
	:param velocity_model:
		see :meth:`robspy.location.hypo71.SINGLE`
	:param num_processes:
		int, (max.) number of parallel processes
		(default: 4)
	:param use_fortran:
		bool, whether or not to use the Fortran version of hypo71
		(default: False)
	**kwargs: further keyword arguments for SINGLE function

	:return:
		(index, solutions)
		- index: index of best solution
		- solutions: list of (LONEP, LATEP, Z, ORG, SE, station_phases, QSD) tuples
	"""
	arg_name = 'ZTR'
	arg_values = focal_depths
	arg_names_values = {arg_name: arg_values}

	kwargs['stations'] = stations
	kwargs['pick_dict'] = pick_dict
	kwargs['velocity_model'] = velocity_model
	kwargs['fix_depth'] = True

	solutions = hypo71_mp(arg_names_values, num_processes, use_fortran=use_fortran,
								verbose=verbose, **kwargs)

	SE = np.zeros(len(focal_depths))
	for s, sol in enumerate(solutions):
		_SE = sol[4]
		SE[s] = np.sqrt(np.sum(_SE**2))
	idx = SE.argmin()

	if verbose:
		for s, solution in enumerate(solutions):
			Z = solution[2]
			#SE = solution[4]
			char = '*' if s == idx else ' '
			print('%cZ=%.1f : SE=%.3f' % (char, Z, SE[s]))

	return idx, solutions


def hypo71_mc(stations, pick_dict, velocity_model,
				sigma_p=0.05, sigma_s=0.1, num_samples=100, random_seed=None,
				truncation_level=2, num_processes=4, use_fortran=False,
				verbose=True, **kwargs):
	"""
	Run hypo71 with Monte-Carlo sampling of phase arrival times

	:param stations:
	:param pick_dict:
	:param velocity_model:
		see :meth:`robspy.location.hypo71.SINGLE`
	:param sigma_p:
		float, uncertainty on P-wave arrival times (in seconds)
		(default: 0.05)
	:param sigma_s:
		float, uncertainty on S-wave arrival times (in seconds)
		(default: 0.1)
	:param num_samples:
		int, number of MC samples
		(default: 100)
	:param random_seed:
		int, seed for random number generator
		(default: None)
	:param truncation_level:
		float, number of standard deviations at which to truncate
		random sampling
		(default: 2)
	:param num_processes:
		int, (max.) number of parallel processes
		(default: 4)
	:param use_fortran:
		bool, whether or not to use the Fortran version of hypo71
		(default: False)
	**kwargs: further keyword arguments for SINGLE function

	:return:
		(mean_solution, solution0, solutions) tuple
	"""
	from scipy.stats import truncnorm

	np.random.seed(random_seed)

	## Count number of P and S phases
	NP = NS = 0
	for station_picks in pick_dict.values():
		if 'P' in station_picks:
			NP += 1
		if 'S' in station_picks:
			NS += 1

	## Generate random time shifts
	if truncation_level:
		P_time_shifts = np.random.normal(0, sigma_p, (num_samples, NP))
		S_time_shifts = np.random.normal(0, sigma_s, (num_samples, NS))
	else:
		tl = truncation_level
		P_time_shifts = truncnorm(-tl, tl, 0, sigma_p, size=(num_samples, NP))
		S_time_shifts = truncnorm(-tl, tl, 0, sigma_s, size=(num_samples, NS))

	## Construct list of time-shifted phase picks
	pick_dict_list = [pick_dict]
	for i in range(num_samples):
		nump = nums = 0
		ts_pick_dict = {}
		for station_code, station_picks in pick_dict.items():
			ts_pick_dict[station_code] = {}
			Ppick = station_picks.get('P')
			if Ppick:
				ts = P_time_shifts[i, nump]
				ts_pick_dict[station_code]['P'] = Ppick.get_time_shifted_copy(ts)
				nump += 1
			Spick = station_picks.get('S')
			if Spick:
				ts = S_time_shifts[i, nums]
				ts_pick_dict[station_code]['S'] = Spick.get_time_shifted_copy(ts)
				nums += 1
		pick_dict_list.append(ts_pick_dict)
	arg_names_values = {'pick_dict': pick_dict_list}

	kwargs['stations'] = stations
	kwargs['velocity_model'] = velocity_model

	solutions = hypo71_mp(arg_names_values, num_processes, use_fortran=use_fortran,
								verbose=verbose, **kwargs)

	mean_solution = calc_mean_solution(solutions, stations, pick_dict, velocity_model,
											weighted=False)

	return (mean_solution, solutions[0], solutions[1:])


def calc_mean_solution(solutions, stations, pick_dict, velocity_model,
							weighted=False):
	"""
	Compute mean location and SE from multiple solutions

	:param stations:
	:param pick_dict:
	:param velocity_model:
		see :meth:`robspy.location.hypo71.SINGLE`
	:param weighted:
		bool, whether or not to weigh solutions by the inverse of their RMSE
		to calculate mean solution
		(default: False)

	:return:
		(LONEP, LATEP, Z, ORG, SE, station_phases, QSD, NI)
	"""
	from .single import (SINGLE, CALC_EPICENTRAL_XY_OFFSET, SHIFT_LONLAT_BY_XY)

	lon0, lat0 = solutions[0][:2]
	lons = np.array([solution[0] for solution in solutions])
	lats = np.array([solution[1] for solution in solutions])
	depths = np.array([solution[2] for solution in solutions])
	dt0 = solutions[0][3]
	time_deltas = np.array([(dt0 - solution[3]) for solution in solutions])

	weights = np.ones_like(lons)
	if weighted:
		## Use RMSE values as (inverse) weights
		rmse_list = []
		for solution in solutions:
			stapha = solution[5]
			rmse_list.append(stapha.calc_rmse())
		weights = 1./np.array(rmse_list)

	dx, dy = CALC_EPICENTRAL_XY_OFFSET(lon0, lat0, lons, lats)
	dx_mean, dy_mean = np.average(dx, weights=weights), np.average(dy, weights=weights)
	lon_mean, lat_mean = SHIFT_LONLAT_BY_XY(lon0, lat0, dx_mean, dy_mean)
	z_mean = np.average(depths, weights=weights)
	# TODO: not sure if this is best way to compute mean origin time
	# other possibility is to run single again with fixed origin
	# to determine origin time that minimizes station residuals
	td_mean = np.average(time_deltas, weights=weights)
	dt_mean = dt0 + td_mean

	## Combine weighted standard deviations from solutions of random sampling
	## with mean standard deviations from hypo71
	errx = np.array([solution[4][0] for solution in solutions])
	erry = np.array([solution[4][1] for solution in solutions])
	errz = np.array([solution[4][2] for solution in solutions])
	errt = np.array([solution[4][3] for solution in solutions])
	errx_mean = np.average(errx, weights=weights)
	erry_mean = np.average(erry, weights=weights)
	errz_mean = np.average(errz, weights=weights)
	errt_mean = np.average(errt, weights=weights)
	dx_var = np.average((dx-dx_mean)**2, weights=weights)
	dy_var = np.average((dy-dy_mean)**2, weights=weights)
	depths_var = np.average((depths-z_mean)**2, weights=weights)
	time_deltas_var = np.average((time_deltas-td_mean)**2, weights=weights)

	SE_mean = np.zeros(4)
	SE_mean[0] = np.sqrt(errx_mean**2 + dx_var)
	SE_mean[1] = np.sqrt(erry_mean**2 + dy_var)
	SE_mean[2] = np.sqrt(errz_mean**2 + depths_var)
	SE_mean[3] = np.sqrt(errt_mean**2 + time_deltas_var)

	## Compute residuals
	_solution = SINGLE(stations, pick_dict, velocity_model,
							ZTR=z_mean, fix_depth=True,
							origin=(lon_mean, lat_mean, dt_mean), fix_origin=True,
							use_fortran_speedups=False, verbose=0)
	station_phases = _solution[5]
	#dt_mean = _solution[3]

	QSlist = [solution[6][0] for solution in solutions]
	QDlist = [solution[6][1] for solution in solutions]
	QS = 'ABCD'[np.argmax([np.sum(np.array(QSlist) == char) for char in 'ABCD'])]
	QD = 'ABCD'[np.argmax([np.sum(np.array(QDlist) == char) for char in 'ABCD'])]
	QSD = QS + QD
	NI = np.round(np.mean([solution[-1] for solution in solutions]))

	mean_solution = (lon_mean, lat_mean, z_mean, dt_mean, SE_mean,
						station_phases, QSD, NI)

	return mean_solution


def hypo71_mc_initloc(stations, pick_dict, velocity_model,
				initial_depth, fix_depth=False, initial_loc=None, sigma_lat=0.1,
				num_samples=100, random_seed=None, truncation_level=2,
				weighted_mean=True, num_processes=4, use_fortran=False,
				verbose=True, **kwargs):
	"""
	Run hypo71 with Monte-Carlo sampling of initial locations

	:param stations:
	:param pick_dict:
	:param velocity_model:
		see :meth:`robspy.location.hypo71.SINGLE`
	:param initial_depth:
		float, initial depth (in km)
	:param fix_depth:
		bool, whether or not depth should be fixed
		(default: False)
	:param initial_loc:
		(lon, lat) tuple with initial location around which to sample
		(default: None, will use location of nearest station)
	:param sigma_lat:
		float, uncertainty on latitude (in degrees)
		Uncertainty on longitude will be derived from this
		(default: 0.1)
	:param num_samples:
		int, number of MC samples
		(default: 100)
	:param random_seed:
		int, seed for random number generator
		(default: None)
	:param truncation_level:
		float, number of standard deviations at which to truncate
		random sampling
		(default: 2)
	:param weighted_mean:
		bool, whether or not to weigh solutions by the inverse of their RMSE
		to calculate mean solution
		(default: True)
	:param num_processes:
		int, (max.) number of parallel processes
		(default: 4)
	:param use_fortran:
		bool, whether or not to use the Fortran version of hypo71
		(default: False)
	**kwargs: further keyword arguments for SINGLE function

	:return:
		(mean_solution, solution0, solutions) tuple
	"""
	from scipy.stats import truncnorm

	np.random.seed(random_seed)

	if initial_loc is None:
		## Use nearest station, adding 0.1 minutes to lon/lat, similar to SINGLE
		Ptimes, Pstations = [], []
		Stimes, Sstations = [], []
		for stat_code, station_picks in pick_dict.items():
			Ppick = station_picks.get('P')
			if Ppick:
				Ptimes.append(Ppick.datetime)
				Pstations.append(stat_code)
			Spick = station_picks.get('S')
			if Spick:
				Stimes.append(Spick.datetime)
				Sstations.append(stat_code)
		if len(Ptimes):
			min_idx = np.nanargmin(Ptimes)
			nearest_stat_code = Pstations[min_idx]
		else:
			min_idx = np.nanargmin(Stimes)
			nearest_stat_code = Sstations[min_idx]
		for station in stations:
			if station.code == nearest_stat_code:
				initial_loc = (station.lon + 0.1/60, station.lat + 0.1/60)

	lon, lat = initial_loc
	sigma_lon = sigma_lat / np.cos(np.radians(lat))

	## Generate random position shifts
	if truncation_level:
		lon_shifts = np.random.normal(0, sigma_lon, num_samples)
		lat_shifts = np.random.normal(0, sigma_lat, num_samples)
	else:
		tl = truncation_level
		lon_shifts = truncnorm(-tl, tl, 0, sigma_lon, size=num_samples)
		lat_shifts = truncnorm(-tl, tl, 0, sigma_lat, size=num_samples)
	lon_shifts = np.concatenate([[0], lon_shifts])
	lat_shifts = np.concatenate([[0], lat_shifts])

	initial_origins = [(lon+dlon, lat+dlat, None)
							for (dlon, dlat) in zip(lon_shifts, lat_shifts)]
	arg_names_values = {'origin': initial_origins}

	kwargs['stations'] = stations
	kwargs['pick_dict'] = pick_dict
	kwargs['ZTR'] = initial_depth
	kwargs['fix_depth'] = fix_depth
	kwargs['fix_origin'] = False

	if isinstance(velocity_model, type('')):
		from ...rob import velocity_model as vmodel_module
		velocity_model = getattr(vmodel_module, velocity_model)
	kwargs['velocity_model'] = velocity_model

	solutions = hypo71_mp(arg_names_values, num_processes, use_fortran=use_fortran,
								verbose=verbose, **kwargs)

	mean_solution = calc_mean_solution(solutions, stations, pick_dict, velocity_model,
												weighted=weighted_mean)

	return (mean_solution, solutions[0], solutions[1:])
