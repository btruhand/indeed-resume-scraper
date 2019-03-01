Scrape resumes from indeed

# Setup
Install `requirements.txt` for your `Python` environment e.g
```
pip install -r requirements.txt
```

or

```
conda install --file requirements.txt
```

A Mac version `geckodriver` is installed. If you use Mac and have Firefox you can use it. If not please, follow the
driver installations for your platform and desired browser (you can use either `Chrome` or `Firefox`) as mentioned [here](https://selenium-python.readthedocs.io/installation.html).

You would need to put it to some directory that is in your PATH e.g `/usr/local/bin`.
Alertnatively you can put the drivers into this directory and add
this directory into your path:

```
PATH=$(pwd):$PATH
```

# Running script

```bash
usage: indeed-scraper.py [-h] -q query --name name [-l location] [-si start]
                         [-ei end] [--override] [--driver {firefox,chrome}]

Scrape Indeed Resumes

optional arguments:
  -h, --help            show this help message and exit
  -l location           location scope for search (default: Canada)
  -si start             starting index (multiples of 50) (default: 0)
  -ei end               ending index (multiples of 50) (default: 5000)
  --override            override existing result if any (default: False)
  --driver {firefox,chrome}

required arguments:
  -q query              search query to run on indeed e.g software engineer
                        (default: None)
  --name name           name of search (used to save files, spaces turned to
                        "-") (default: None)
```

## Simulating logging in
It seems that Indeed blocks non-loggedin user to get resume results above a certain point
(so far the ceiling seems to be 1050 resumes). However logging in seems to circumvent this.

The `--login` option allows you to do this. You would need to set the environemnt variables
`INDEED_RESUME_USER` and `INDEED_RESUME_PASSWORD`. If not, the program will exit telling you
that you need to set those environment variables

## Example
Scrape 100 resumes (1st - 100th resume) for software engineering in Canada
```bash
python indeed-scraper.py -q 'software engineer'  --name software-canada -ei 100
```

## Multiple queries
The `script.sh` can be run with a file that has a job title per line
```
./script.sh <filename>
```

Please read `script.sh` for some more details (you may modify as needed)