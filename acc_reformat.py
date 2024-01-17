import sys, os, getopt
from pathlib import Path
from datetime import datetime
import pandas as pd
import math
from ast import literal_eval # Use ast.literal_eval to convert the string representation of list to acutual list

def main():
    # Help message:
    help_msg ='''This script reformats the accelerome records and calculate acceleration from the 3 recorded components.

    Usage: python acc_reformat.py -f <filename> [options]

    Arguments:
        -f: .csv file containing accelerometer data from raw files

    Options:
        -h or --help: print help document
        -b: bin size in seconds, 300s by default
        -v: Verbose mode
    '''
    
    arg_list = sys.argv[1:]
    short_opts = 'f:b:hv'
    long_opts = ['help']
    global verbose
    verbose = False
    
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
    file_name = ''
    binsize = 300
    
    # Parse options
    for current_opt,current_val in opt_list:
        if current_opt == '-f':
            file_name = validate_file(current_val,accepted_formats=['.csv'])[0]
        elif current_opt == '-b':
            msg(f'Bin size set to: {current_val} seconds')
            binsize = current_val
    
    if file_name == '':
        print('Missing file name. Exiting.')
        sys.exit(2)
    
    base_name=Path(file_name).absolute().parts[-2]
    out_name=str(Path(file_name).parent) + "/0_" + base_name + "_ac_reformatted.csv"
    if Path(out_name).exists():
        print(f'{out_name} already exist, skipping.')
        sys.exit(0)
    
    msg(f'Processing {file_name}')
    ac=pd.read_csv(file_name)
    ac['data']=ac['data'].apply(lambda x: literal_eval(x))
    ac['date_time'] = pd.to_datetime(ac['date_time'])
    
    acc_df=acc_flatten(ac,match_range=6)
    msg('Data reformatting completed. Calculating combined accelerations...')
    seconds=[]
    intervals=[]
    acc=[]
    for i in range(0,len(acc_df),1):
        s=acc_df["date_time"][i].hour*3600+acc_df["date_time"][i].minute*60+acc_df["date_time"][i].second+acc_df["date_time"][i].microsecond/1000000
        seconds.append(s)
        n=math.floor(s/binsize)
        intervals.append(n)
        g=math.sqrt(acc_df['acx'][i]**2+acc_df['acy'][i]**2+acc_df['acz'][i]**2)
        acc.append(g)
    acc_df['seconds']=seconds
    acc_df['bin']=intervals
    acc_df['g_force']=acc
    
    acc_df.to_csv(out_name,index=False)
    msg(f'Completed. Saved to {out_name}\n')
    
# verbose function for printing messages
def msg(text):
    global verbose
    if verbose == True:
        print(text)

# Functions to convert the accceleration data to a single table with x, y, and z values on each row
def acc_flatten(ac,match_range=6):
    # set the top row containing a dummy datetime value
    top_row = pd.DataFrame({'kind':'ac','date_time':datetime.fromtimestamp(1),'data':'NA'},index=[0])
    # extract the three components of the acceleration
    ac_slim=ac[['kind','date_time','data']]
    acx=pd.concat([top_row,ac_slim[ac_slim['kind']=='acx']]).reset_index(drop=True)
    acx['date_time'] = pd.to_datetime(acx['date_time'])
    acy=pd.concat([top_row,ac_slim[ac_slim['kind']=='acy']]).reset_index(drop=True)
    acy['date_time'] = pd.to_datetime(acy['date_time'])
    acz=pd.concat([top_row,ac_slim[ac_slim['kind']=='acz']]).reset_index(drop=True)
    acz['date_time'] = pd.to_datetime(acz['date_time'])
    nrows_ac = min(len(acx),len(acy),len(acz))
    if nrows_ac==0:
        raise Warning('Missing at least one of: acx, acy, acz. Process stopped.')
        return
    # match up timestamps from the three dataframes
    msg('Matching acceleration timestamps.')
    acc_filt=match_acc(acx,acy,acz,n=match_range)
    acx,acy,acz=acc_filt[0],acc_filt[1],acc_filt[2]
    nrows_ac = min(len(acx),len(acy),len(acz))
    msg(str(nrows_ac) + " records in the filtered data. Starting to reformat.")

    # Make a new dataframe with 4 columns
    df = pd.DataFrame(columns=['acx','acy','acz','date_time'])
    start_row = 0
    start_time = datetime.fromtimestamp(1)
    for i in range(1,nrows_ac,1):
        dt=(acx['date_time'][i]-acx['date_time'][i-1]).total_seconds()
        if dt>1: # reset start row and time if the gap is more than a second
            start_row = i
            start_time = acx['date_time'][i]
        t_smooth=smooth_timestamp(start_row,i,start_time)
        df_row=pd.DataFrame({'acx':acx['data'][i],'acy':acy['data'][i],'acz':acz['data'][i],'date_time':t_smooth})
        df=pd.concat([df,df_row])
        if i%1000 == 0:
            msg(str(i) + '/' + str(nrows_ac) +' records processed.')
    df.reset_index(drop=True,inplace=True)
    df['date_time']=pd.to_datetime(df['date_time'])
    return df

