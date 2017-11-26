import traceback

import numpy as np
import sys
from time import time
from data_input_processing import Data, train_test_validation_indices, generate_training_variables
from strategy_evaluation import post_process_training_results, output_strategy_results
from machine_learning import random_forest_fitting, svm_fitting, adaboost_fitting, gradient_boosting_fitting,\
    extra_trees_fitting, tensorflow_fitting, tensorflow_sequence_fitting

SEC_IN_DAY = 24*60*60


def meta_fitting(fitting_inputs, fitting_targets, strategy_dictionary):
    error = []
    fitting_dictionary = {}
    train_indices, test_indices, validation_indices = train_test_validation_indices(
        fitting_inputs, strategy_dictionary['train_test_validation_ratios'])
    if strategy_dictionary['ml_mode'] == 'svm':
        fitting_dictionary, error = svm_fitting(
            fitting_inputs, fitting_targets, train_indices, test_indices, validation_indices, strategy_dictionary)

    elif strategy_dictionary['ml_mode'] == 'randomforest':
        fitting_dictionary, error = random_forest_fitting(
            fitting_inputs, fitting_targets, train_indices, test_indices, validation_indices, strategy_dictionary)

    elif strategy_dictionary['ml_mode'] == 'adaboost':
        fitting_dictionary, error = adaboost_fitting(
            fitting_inputs, fitting_targets, train_indices, test_indices, validation_indices, strategy_dictionary)

    elif strategy_dictionary['ml_mode'] == 'gradientboosting':
        fitting_dictionary, error = gradient_boosting_fitting(
            fitting_inputs, fitting_targets, train_indices, test_indices, validation_indices, strategy_dictionary)

    elif strategy_dictionary['ml_mode'] == 'extratreesfitting':
        fitting_dictionary, error = extra_trees_fitting(
            fitting_inputs, fitting_targets, train_indices, test_indices, validation_indices, strategy_dictionary)

    fitting_dictionary['train_indices'] = train_indices
    fitting_dictionary['test_indices'] = test_indices
    fitting_dictionary['validation_indices'] = validation_indices
    fitting_dictionary['error'] = error

    return fitting_dictionary


def input_processing(data_input_1, data_input_2, strategy_dictionary):
    print("Generating training variables [1]")
    fitting_inputs, continuous_targets, classification_targets = generate_training_variables(
        data_input_1, strategy_dictionary)

    print("Generating training variables [2]")
    fitting_inputs_2, fitting_targets_2, classification_targets_2 = generate_training_variables(
        data_input_2, strategy_dictionary, prior_data_obj=data_input_1)

    print("Trimming inputs")
    fitting_inputs, fitting_inputs_2 = trim_inputs(fitting_inputs, fitting_inputs_2)

    print("Hstacking")
    fitting_inputs = np.hstack((fitting_inputs, fitting_inputs_2))

    return fitting_inputs, continuous_targets, classification_targets


def trim_inputs(fitting_inputs, fitting_inputs_2):
    length_1 = len(fitting_inputs)
    length_2 = len(fitting_inputs_2)

    min_length = np.minimum(length_1, length_2)

    fitting_inputs = fitting_inputs[-min_length:]
    fitting_inputs_2 = fitting_inputs_2[-min_length:]
    return fitting_inputs, fitting_inputs_2


def tic():
    t = time()
    return lambda: (time() - t)


def retrieve_data(ticker, scraper_currency, strategy_dictionary, filename):
    data_local = None
    while data_local is None:
        print ("Attempting data retrieval")
        try:
            if strategy_dictionary['web_flag']:
                end = time() - strategy_dictionary['offset'] * SEC_IN_DAY

                start = end - SEC_IN_DAY * strategy_dictionary['n_days']

                data_local = Data(
                    ticker, scraper_currency, strategy_dictionary['candle_size'], strategy_dictionary['web_flag'],
                    start=start, end=end,
                )
            else:
                data_local = Data(
                    ticker, scraper_currency, strategy_dictionary['candle_size'], strategy_dictionary['web_flag'],
                    offset=strategy_dictionary['offset'], filename=filename,
                    n_days=strategy_dictionary['n_days'])
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            print("*** print_tb:")
            traceback.print_tb(exc_traceback, limit=1, file=sys.stdout)
            print("*** print_exception:")
            traceback.print_exception(exc_type, exc_value, exc_traceback, file=sys.stdout)
            sys.exit(1)

    data_local.normalise_data()

    return data_local


