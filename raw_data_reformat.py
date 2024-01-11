### recursive search for all files within the given master folder that fits a pattern
def search_files(dirname,pattern,recursive = False):
    print(f'Searching files with the pattern "{pattern}"...')
    if (recursive == True):
        search_str = os.path.abspath(dirname) + '/**/*' + pattern + '*'
    else:
        search_str = os.path.abspath(dirname) + '/*' + pattern + '*'
    file_list = glob.glob(search_str,recursive=recursive)
    return(sorted(file_list))

# timestamp_diff will take precedence over ref_time
# File refference pattern searches for the full timestamp within the file name (i.e. ####-##-## ##-##-##), can be edited
def load_json(dirname, timestamp_diff=None, ref_time=None, file_ref_pattern='\d\d\d\d-\d\d-\d\d\s\d\d-\d\d-\d\d', verbose=False, recursive=False): 
    jdata=pd.DataFrame()
    if dirname==None:
        print('Error: Missing directory name.')
        sys.exit(2)
    file_list = search_files(dirname,'.json',recursive=recursive)
    for filename in file_list:
        if verbose == True:
            print(f'Loading file: {filename}')
        j_id=re.search(file_ref_pattern,filename) # this is the time in the file name
        if j_id == None:
            print(f'Could not find timestamp pattern ({file_ref_pattern}) in file name: {filename}')
            j_id = ''
        else:
            j_id = j_id.group(0)
        j = pd.read_json(filename)
        j['jname'] = j_id
        jdata=pd.concat([jdata,j],ignore_index=True)
    if verbose == True:
        print('All data loaded')    
    jdata=adjust_time(jdata, d_time=timestamp_diff,excel_time=ref_time,dirname=dirname)
    jdata=convert_date_time(jdata)
    jdata.sort_values(by=['kind', 'date_time'], inplace=True)
    
    return(jdata)

def adjust_time(df, excel_time, d_time, dirname):
    if excel_time==None and d_time==None:
        df['adj_time'] = df['time'].apply(lambda x: x)
    elif d_time!=None:
        df['adj_time'] = df['time'].apply(lambda x: int(x + d_time))
        print('Using d_time.')
    else:
        json_time = min(df['time'])
        d_time = round((excel_time*1000 - json_time)/900000)*900000
        # excel timestamp is second precision, json timestamp is millisecond precision
        df['adj_time'] = df['time'].apply(lambda x: int(x + d_time))
        print('Using excel_time')
    # saving d_time for future use
    dirname=Path(dirname)
    filename=str(dirname.parent.parent) + '/timestamp_diff.txt'
    with open(filename,'w') as f:
        f.write(str(d_time))
    return(df)

def convert_date_time(df):
    local_format='%Y-%m-%d %H:%M:%S.%f' # including the milliseconds in the time
    df['date_time']=pd.to_datetime(df['adj_time'].apply(lambda x: 
                                                        datetime.fromtimestamp(x/1000).strftime(local_format)))
    df.drop(['time','adj_time'],axis = 1,inplace=True)
    df['date']=df['date_time'].apply(lambda x: x.date())
    df['time']=df['date_time'].apply(lambda x: x.time())
    return(df)

def json_data_cleanup(df, save_as_csv=False, dirname=None, verbose=False):
    '''
    ppg will be stored in a separate df
    hr current, hr, st, and spo2 need to be unlisted to numerical values
    bp needs to be separated to bp_sys and bp_dia
    multi measure needs to by separated to mm_hr, mm_spo2, mm_bp_sys, mm_bp_dia, and mm_st
    activity needs to be separated to step, Calories, sleep_light, sleep_deep, and awake
    all sub-functions contains a len(df1)>0 statement, so that empty df are skipped instead of causing errors
    '''
    ppg=df[df['kind']=='ppg']
    ppg=ppg.reset_index(drop=True)
    acx=df[df['kind']=='acx']
    acy=df[df['kind']=='acy']
    acz=df[df['kind']=='acz']
    ac=pd.concat([acx,acy,acz],ignore_index=True)
    ac.sort_values(by='date_time')
    a=unlist_values(df)
    b=unlist_bp(df)
    c=unlist_activity(df)
    d=unlist_multi_measure(df)
    new_df=pd.concat([a,b,c,d], ignore_index=True)
    new_df.sort_values(by=['kind','date_time'])
   
    if save_as_csv==True:
        base_name=Path(dirname).parts[-1]
        # adding '0_' to the file names so that they can be sorted on top
        filename1=dirname + '/0_' + base_name + '_measurements.csv'
        filename2=dirname + '/0_' + base_name + '_ppg.csv'
        filename3=dirname + '/0_' + base_name + '_ac.csv'
        if verbose == True:
            print('Saving to csv files..')
            print(f'    - Saving {filename1}')
            print(f'    - Saving {filename2}')
            print(f'    - Saving {filename3}')
        new_df.to_csv(filename1,index=False)
        ppg.to_csv(filename2,index=False)
        ac.to_csv(filename3,index=False)    
    return

def unlist_values(df):
    df1=df[df['kind'].isin(['hr current', 'hr', 'st', 'spo2'])].copy()
    if len(df1) > 0:
        df1['data']=df1['data'].apply(lambda x: x[0] if isinstance(x,list) else x)
    else:
        pass
    return(df1)

def unlist_bp(df):
    df1=df[df['kind']=='bp'].copy()
    if len(df1) > 0:
        df1[['bp_sys','bp_dia']]=pd.DataFrame(df1.data.tolist(), index= df1.index)
        df1.drop(['data','kind'],axis = 1,inplace=True)
        df1=pd.melt(df1, id_vars=['jname','date_time','date','time'],value_vars=['bp_sys','bp_dia'],
                value_name='data',var_name='kind')
    else:
        pass
    return(df1)

