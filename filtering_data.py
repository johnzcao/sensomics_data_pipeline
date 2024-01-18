# verbose function for printing messages
def msg(text):
    global verbose
    if verbose == True:
        print(text)

# recursive search for all files within the given master folder that fits a pattern
def search_files(dirname,pattern):
    msg(f'Searching files with the pattern "{pattern}"...')
    search_str = os.path.abspath(dirname) + '/**/*' + pattern
    file_list = glob.glob(search_str,recursive=True)
    return(sorted(file_list))

# data loading functions
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
    return int(hs[0])*60+int(hs[1])

def load_file(file_list,suffix):
    df = pd.DataFrame()
    if suffix == '.csv':
        for f in file_list:
            msg(f'Loading {str(Path(f).parts[-1])}')
            new_df = pd.read_csv(f)
            new_df['date_time'] = pd.to_datetime(new_df['date_time'])
            df = pd.concat([df,new_df], axis=0, ignore_index=True)
    elif suffix == '.xlsx':
        for f in file_list:
            msg(f'Loading {str(Path(f).parts[-1])}')
            new_df = load_excel(f)
            df = pd.concat([df,new_df], axis=0, ignore_index=True)
    else:
        print('Error: Unsupported file type. .csv or .xlsx files required.')
        sys.exit(2)
    df.sort_values(by=['kind', 'date_time'], inplace=True) 
    df['data'] = df['data'].apply(lambda x: float(x))
    df.reset_index(drop=True, inplace=True)
    msg(f'All done. {str(len(file_list))} file(s) loaded.')
    return(df)

# separate measurements into different dataframes
# if replace == True, then the filtered subset will be merged back to the input dataframe, replacing the original subset
def subset_df(df, kind, min_val=0, max_val=1000000, keep_na=False, replace = False):
    new_df = df[df['kind']==kind]
    if keep_na == False:
        new_df = new_df[((new_df['data']<=max_val) & (new_df['data']>=min_val))]
    else:
        new_df = new_df[((new_df['data']<=max_val) & (new_df['data']>=min_val)) | np.isnan(new_df['data'])]
    if replace == True:
        df1 = df[df['kind']!=kind]
        new_df = pd.concat([df1,new_df])
    new_df.reset_index(drop=True,inplace=True)
    return(new_df)

# filtering function. used on heart rate data to detect periods with abnormal recording (same number recorded for a long period of time)
def t_incl(df):
    df1 = df.copy()
    df1.reset_index(drop=True, inplace=True) # making sure indices of input dataframe is in order
    x = list(df1['data'])
    # itertools.groupby creates a generator object. 
    # When used on numerical list, each element consists of the name of repeating data (p here, same as the data value) and all instances of repeat (q here)
    # len(list(q)) expands q and count the length, i.e. the number of times p repeats in a row
    grouped_x = [(p, len(list(q))) for p,q in groupby(x)] 
    start = 0
    end = 0
    incl_time = list()
    for i,j in grouped_x:
        if j <= 20: # normal cases (extremely rare to see any normal recording to have any identical number repeating 20+ time in a row)
            end += j
            if end == len(x): # reaching the end of the list
                incl_time.append((df1['date_time'][start],df1['date_time'][end-1],1))
        else: # abnormal cases
            if end > start: # if there are previous normal records, record the previous interval first, then reset start to current value of end
                incl_time.append((df1['date_time'][start],df1['date_time'][end-1],1))
                start = end
            end += j
            incl_time.append((df1['date_time'][start],df1['date_time'][end-1],0)) # record abnormal interval (marked by 0 at the end)
            start = end
    return(incl_time)

# filter based on include/exclude time intervals established by t_incl()
def df_filter(df,t_intervals):
    msg(f'Total rows in input dataframe: {len(df)}')
    new_df = pd.DataFrame()
    for start,end,include in t_intervals:
        if include == 1:
            df_sub = df[(df['date_time'] >= start) & (df['date_time'] <= end)]
            new_df = pd.concat([new_df,df_sub],ignore_index=True)
        else:
            msg(f'    - Data between {start} and {end} discarded.')
    msg(f'Done. Total rows in filtered dataframe: {len(new_df)}')
    return(new_df)