def offset_scan_validation(strategy_dictionary, data_to_predict, fitting_inputs, fitting_targets, offsets):
    strategy_dictionary['plot_flag'] = False
    strategy_dictionary['ouput_flag'] = True

    total_error = 0
    total_profit = 0

    for offset in offsets:
        strategy_dictionary['offset'] = offset
        fitting_dictionary,  profit_fraction = fit_strategy(
            strategy_dictionary, data_to_predict, fitting_inputs, fitting_targets)
        total_error += fitting_dictionary['error'] / len(offsets)
        total_profit += profit_fraction

    underlined_output('Averages: ')
    print('Total profit: %s' % total_profit)
    print('Average error: %s' % total_error)


def tensorflow_offset_scan_validation(strategy_dictionary, data_to_predict, fitting_inputs, fitting_targets, offsets):
    strategy_dictionary['plot_flag'] = False
    strategy_dictionary['ouput_flag'] = True
    
    total_error = 0
    total_profit = 0

    for offset in offsets:
        strategy_dictionary['offset'] = offset
        fitting_dictionary, error, profit_fraction = fit_tensorflow(
            strategy_dictionary, data_to_predict, fitting_inputs, fitting_targets)
        total_error += error
        total_profit += profit_fraction

    underlined_output('Averages: ')
    print ('Total profit: %s' % total_profit)
    print ('Average error: %s' % total_error)


def import_data(strategy_dictionary):
    print ('Retrieving candlestick data for ticker1[%s]' % strategy_dictionary['ticker_1'])
    data_1 = retrieve_data(
        strategy_dictionary['ticker_1'], strategy_dictionary['scraper_currency_1'], strategy_dictionary, strategy_dictionary['filename1'])

    print('Retrieving candlestick data for ticker2[%s]' % strategy_dictionary['ticker_2'])
    data_2 = retrieve_data(
        strategy_dictionary['ticker_2'], strategy_dictionary['scraper_currency_2'], strategy_dictionary, strategy_dictionary['filename2'])

    return data_1, data_2


def fit_strategy(strategy_dictionary, data_to_predict, fitting_inputs, fitting_targets):
    toc = tic()

    fitting_dictionary = meta_fitting(fitting_inputs, fitting_targets, strategy_dictionary)

    fitting_dictionary = post_process_training_results(strategy_dictionary, fitting_dictionary, data_to_predict)

    profit_factor = output_strategy_results(strategy_dictionary, fitting_dictionary, data_to_predict, toc)

    return fitting_dictionary, profit_factor


def fit_tensorflow(strategy_dictionary, data_to_predict, fitting_inputs, fitting_targets):
    toc = tic()

    train_indices, test_indices, validation_indices = train_test_validation_indices(
        fitting_inputs, strategy_dictionary['train_test_validation_ratios'])

    if strategy_dictionary['sequence_flag']:
        fitting_dictionary, error = tensorflow_sequence_fitting(
            '/tmp/test', train_indices, test_indices, validation_indices, fitting_inputs, fitting_targets,
            strategy_dictionary)

    else:
        fitting_dictionary, error = tensorflow_fitting(
            train_indices, test_indices, validation_indices, fitting_inputs,
                                                       fitting_targets)

    fitting_dictionary['train_indices'] = train_indices
    fitting_dictionary['test_indices'] = test_indices
    fitting_dictionary['validation_indices'] = validation_indices

    fitting_dictionary = post_process_training_results(strategy_dictionary, fitting_dictionary, data_to_predict)

    profit_factor = output_strategy_results(strategy_dictionary, fitting_dictionary, data_to_predict, toc)
    return fitting_dictionary, error, profit_factor


def underlined_output(string):
    print ('%s\n----------------------\n' % string)
