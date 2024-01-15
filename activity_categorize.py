def msg(text):
    global verbose
    if verbose == True:
        print(text)
# read files
def search_files(dirname,pattern,recursive = False):
    msg(f'Searching files with the pattern "{pattern}"...')
    if recursive:
        file_list = sorted(Path(dirname).rglob(pattern))
    else:
        file_list = sorted(Path(dirname).glob(pattern))
    return(file_list)

def load_excel(file_name):
    out_df = pd.DataFrame(columns=['Time','kind','data'])
    feature_rename={ 'Heart rate (bpm)':'hr',
                    'Diastolic (mmHg)':'bp_dia',
                    'Systolic (mmHg)':'bp_sys',
                    'SaO2 (%)':'spo2',
                    'Body temperature (C)':'st', 
                    'Pedometer':'step',
                    'Total sleep':'sleep_total',
                    'Deep sleep':'sleep_deep',
                    'Light sleep':'sleep_light',
                    'Event Markers':'Event_markers'}
    wb = load_workbook(file_name)
    for sheet in wb.worksheets:
        data = sheet.values
        header = next(data)
        header = [feature_rename[x] if x in feature_rename else x for x in header]
        data = list(data)
        df = pd.DataFrame(data,columns=header)
        if 'sleep_total' in header:
            df['sleep_total'] = df['sleep_total'].apply(lambda x: to_minutes(x) if len(x) > 0 else x)
            df['sleep_deep'] = df['sleep_deep'].apply(lambda x: to_minutes(x) if len(x) > 0 else x)
            df['sleep_light'] = df['sleep_light'].apply(lambda x: to_minutes(x) if len(x) > 0 else x)
        df = pd.melt(df, id_vars=['Time'], value_vars=header[1:], var_name='kind', value_name='data')
        df = df[df['kind'] != 'Body temperature (F)']
        df = df[df['data'] != '']
        out_df = pd.concat([out_df,df],ignore_index=True)
    out_df.reset_index(inplace = True, drop = True)
    out_df.rename(columns={'Time':'date_time'},inplace=True)
    out_df['date_time'] = pd.to_datetime(out_df['date_time'])
    return(out_df)

def to_minutes(t):
    hs=t.strip('m').split('h')
    return(int(hs[0])*60+int(hs[1]))

def load_csv(file_name,file_type = 'measurement'):
    if file_type == 'measurement':
        out_df = pd.read_csv(file_name,usecols=['date_time','kind','data'])
        out_df['date_time'] = pd.to_datetime(out_df['date_time'])
        out_df['kind'] = out_df['kind'].apply(lambda x: str(x))
        out_df['data'] = out_df['data'].apply(lambda x: float(x))
    elif file_type == 'acc':
        out_df = pd.read_csv(file_name,usecols=['date_time','g_force'])
        out_df['date_time'] = pd.to_datetime(out_df['date_time'])
        out_df['g_force'] = out_df['g_force'].apply(lambda x: float(x))
    elif file_type == 'acc_cat':
        out_df = pd.read_csv(file_name,usecols=['start_time','end_time','category'])
        out_df['start_time'] = pd.to_datetime(out_df['start_time'])
        out_df['end_time'] = pd.to_datetime(out_df['end_time'])
    else:
        return()
    return(out_df)

def extract_kind(df, kind = 'sleep_total'):
    df = df[(df['kind'] == kind) & (~np.isnan(df['data'].values))].copy()
    new_df = df[df['data'].shift() != df['data']].copy()
    new_df.reset_index(drop = True, inplace = True)
    return(new_df)

