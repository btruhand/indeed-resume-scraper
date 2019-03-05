#!/usr/bin/env bash
# Usage: ./script.sh <file with job titles>
# Assumes each line is a job title
# Defaults search to be in Canada
# Defaults search for 5000 resumes
# Defaults override

FILE=$1

while read -u 3 job || [ -n "$job" ]; do
    echo "Searching resumes for ${job}"
    python3 indeed-resume-scraper.py -q "$job" --name "$job-canada" -si 0 -ei 10000 --driver chrome --processes 2 --login --simulate --headless --override 2> scrape-"$job-canada".log
    read -u 1 -t 5 -p "Stop searching? (y/n) " isStop
    if [[ "$isStop" == "y" ]]; then
        break
    fi
done 3< "$FILE"