def unlist_activity(df):
    df1=df[df['kind']=='activity'].copy()
    if len(df1) > 0:
        df1[['step','Calories','sleep_light','sleep_deep','awake']]=pd.DataFrame(df1.data.tolist(), index= df1.index)
        df1.drop(['data','kind'],axis = 1,inplace=True)
        df1=pd.melt(df1, id_vars=['jname','date_time','date','time'],
                    value_vars=['step','Calories','sleep_light','sleep_deep','awake'],
                    value_name='data',var_name='kind')
    else:
        pass
    return(df1)

def unlist_multi_measure(df):
    df1=df[df['kind']=='multi measure'].copy()
    if len(df1) > 0:
        df1[['mm_hr', 'mm_spo2', 'mm_bp', 'mm_st']]=pd.DataFrame(df1.data.tolist(), index= df1.index)
        df1[['mm_bp_sys','mm_bp_dia']]=pd.DataFrame(df1.mm_bp.tolist(), index= df1.index)
        df1.drop(['data','kind','mm_bp'],axis = 1,inplace=True)
        df1=pd.melt(df1, id_vars=['jname','date_time','date','time'],
                    value_vars=['mm_hr', 'mm_spo2', 'mm_bp_sys','mm_bp_dia', 'mm_st'],
                    value_name='data',var_name='kind')
    else:
        pass
    return(df1)

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

# Help message:
help_msg ='''This script processes all .json files and convert them into .csv files for faster access in later steps.
Accelerations, ppg, and all other measurements will be split into 3 sepearate files. 
    
Usage: python 01_data_reformat.py -d <dirname> [options]
    
Arguments:
    -d: directory containing all .json files

Options:
    -h or --help: print help document
    -e: Provide matching computed data for timestamp matching
    -t: Provide existing timestamp difference file.
    -r: Recursive search mode
    -v: Verbose mode
'''

def main():
    arg_list = sys.argv[1:]
    short_opts = 'e:t:d:hv'
    long_opts = ['help']
    global verbose
    verbose = False
    recur = False
    
    try:
        opt_list = getopt.getopt(arg_list, short_opts, long_opts)[0]
    except getopt.error as err:
        print(str(err))
        sys.exit(2)
    
    if (('--help','') in opt_list) or (('-h','') in opt_list) or len(opt_list)==0:
        print(help_msg)
        sys.exit(0)
    
    if ('-v','') in opt_list:
        verbose = True
    
    # Initialize variables
    dir_name,xlsx_file,tdiff_file = '','',''    
    # Parse options
    for current_opt,current_val in opt_list:
        if current_opt == '-d':
            msg(f'Directory set to "{current_val}"')
            dir_name = validate_file(current_val)
        elif current_opt == '-e':
            msg(f'Matching time stamp with "{current_val}"')
            xlsx_file = validate_file(current_val)
        elif current_opt == '-t':
            msg(f'Timestamp difference file: "{current_val}"')
            tdiff_file = current_val
        elif current_opt == '-r':
            msg('Recursive search on.')
            recur = True
    
    if dir_name == '':
        print('Directory containing all .json files is not defined. Exiting.')
        sys.exit(2)
    
    if len(os.listdir(dir_name)) == 0:
        print("Empty directory, skipping.")
    elif (len(glob.glob(dir_name + '/0_*_measurements.csv'))==0) or (len(glob.glob(dir_name + '/0_*_ppg.csv'))==0) or (len(glob.glob(dir_name + '/0_*_ac.csv'))==0):
        if xlsx_file != '':
            e_df = load_excel(xlsx_file)
            min_time = datetime.timestamp(min(e_df['date_time']))
            j_df_all=load_json(dir_name, timestamp_diff=None, ref_time=min_time,verbose=verbose, recursive=recur)
            json_data_cleanup(j_df_all,save_as_csv=True,dirname=dir_name,verbose=verbose)
        elif tdiff_file != '':
            with open(tdiff_file) as f:
                dt=f.readlines()
                dt=int(dt[0])
            j_df_all=load_json(dir_name, timestamp_diff=dt, ref_time=None,verbose=verbose, recursive=recur)
            json_data_cleanup(j_df_all,save_as_csv=True,dirname=dir_name,verbose=verbose)
        else:
            j_df_all=load_json(dir_name, timestamp_diff=None, ref_time=None,verbose=verbose, recursive=recur)
            json_data_cleanup(j_df_all,save_as_csv=True,dirname=dir_name,verbose=verbose)
    else:
        print("Files exist, skipping.")

# verbose function for printing messages
def msg(text):
    global verbose
    if verbose == True:
        print(text)

### validate file or directory exists
def validate_file(file_path,accepted_formats=''): 
    if Path(file_path).exists():
        if (accepted_formats != '') and (Path(file_path).suffix in accepted_formats):
            return([file_path,Path(file_path).suffix])
        elif (accepted_formats != '') and (Path(file_path).suffix not in accepted_formats): 
            print(f'Invalid file format: {Path(file_path).parts[-1]}{os.linesep}Must be {" or ".join(accepted_formats)} file.')
            sys.exit(2)
        else:
            return(os.path.abspath(file_path))
    else:
        print(f'Error: "{file_path}" does not exist!')
        sys.exit(2)
    
if __name__ == '__main__':
    import sys, os, getopt, glob,re
    from pathlib import Path
    from datetime import datetime
    import pandas as pd
    main()