def preliminary_intervals(df,reset_gap_hours = 12):
    reset_time_delta = np.timedelta64(reset_gap_hours,'h')
    zero_time = np.array([pd.Timestamp('2000-01-01 00:00:00').to_numpy()])
    times = df['date_time'].values
    prev_times = np.concatenate((zero_time,times[:len(times) - 1]))
    timedeltas = np.subtract(times,prev_times)
    timer_reset = timedeltas > reset_time_delta
    
    total_sleep_minutes = df['data'].values
    prev_minutes = np.concatenate((np.array([0]),total_sleep_minutes[:len(total_sleep_minutes)-1]))
    prev_minutes = np.subtract(prev_minutes,prev_minutes,out = prev_minutes,where = timer_reset)
    new_sleep_minutes = np.subtract(total_sleep_minutes, prev_minutes, out = total_sleep_minutes, where = total_sleep_minutes > prev_minutes)
    df['sleep_minutes'] = new_sleep_minutes
    sleep_periods = np.array([np.timedelta64(int(x),'m') for x in new_sleep_minutes])
    sleep_start = np.subtract(times,sleep_periods)
    sleep_intervals = np.array([*zip(sleep_start,times)])
    return(sleep_intervals)

def merge_intervals(time_intervals):
    time_intervals.sort()
    output = []
    output.append(time_intervals[0])
    for i in time_intervals[1:]:
        if output[-1][1] >= i[0]:
            output[-1][1] = max(output[-1][1],i[1])
        else:
            output.append(i)
    output = np.array(output)
    return(output)

def subtract_intervals(base, sub):
    base_gen, sub_gen = (list(x) for x in base), (x for x in sub) # turn list into generator
    a, b = next(base_gen),next(sub_gen)
    out_list = []
    while True:
        if not check_overlap(a,b):
            if a[1] < b[0]:
                out_list.append(a)
                try:
                    a = next(base_gen)
                except StopIteration:
                    break
            else:
                try:
                    b = next(sub_gen)
                except StopIteration:
                    remaining_base = [x for x in base_gen]
                    out_list.append(a)
                    out_list = out_list + remaining_base
                    break
        else:
            if a[1] <= b[1]:
                if a[0] <= b[0]:
                    out_list.append([a[0],b[0]])
                try:
                    a = next(base_gen)
                except StopIteration:
                    break
            else:
                if a[0] <= b[0]:
                    out_list.append([a[0],b[0]])
                a = [b[1],a[1]]
                try:
                    b = next(sub_gen)
                except StopIteration:
                    remaining_base = [x for x in base_gen]
                    out_list.append(a)
                    out_list = out_list + remaining_base
                    break
    return(np.array(out_list))

def check_overlap(interval_a, interval_b):
    if (interval_a[0] < interval_b[0] and interval_a[1] < interval_b[0]) or (interval_a[0] > interval_b[1] and interval_a[1] > interval_b[1]):
        return(False)
    else:
        return(True)
    
def sleep_acc_thresh(df,sleep_periods,quantiles = (0.025,0.975)):
    df.sort_values(by = 'date_time', inplace = True)
    timestamps = df['date_time'].values
    filter_array = np.repeat(False, len(timestamps))
    for p in sleep_periods:
        ind = np.logical_and(timestamps >= p[0], timestamps <= p[1])
        filter_array = np.logical_or(filter_array,ind)
    filtered_df = df[filter_array].copy()
    filtered_df.reset_index(drop = True, inplace = True)
    sleep_g = filtered_df['g_force'].values
    thresholds = (np.quantile(sleep_g,quantiles[0]),np.quantile(sleep_g,quantiles[1]))
    return(thresholds)

def acc_categorize(df,acc_threshold, bin_size = 5):
    msg(f'Binning acceration data in {bin_size} minute windows')
    df['date'] = df['date_time'].apply(lambda x: x.date())
    start_time_list,end_time_list,category_list = [],[],[]
    df['floored_date_time'] = time_bin(df['date_time'].values, bin_size)
    msg('Finished binning, categorizing acceleration status in each window.')
    for bin_time, bin_df in df.groupby('floored_date_time'):
        start_time_list = start_time_list + [bin_time]
        end_time_list = end_time_list + [bin_time + np.timedelta64(bin_size,'m')]
        category_list = category_list + [bin_categorize(bin_df['g_force'].values,acc_threshold)]
    out_df = pd.DataFrame({'start_time':start_time_list,'end_time':end_time_list,'category':category_list})
    out_df = merge_windows(out_df)
    return(out_df)