def main():
    # Help message:
    help_msg ='''This script filters values in input files to remove noise.

    Usage: python filtering_data.py -f/-d <input_files/directory> -s save_name [options]

    Arguments:
        -f: input file, .xlsx or .csv
        -d: directory containing multiple data files, reads all .xlsx files by default (use -p to modify search pattern)
        -s: save file name (.csv)

    Options:
        -h or --help: print help document
        -p: search pattern for -d (default '*.xlsx')
            If pattern include wild card characters (* or ?), use quotation marks around the pattern
        -v: verbose mode
    '''
    # read arguments from command line and parse options
    arg_list = sys.argv[1:]
    short_opts = 'f:d:p:s:hv'
    long_opts = ['help']
    global verbose
    verbose = False
    try:
        opt_list = getopt.getopt(arg_list, short_opts, long_opts)[0]
    except getopt.error as err:
        print(str(err))
        sys.exit(2)
    
    if (('--help','') in opt_list) or (('-h','') in opt_list) or len(arg_list) == 0:
        print(help_msg)
        sys.exit(0)
    
    if ('-v','') in opt_list:
        verbose = True
            
    # check that one of -d or -f is used in arguments
    if ('-d' in arg_list) and ('-f' in arg_list):
        sys.exit('Error: -d and -f cannot be used together.')
    elif (not '-d' in arg_list) and (not '-f' in arg_list):
        sys.exit('Error: Require either -d or -f.')
    
    # initialize variables and process arguments
    dir_name,file_list,file_type,save_file = '','','',''
    search_pattern = '*.xlsx'
    for current_arg, current_val in opt_list:
        if current_arg == '-f':
            file_name = current_val
            file_list = [file_name]
        elif current_arg == '-d':
            dir_name = current_val
        elif current_arg == '-p':
            search_pattern = current_val
            msg(f'Search pattern changed to "{search_pattern}"')
        elif current_arg == '-s':
            save_file = current_val
    
    if save_file == '':
        print('Output file name or directory not provided (-s)')
        sys.exit()
    
    if dir_name != '':
        file_list = search_files(dir_name,search_pattern)
    if len(file_list) == 0:
        sys.exit(f'Error: No file with pattern "{search_pattern}" found within {dir_name}.' )

    # load data
    # detect file type
    if file_type == '':
        file_type = Path(file_list[0]).suffix
        # check if there's more than one file format
        for f in file_list:
            if file_type != Path(f).suffix:
                sys.exit(f'Error: With the current search pattern ({search_pattern}), there are more than one type of file in the input list ({file_type} and {Path(f).suffix}).')
        msg(f'Loading file type: {file_type}')

    hr_min = 50
    bp_dia_min, bp_sys_min = 60, 80
    spo2_min = 80
    st_min = 30


    # load computed data
    computed_df = load_file(file_list,file_type)
    # extract hr to detect abnormal measurements
    hr_df = computed_df[computed_df['kind']=='hr'].copy()
    t1 = t_incl(hr_df)
    computed_df_filt = df_filter(computed_df,t1)
    computed_df_filt = subset_df(computed_df_filt, 'hr', min_val=hr_min,replace=True)
    computed_df_filt = subset_df(computed_df_filt, 'bp_dia', min_val=bp_dia_min,replace=True)
    computed_df_filt = subset_df(computed_df_filt, 'bp_sys', min_val=bp_sys_min,replace=True)
    computed_df_filt = subset_df(computed_df_filt, 'spo2', min_val=spo2_min,replace=True)
    computed_df_filt = subset_df(computed_df_filt, 'st', min_val=st_min,replace=True)
    computed_df_filt.sort_values(by=['kind','date_time'],inplace=True)
    computed_df_filt.to_csv(save_file,index = False)
    return

if __name__ == '__main__':
    import glob, os, getopt, sys
    import pandas as pd
    from pathlib import Path
    import numpy as np
    from itertools import groupby
    from openpyxl import load_workbook
    main()
    
    
