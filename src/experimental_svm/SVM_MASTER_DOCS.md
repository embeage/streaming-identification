# Master documentation for SVM's

## To install  dependancies
<ul>
	<li>Make sure you are using python version 3.10 or higher</li>
	<li>Install corresponding version of pip</li>
	<li>To see the list of dependancies, see svm_requirements.txt</li>
</ul>
<p>Run command: </p>

```
pip install -r svm_requirements.txt
```

## To update dependancies
<p>Make sure that you have the appropriate python version, then when in the root folder of the SVM after installing your new dependancies locally update svm_requirements.txt to allow other users to follow the new dependancies, run the command: </p>

```
pip freeze > svm_requirements.txt
```
## Tests

<p>
The different tests of the svm can be found in the files:
</p>


### Parameter tests
<p>
./test_params_svm.py, which tests different parameters for the SVM, such as C, gamma, window width etc.

Further development: implement a GridSearch to find the best parameters
</p>

### Time tests
<p>
./test_time_svm.py, which tests the combined building and training times for the SVM

Saves graphs of results in "./time_testX.png" where X is the first available filename in the directory.

The pure data can be seen in "./times_fast_SVM.csv" or "./times_slow_SVM.csv" depending on the Fast or slow option, for more information on this option see ./test_time_svm.py and ./create_svm.py
</p>

### Gridsearch test

<p>
./gridsearch_svm.py, variant of the parameter test with exhaustive search with the built in utilities from the scikitlearn. Results are saved in ./gridsearch_results.csv and written to the console.
</p>

### Utilities

<p>
./svm_utilities.py created to access previously defined functions in the create_svm.py classes to allow for usage in different files/modules.
</p>

