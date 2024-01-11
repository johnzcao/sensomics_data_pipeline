
def msg(text):
    global verbose
    if verbose == True:
        print(text)

def extract_zip(archive,dst):
    try:
        with zipfile.ZipFile(archive,'r') as zf:
            file_list = zf.namelist()
            zf.extractall(dst)
    except Exception as err:
        print(err)
    if not verbose:
        return
    msg(f'{archive}: {len(file_list)} files in total.')
    ext_list = [Path(x).suffix for x in file_list]
    file_type_summary = [(x,len(list(y))) for x,y in groupby(ext_list)]
    for f,n in file_type_summary:
        msg(f'\t{n} {f} files.')

# find the longest string that is a part of every file name
def auto_stem_detect(computed_file_dir : str, file_ext = 'xlsx'):
    search_pat = str(Path(computed_file_dir)) + '/*' + file_ext
    path_list = glob.glob(search_pat)
    name_list =[Path(f).stem for f in path_list]
    name_list = [x[0:len(x)-11] for x in name_list] # remove date from stem
    unique_stems = list(set(name_list))
    if len(unique_stems) == 1:
        msg(f'Using "{unique_stems[0]}" as name stem.')
        return(unique_stems[0])
    else:
        print('Multiple possible stem found:')
        for i in range(len(unique_stems)):
            print(f'\t{i}: {unique_stems[i]}')
        index = input(f'Please choose the name stem to use (0-{len(unique_stems)-1}): ')
        try:
            return(unique_stems[int(index)])
        except Exception as err:
            print(err)
            return(None)

def make_dirs(file_list,name_stem):
    date_list = list(set([re.findall('\d{4}-\d{2}-\d{2}',f)[0] for f in file_list]))
    for d in date_list:
        msg(f'Making directory for date: {d}')
        dir_name = name_stem + '_' + d
        if Path(dir_name).exists():
            msg(f'{dir_name} already exist. Moving on to the next date.')
            continue
        os.mkdir(dir_name)
        msg(f'Created directory: {dir_name}')
    return

def sort_files(file_list,name_stem):
    for f in file_list:
        f_date = re.findall('\d{4}-\d{2}-\d{2}',f)[0]
        dst_dir = name_stem + '_' + f_date
        shutil.move(f,dst_dir)
        msg(f'Moved {f} to {dst_dir}')
    

def main():
    help_msg ='''This script unzip and sort all raw data to folders organized by date. 
        
    Usage: python 01_organize_raw_files.py -d <dirname> -o <output_name_stem> [options]
        
    Arguments:
        -d: directory containing all files to process
            Can be zip or json format, but not a mix of both. See -j option below
        -o: output folder name stem. Modified by -c option.
            e.g., "-o example" will create folders like "example_2021-09-08/", "example_2021-09-09/", etc.
            Can be preceded with a path to appropriate output folders, e.g., -o ~/Save/files/here/example 

    Options:
        -h or --help: print help document
        -j: Process .json files instead of .zip files (the default format). 
        -c: Modifies -o behavior to automatically find name stem according to matching computed data file names.
            Looks for .xlsx files in the provided folder instead of taking the argument as name stem
            e.g., "-o Computed/ -c" will find the name stem used in .xlsx files in the "Computed/" folder.
            
        -v: Verbose mode
    '''
    arg_list = sys.argv[1:]
    short_opts = 'd:o:cjhv'
    long_opts = ['help']
    global verbose
    verbose = False
    
    try:
        opt_list = getopt.getopt(arg_list, short_opts, long_opts)[0]
    except getopt.error as err:
        sys.exit(err)
    
    if (('--help','') in opt_list) or (('-h','') in opt_list) or len(opt_list)==0:
        print(help_msg)
        sys.exit(0)
    
    if ('-v','') in opt_list:
        verbose = True
    
    # Initialize variables
    file_format = 'zip'
    auto_stem = False
    src_dir, output_stem = None, None
    zip_list = None
    for current_arg, current_val in opt_list:
        if current_arg == '-d':
            src_dir = current_val
            if not Path(src_dir).is_dir():
                sys.exit(f'Invalid path: {src_dir}')
        if current_arg == '-o':
            output_stem = current_val
        if current_arg == '-c':
            auto_stem = True
        if current_arg == '-j':
            file_format = 'json'
            
    if src_dir is None or output_stem is None:
        sys.exit('Missing -d or -o arguments, exiting.')
        
    if auto_stem:
        if not Path(output_stem).is_dir():
            sys.exit(f'Invalid path: {output_stem}')
        output_stem = auto_stem_detect(output_stem)
    else:
        if not Path(output_stem).parent.is_dir():
            sys.exit(f'Invalid path: {Path(output_stem).parent}')
    
    # unzip all files
    if file_format == 'zip':
        search_pat = str(Path(src_dir)) + '/*.zip'
        zip_list = glob.glob(search_pat)
        for f in zip_list:
            extract_zip(f, src_dir)
    
    # find all .json files
    search_pat = str(Path(src_dir)) + '/*.json'
    file_list = glob.glob(search_pat)
    
    # create output directories
    make_dirs(file_list, output_stem)
    
    # sort files in file_list into output directories
    sort_files(file_list, output_stem)
    
    if zip_list is None:
        print('All files sorted.')
        sys.exit(0)
    
    print('All files unzipped and sorted. Delete original zip files?')
    remove = input('Caution: deleted files are not recoverable. (Y/N): ')
    
    if remove == 'Y' or remove == 'y':
        for f in zip_list:
            os.remove(f)
            msg(f'{f} removed')
        print('All zip files removed')  
        sys.exit(0)
    
    print('Original zip files are preserved.')


if __name__ == '__main__':
    import os,sys,getopt,glob,re
    import zipfile,shutil
    from pathlib import Path
    from itertools import groupby
    main()
