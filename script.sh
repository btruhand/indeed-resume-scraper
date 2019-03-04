#!/usr/bin/env bash
# Usage: ./script.sh <file with job titles>
# Assumes each line is a job title
# Defaults search to be in Canada
# Defaults search for 5000 resumes
# Defaults override

FILE=$1

while read -u 3 job || [ -n "$job" ]; do
    echo "Searching resumes for ${job}"
    python3 indeed-resume-scraper.py -q "$job" --name "$job" -ei 1050 --override --driver chrome
    read -u 1 -t 5 -p "Stop searching? (y/n) " isStop
    if [[ "$isStop" == "y" || -z "$isStop" ]]; then
        break
    fi
done 3< "$FILE"
