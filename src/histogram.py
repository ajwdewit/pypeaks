#!/usr/bin/env python

from __future__ import division
import pickle
from warnings import warn

import numpy as np
from scipy.ndimage.filters import gaussian_filter

import slope


class Histogram:
    def __init__(self, x, y, smoothness=7):
        self.x = np.array(x)
        self.y_raw = np.array(y)
        self.y = y
        self.smooth()
        self.smoothness = smoothness
        self.peaks = {}

    def set_smoothness(self, smoothness):
        self.smoothness = smoothness

    def smooth(self):
        self.y = gaussian_filter(self.y, self.smoothness)

    def normalize(self):
        #TODO
        pass

    def serialize(self, path):
        pickle.dump([self.x, self.y_raw], file(path, 'w'))

    def get_peaks(self, method="slope", peak_amp_thresh=0.00005,
                  valley_thresh=0.00003, intervals=None, lookahead=20,
                  avg_interval=100):
        """
        This function expects SMOOTHED histogram. If you run it on a raw histogram,
        there is a high chance that it returns no peaks.

        method can be interval/slope/hybrid.
            The interval-based method simply steps through the whole histogram
            and pick up the local maxima in each interval, from which irrelevant
            peaks are filtered out by looking at the proportion of points on 
            either side of the detected peak in each interval.
        
            Slope approach uses, of course slope information, to find peaks, 
            which are then filtered by applying peal_amp_thresh and 
            valley_thresh bounds. 
            
            Hybrid approach first finds peaks using slope method and then filters 
            them heuristically as in interval-based approach.
        
        peak_amp_thresh is the minimum amplitude/height that a peak should have
        in a normalized smoothed histogram, to be qualified as a peak. 
        valley_thresh is viceversa for valleys!

        If the method is interval/hybrid, then the intervals argument must be passed
        and it should be an instance of Intervals class.

        If the method is slope/hybrid, then the lookahead and avg_window
        arguments should be changed based on the application. 
        They have some default values though.

        The method returns:
        {"peaks":[[peak positions], [peak amplitudes]], 
        "valleys": [[valley positions], [valley amplitudes]]}
        """

        peaks = {}
        slope_peaks = {}
        #Oh dear future me, please don't get confused with a lot of mess around
        # indices around here. All indices (eg: left_index etc) refer to indices
        # of x or y (of histogram).
        if method == "slope" or method == "hybrid":

            #step 1: get the peaks
            result = slope.peaks(self.x, self.y, lookahead=lookahead,
                                 delta=valley_thresh)

            #step 2: find left and right valley points for each peak
            peak_data = result["peaks"]
            valley_data = result["valleys"]

            for i in xrange(len(peak_data[0])):
                nearest_index = slope.find_nearest_index(valley_data[0],
                                                         peak_data[0][i])
                if valley_data[0][nearest_index] < peak_data[0][i]:
                    left_index = slope.find_nearest_index(
                        self.x, valley_data[0][nearest_index])
                    if len(valley_data[0][nearest_index + 1:]) == 0:
                        right_index = slope.find_nearest_index(
                            self.x, peak_data[0][i] + avg_interval / 2)
                    else:
                        offset = nearest_index + 1
                        nearest_index = offset + slope.find_nearest_index(
                            valley_data[0][offset:], peak_data[0][i])
                        right_index = slope.find_nearest_index(
                            self.x, valley_data[0][nearest_index])
                else:
                    right_index = slope.find_nearest_index(
                        self.x, valley_data[0][nearest_index])
                    if len(valley_data[0][:nearest_index]) == 0:
                        left_index = slope.find_nearest_index(
                            self.x, peak_data[0][i] - avg_interval / 2)
                    else:
                        nearest_index = slope.find_nearest_index(
                            valley_data[0][:nearest_index], peak_data[0][i])
                        left_index = slope.find_nearest_index(
                            self.x, valley_data[0][nearest_index])

                pos = slope.find_nearest_index(self.x, peak_data[0][i])
                slope_peaks[pos] = [peak_data[1][i], left_index, right_index]

        if method == "slope":
            peaks = slope_peaks

        interval_peaks = {}
        if method == "interval" or method == "hybrid":
            #step 1: get the average size of the interval, first and last
            # probable centers of peaks
            avg_interval = np.average(intervals.intervals[1:] - intervals.intervals[:-1])
            first_center = (min(self.x) + 1.5 * avg_interval) / avg_interval * avg_interval
            last_center = (max(self.x) - avg_interval) / avg_interval * avg_interval
            if first_center < min(intervals.intervals[0]):
                first_center = intervals.intervals[0]
                warn("In the interval based approach, the first center was seen\
                    to be too low and is set to " + str(first_center))
            if last_center > intervals.intervals[-1]:
                last_center = intervals.intervals[-1]
                warn("In the interval based approach, the last center was seen\
                     to be too high and is set to " + str(last_center))

            #step 2: find the peak position, and set the left and right bounds
            # which are equivalent in sense to the valley points
            interval = first_center
            while interval < last_center:
                prev_interval = intervals.prev_interval(interval)
                next_interval = intervals.next_interval(interval)
                left_index = slope.find_nearest_index(
                    self.x, (interval + prev_interval) / 2)
                right_index = slope.find_nearest_index(
                    self.x, (interval + next_interval) / 2)
                peak_pos = np.argmax(self.y[left_index:right_index])
                # add left_index to peak_pos to get the correct position in x/y
                peak_amp = self.y[left_index + peak_pos]
                interval_peaks[left_index + peak_pos] = [peak_amp, left_index,
                                                         right_index]

        if method == "interval":
            peaks = interval_peaks

        # If its is a hybrid method merge the results. If we find same
        # peak position in both results, we prefer valleys of slope-based peaks
        if method == "hybrid":
            p1 = slope_peaks.keys()
            p2 = interval_peaks.keys()
            all_peaks = {}
            for p in p1:
                near_index = slope.find_nearest_index(p2, p)
                if abs(p - p2[near_index]) < avg_interval / 2:
                    p2.pop(near_index)
            for p in p1:
                all_peaks[p] = slope_peaks[p]
            for p in p2:
                all_peaks[p] = interval_peaks[p]
            peaks = all_peaks

        # Finally, filter the peaks and retain eligible peaks, also get
        # their valley points.

        # check 1: peak_amp_thresh
        for pos in peaks.keys():
            # pos is an index in x/y. DOES NOT refer to a cent value.
            if peaks[pos][0] < peak_amp_thresh:
                peaks.pop(pos)

        # check 2, 3: valley_thresh, proportion of size of left and right lobes
        valleys = {}
        for pos in peaks.keys():
            # remember that peaks[pos][1] is left_index and
            # peaks[pos][2] is the right_index
            left_lobe = self.y[peaks[pos][1]:pos]
            right_lobe = self.y[pos:peaks[pos][2]]
            if len(left_lobe) == 0 or len(right_lobe) == 0 or\
                  len(left_lobe) / len(right_lobe) < 0.15 or\
                  len(left_lobe) / len(right_lobe) > 6.67:
                continue

            left_valley_pos = np.argmin(left_lobe)
            right_valley_pos = np.argmin(right_lobe)
            if (abs(left_lobe[left_valley_pos] - self.y[pos]) < valley_thresh and
                abs(right_lobe[right_valley_pos] - self.y[pos]) < valley_thresh):
                peaks.pop(pos)
            else:
                valleys[peaks[pos][1] + left_valley_pos] = left_lobe[left_valley_pos]
                valleys[pos + right_valley_pos] = right_lobe[right_valley_pos]

        if len(peaks) > 0:
            peak_amps = np.array(peaks.values())
            peak_amps = peak_amps[:, 0]
            # hello again future me, it is given that you'll pause here
            # wondering why the heck we index x with peaks.keys() and
            # valleys.keys(). Just recall that pos refers to indices and
            # not value corresponding to the histogram bin. If i is pos,
            # x[i] is the bin value. Tada!!
            self.peaks = {'peaks': [self.x[peaks.keys()], peak_amps], 'valleys': [self.x[valleys.keys()], valleys.values()]}
        else:
            self.peaks = {'peaks': [[], []], 'valleys': [[], []]}

    @staticmethod
    def extend_peaks(src_peaks, prop_thresh=50):
        """Each peak in src_peaks is checked for its presence in other octaves.
        If it does not exist, it is created. prop_thresh is the cent range within
        which the peak in the other octave is expected to be present, i.e., only
        if there is a peak within this cent range in other octaves, then the peak
        is considered to be present in that octave.

        This is a static method which is not allowed to change the existing peaks.
        It just returns the extended peaks.
        """
        # octave propagation of the reference peaks
        temp_peaks = [i + 1200 for i in src_peaks["peaks"][0]]
        temp_peaks.extend([i - 1200 for i in src_peaks["peaks"][0]])
        extended_peaks = []
        extended_peaks.extend(src_peaks["peaks"][0])
        for i in temp_peaks:
            # if a peak exists around, don't add this new one.
            nearest_ind = slope.find_nearest_index(src_peaks["peaks"][0], i)
            diff = abs(src_peaks["peaks"][0][nearest_ind] - i)
            diff = np.mod(diff, 1200)
            if diff > prop_thresh:
                extended_peaks.append(i)
        return extended_peaks