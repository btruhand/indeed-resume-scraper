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
python indeed-scraper.py -h
usage: python indeed-scraper.py <arguments>

Scrape Indeed Resumes

optional arguments:
  -h, --help         show this help message and exit
  -q query           search query to run on indeed e.g software engineer
  -l location        location scope for search
  -si start          starting index (multiples of 50)
  -ei end            ending index (multiples of 50)
  --threads threads  # of threads to run
  --override         override existing result if any
  --name name        name of search (used to save files)
```

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

Please read `script.sh` for some more details