# Function to check that the three timestamps are within 0.5 seconds
def xyz_match(x,y,z,t=0.5):
    a=abs((x-y).total_seconds())
    b=abs((y-z).total_seconds())
    c=abs((y-z).total_seconds())
    if max(a,b,c)>t:
        return False
    else: 
        return True

# Function to find closest matches in following rows if current row doesn't match
def find_match(list_x,list_y,list_z,t=0.4):
    # generate all possible combinations of timestamps
    t_comb=[]
    i=0
    while i < len(list_x):
        j=0
        while j < len(list_y):
            k=0
            while k < len(list_z):
                m=xyz_match(list_x[i],list_y[j],list_z[k],t=t)
                comb=(i,list_x[i],j,list_y[j],k,list_z[k],i+j+k,m)
                t_comb.append(comb)
                k=k+1
            j=j+1
        i=i+1
    t_comb=pd.DataFrame(t_comb,columns=['index_x','time_x','index_y','time_y','index_z','time_z','total_changes','xyz_match'])
    t_comb.sort_values(by='total_changes',inplace=True)
    t_comb.reset_index(drop=True,inplace=True)
    # find the first matching combo
    for i in range(0,len(t_comb),1):
        if t_comb['xyz_match'][i]:
            return [t_comb['index_x'][i],t_comb['index_y'][i],t_comb['index_z'][i]]
            break
    return []

# Function to test if the current row matches; if not, find_match is called
def match_acc(x,y,z,n):
    a=0
    t_x=x['date_time'].tolist()
    val_x=x['data'].tolist()
    t_y=y['date_time'].tolist()
    val_y=y['data'].tolist()
    t_z=z['date_time'].tolist()
    val_z=z['data'].tolist()
    # remove any necessary values
    while a<(len(t_x)-n) and a<(len(t_y)-n) and a<(len(t_z)-n):
        if not xyz_match(t_x[a],t_y[a],t_z[a]):
            lx,ly,lz=t_x[a:a+n],t_y[a:a+n],t_z[a:a+n]
            first_match=[]
            first_match=first_match+find_match(lx,ly,lz)
            ### Automatically increase n if match is not found. ###
            while len(first_match)==0:
                n=n+2
                msg('Match range increased to ' + str(n))
                lx,ly,lz=t_x[a:a+n],t_y[a:a+n],t_z[a:a+n]
                first_match=[]
                first_match=first_match+find_match(lx,ly,lz)
                
            for i in range(0,first_match[0],1):
                t_x.pop(a)
                val_x.pop(a)
            for i in range(0,first_match[1],1):
                t_y.pop(a)
                val_y.pop(a)
            for i in range(0,first_match[2],1):
                t_z.pop(a)
                val_z.pop(a)
        a=a+1
    # there are n rows at the end that this loop will not process. Since n is relatively small, those rows are just discarded.
    del t_x[a:len(t_x)]
    del val_x[a:len(val_x)]
    del t_y[a:len(t_y)]
    del val_y[a:len(val_y)]
    del t_z[a:len(t_z)]
    del val_z[a:len(val_z)]
    # make three new dataframes to return
    new_x=pd.DataFrame({'date_time':t_x,'data':val_x})
    new_y=pd.DataFrame({'date_time':t_y,'data':val_y})
    new_z=pd.DataFrame({'date_time':t_z,'data':val_z})
    return new_x,new_y,new_z

# Function to smooth the timestamp gaps to 0.1 second
def smooth_timestamp(start_row,current_row,start_time):
    local_format='%Y-%m-%d %H:%M:%S.%f'
    start_time=datetime.timestamp(start_time)
    t0=(start_time-0.4)+0.5*(current_row-start_row)
    t1,t2,t3,t4=t0+0.1,t0+0.2,t0+0.3,t0+0.4
    t0f=datetime.fromtimestamp(t0).strftime(local_format)
    t1f=datetime.fromtimestamp(t1).strftime(local_format)
    t2f=datetime.fromtimestamp(t2).strftime(local_format)
    t3f=datetime.fromtimestamp(t3).strftime(local_format)
    t4f=datetime.fromtimestamp(t4).strftime(local_format)
    return [t0f,t1f,t2f,t3f,t4f]

### validate file or directory exists
def validate_file(file_path,accepted_formats=''): 
    if Path(file_path).exists():
        if (accepted_formats != '') and (Path(file_path).suffix in accepted_formats):
            return([os.path.abspath(file_path),Path(file_path).suffix])
        elif (accepted_formats != '') and (Path(file_path).suffix not in accepted_formats): 
            print(f'Invalid file format: {Path(file_path).parts[-1]}{os.linesep}Must be {" or ".join(accepted_formats)} file.')
            sys.exit(2)
        else:
            return(os.path.abspath(file_path))
    else:
        print(f'Error: "{file_path}" does not exist!')
        sys.exit(2)    

if __name__ == '__main__':
    main()