def time_bin(t_array, window = 5):
    t_array = t_array.astype('datetime64[m]').astype(int)
    t_array = t_array // window * 5
    t_array = t_array.astype('datetime64[m]')
    return(t_array)

def bin_categorize(g_force_array,thresholds, cutoffs = (5,10)):
    outliers = np.logical_or(g_force_array < thresholds[0], g_force_array > thresholds[1])
    percentage = sum(outliers) / len(outliers) * 100
    if percentage > cutoffs[1]:
        return('high active')
    elif percentage > cutoffs[0]:
        return('low active')
    else:
        return('rest')

def merge_windows(df):
    df_gen = (x for x in df.values)
    current_start, current_end, current_cat = next(df_gen)
    start_list, end_list, cat_list = [],[],[]
    for ti in df_gen:
        if (current_cat != ti[2]) or (ti[0] != current_end):
            start_list.append(current_start)
            end_list.append(current_end)
            cat_list.append(current_cat)
            current_start, current_end, current_cat = ti
        else: 
            current_end = ti[1]
    out_df = pd.DataFrame({'start_time':start_list,'end_time':end_list,'category':cat_list})
    return(out_df)

def main():
    help_msg ='''This script categorizes user time to rest, low activity, or high activity.

    Usage: python activity_categorize.py -f <input_files> -a <acceleration_files> -s <save_name>  [options]

    Arguments:
        -f: Input file, .xlsx or .csv. Can provide a directory, the script will search all files with corresponding file extensions (see -e below)
        -a: Reformatted acceleration table. Can provide a directory; the script will perform recursive search for files ending in *ac_reformatted.csv and load all of them.
            --acc_cat: Alternative to -a, provide a pre-existing acceleration catagorizing table in .csv format.
        -s: save file location and name stem, e.g. output/directory/subject_id

    Options:
        -h or --help: print help document
        -e: file extension for -d, "csv" or "xlsx" (default 'csv')
        -v: verbose mode
    '''
    # read arguments from command line and parse options
    arg_list = sys.argv[1:]
    short_opts = 'a:f:e:s:hv'
    long_opts = ['help','acc_cat=']
    global verbose
    verbose = False
    try:
        opt_list = getopt.getopt(arg_list, short_opts, long_opts)[0]
    except getopt.error as error:
        sys.exit(error)
    
    if (('--help','') in opt_list) or (('-h','') in opt_list) or len(arg_list) == 0:
        print(help_msg)
        sys.exit(0)
    
    if ('-v','') in opt_list:
        verbose = True
    
    # initialize variables and process arguments
    dir_name,file_list,acc_file,acc_cat,save_name = None, None, None, None, None
    search_pattern = 'csv'
    for current_arg, current_val in opt_list:
        if current_arg == '-f':
            if Path(current_val).is_file():
                file_list = [current_val]
            elif Path(current_val).is_dir():
                dir_name = current_val
            else:
                print('Please provide valid path to data file or directory.')
        elif current_arg == '-e':
            search_pattern = current_val
            msg(f'Search pattern changed to "{search_pattern}"')
        elif current_arg == '-a':
            if Path(current_val).is_file():
                acc_file = [current_val]
            elif Path(current_val).is_dir():
                acc_file = search_files(current_val, '*ac_reformatted.csv',recursive=True)
            else:
                print('Please provide valid path to acceleration file or directory.')
        elif current_arg == '--acc_cat':
            acc_cat = current_val
        elif current_arg == '-s':
            save_name = current_val
    
    if dir_name is not None:
        file_list = search_files(dir_name,search_pattern)
        if len(file_list) == 0:
            sys.exit(f'Error: No file with pattern "{search_pattern}" found within {dir_name}.')

    # Load data
    msg('Loading measurement data.')
    measurements = pd.DataFrame()
    for f in file_list:
        if Path(f).suffix == '.csv':
            measurements = pd.concat([measurements,load_csv(f)])
        elif Path(f).suffix == '.xlsx':
            measurements = pd.concat([measurements,load_excel(f)])
    
    msg('Loading acceleration data.')
    acc_df = pd.DataFrame()
    if acc_cat is not None:
        categorized_acc = load_csv(acc_cat,file_type='acc_cat')
    else:
        for f in acc_file:
            acc_df = pd.concat([acc_df,load_csv(f,file_type = 'acc')])
    
    # Calculate primary sleep intervals
    msg('Calculating sleep intervals.')
    sleep_df = extract_kind(measurements, kind='sleep_total')
    sleep_intervals = preliminary_intervals(sleep_df)
    sleep_intervals = merge_intervals(sleep_intervals)
    
    # Find step increase
    dt = np.timedelta64(10,'m')
    step_df = extract_kind(measurements,kind='step')
    step_df = step_df[step_df['data'] > 0]
    step_increase = np.array([[t-dt,t] for t in step_df['date_time'].to_numpy()])
    
    # Subtract step increase periods from primary sleep intervals
    sleep_intervals = subtract_intervals(sleep_intervals,step_increase)
    
    msg('Processing and categorizing acceleration data.')
    if acc_cat is None:
        # Find baseline acceleration boundaries
        acc_thresh = sleep_acc_thresh(acc_df,sleep_intervals)
        categorized_acc = acc_categorize(acc_df, acc_thresh)
        categorized_acc = merge_windows(categorized_acc)
    active_periods = categorized_acc[categorized_acc['category'] != 'rest']
    final_cat_df = active_periods.copy()
    active_periods = active_periods[['start_time','end_time']].values
    
    # Subtract active periods from sleep periods
    sleep_intervals = subtract_intervals(sleep_intervals,active_periods)
    sleep_int_df = pd.DataFrame(sleep_intervals,columns=['start_time','end_time'])
    sleep_int_df['category'] = np.repeat('sleep',len(sleep_int_df))
    
    # Finish categorizing other status
    rest_periods = categorized_acc[categorized_acc['category'] == 'rest']
    rest_periods = rest_periods[['start_time','end_time']].values
    wake_rest_intervals = subtract_intervals(rest_periods,sleep_intervals)
    wake_rest_int_df = pd.DataFrame(wake_rest_intervals,columns=['start_time','end_time'])
    wake_rest_int_df['category'] = np.repeat('rest',len(wake_rest_int_df))
    
    final_cat_df = pd.concat([final_cat_df,sleep_int_df,wake_rest_int_df],ignore_index=True)
    final_cat_df.sort_values(by = 'start_time', inplace = True)
    final_cat_df.reset_index(drop=True, inplace=True)
    
    # Saving data
    # Things to save: sleep_intervals, rest_intervals (rest acc subtract sleep_interval)
    msg('Saving results.')
    if acc_cat is None:
        thresh_save_name = save_name + '_sleep_acc_thresholds.csv'
        with open(thresh_save_name,'w') as f:
            f.write(f'lower_threshold,{acc_thresh[0]}\nupper_threshold,{acc_thresh[1]}\n')
        acc_cat_save_name = save_name + '_acc_category.csv'
        categorized_acc.to_csv(acc_cat_save_name,index=False)
    category_df_save_name = save_name + '_activity_categorized.csv'
    final_cat_df.to_csv(category_df_save_name,index=False)
    msg('All done.')

    
if __name__ == '__main__':
    import sys, os, getopt, glob
    import pandas as pd
    import numpy as np
    from pathlib import Path
    from openpyxl import load_workbook
    main()