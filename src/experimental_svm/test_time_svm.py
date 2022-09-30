import matplotlib.pyplot as plt
from numpy import array
from create_svm import SvmLearner
from timeit import default_timer as timer
import csv
import os
# sizes of the database to test (nr of fingerprints)
TEST_SIZES = [10, 20, 30, 40, 50]
# if true: only train on the first 6 windows
# else:    train on all windows of the fingerprints
FAST_MODE = True



def plot_time_test(results, database_size) -> None:
    """
    Function used to plot results from run_buildtime_test
    it saves the result in ./time_test.png
    """
    file_found = False
    file_number = 1
    file_name = "./time_test1.png"
    while not file_found:
        if not os.path.isfile(file_name):
            file_found = True
        else:
            file_number = file_number + 1
            file_name = "./time_test{}.png".format(file_number)

    print("Writing to file {}".format(file_name))

    plt.figure(figsize=(8,6))
    plt.xlabel("# fingerprints for build and training")
    plt.ylabel("Time (seconds)")
    plt.title("Training times for SVM")
    plt.plot(database_size, results)
    plt.savefig(file_name)




def save_result(start : float, end : float, size : int, fast_mode : bool) -> None:
    """
    Store results from run_buildtime_test in ./times_fast_SVM.csv or ./times_slow_SVM.csv
    depending on the type of SVM being built and trained in run_buildtime_test
    """
    mode = "slow"
    if fast_mode: mode="fast"
    with open(f'times_{mode}_SVM.csv', 'a', newline='', encoding='utf8') as csv_file:
                    writer = csv.writer(csv_file)
                    writer.writerow([size, (end-start)])



def run_buildtime_test(sizes, fast_mode = False) -> None:
    """
    Function to calculate the time taken to build and train a SVM with X number of fingerprints.

    build_times:        The time (seconds) it takes to build and train a SVM with X number of fingerprints.
    num_fingerprints:   num_fingerprints[i] corresponds to build_times[i] for num_fingerprints[i] of fingerprints.
    """
    build_times = []
    num_fingerprints = []
    for size in sizes:
        print("Testing, building and training time for {} videos.".format(size))
        start = timer()
        if fast_mode:
            SvmLearner(fingerprint_start=14, fingerprint_end=34, nr_fingerprints=size)
        else:
            SvmLearner(nr_fingerprints=size)
        end = timer()
        print("Time lapsed for {} is {} seconds".format(size, end-start))
        save_result(start, end, size, fast_mode)
        
        build_times.append(end-start)
        num_fingerprints.append(size)

    plot_time_test(build_times, num_fingerprints)



run_buildtime_test(sizes=TEST_SIZES, fast_mode=FAST_MODE)


