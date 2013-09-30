import numpy as np
import peak_detection as pd

class Intervals:
    def __init__(self, intervals):
        self.intervals = np.array(intervals)
    
    def next_interval(self, interval):
        """
        Given a value of an interval, this function returns the 
        next interval value
        """
        index = np.where(self.intervals == interval)
        if index[0][0] + 1 < len(self.intervals):
            return self.intervals[index[0][0] + 1]
        else:
            raise IndexError("Ran out of intervals!")

    def nearest_interval(self, interval):
        """
        This function returns the nearest interval to any given interval.
        """
        thresh_range = 25 #in cents
        if interval < self.intervals[0] - thresh_range or interval > self.intervals[-1] + thresh_range:
            raise IndexError("The interval given is beyond " + str(thresh_range)
                             + " cents over the range of intervals defined.")

        index = pd.find_nearest_index(self.intervals, interval)
        return self.intervals[index]
