#!/bin/bash
# organizing all .json files into folders by date
# This script assumes that all input files are from the same subject
# Execute the script in the folder containing all .json files. 
# Requires subject number as an input for proper naming of the folders. e.g. "sh organize_raw_file.sh -s 23", where 23 is the subject number.

verbose=0
work_dir="./"
subject=""
prefix="0729stanford"
id_pattern="(\w\w-){5}\w\w_\d{4}(-\d\d){2}" # e.g. "E0-77-5D-CB-FF-18_2022-01-26". Change regex if id pattern changes in the future
function help_msg() 
{
    echo "This is a script to organize all .json files into folders by dates."
    echo "    Usage:
        sh 00_raw_file_organizing.sh -s <subject_ID> [Options]"
    echo "    Options:
        -h  Display help message
        -s  Subject ID (required). 
        -d  Define working directory (if not current directory)
        -i  Redefine ID pattern with regular expression. ID pattern is the part in the file name that specify which subject the file belongs to and will be included in the folder names.
            Default is \"(\w\w-){5}\w\w_\d{4}(-\d\d){2}\" (six alphanumeric pairs separated by dash, followed by an underscore, followed by numerical date YYYY-MM-DD)
        -p  Prefix name, default is \"0729stanford\" to match up with the computed files.
        -v  Verbose mode (print all log messages)"
    exit 1
}

# in case no value argument is provided to the script, print help message
if [ -z "$1" ]
then
    help_msg
fi

while getopts 'hvd:i:p:s:' args
do
    case "$args" in
        h)
        help_msg;;
        v)
        verbose=1
        echo "Verbose mode is on.";;
        d)
        work_dir=$OPTARG
        echo "Working directory: "$work_dir;;
        i)
        id_pattern=$OPTARG
        echo "ID pattern has been changed to "$id_pattern;;
        p)
        prefix=$OPTARG
        echo "Prefix has been changed to "$prefix;;
        s)
        subject=$OPTARG
        echo "subject ID is "$subject;;
    esac
done

if [[ "$subject" == "" ]]
then
    echo 'Missing subject ID (-s option). Exiting.'
    exit 2
fi

cd $work_dir
if [[ "$verbose" == 1 ]]
then 
    echo "Current directory: "$(pwd)
fi

full_pref=$(echo $prefix$subject"_") # define the directory prefix

# Report total files to be processed
files=(*.json)
N=${#files[@]}
unset files
echo "Total .json files: "$N

# Set up counter
n=0

# Start looping through .json files

for i in *.json
do
    # Find and extract the sub-string that contains the unique identifier sequence and the date
    # prefix is added to the front to complete the directory name
    id=$(grep -o -E '(\w{2}-){5}\w{2}_\d{4}(-\d{2}){2}' <<< $i)
    dir=$full_pref$id 
    
    # Create directory if not already existsing
    if [ ! -d $dir ]
    then
        mkdir $dir
        if [[ "$verbose" == 1 ]]
        then
            echo "New directory: "$dir
        fi
    fi

    # move current file into the directory
    mv "$i" $dir/
    
    # report progress 
    n=$((n+1))
    if [ $((n % 100)) -eq 0 ] 
    then
        if [[ "$verbose" == 1 ]]
        then
            echo $n" / "$N" files moved"
        fi
    fi
done

echo "Finished. Total files moved: "$n


