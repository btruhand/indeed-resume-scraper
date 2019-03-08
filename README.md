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

```bash
PATH=$(pwd):$PATH
```

You can also modify the `PATH` variable in files like `.bashrc` and `.bash_profile` to persist the change (though you would need to
statically set the directory path of where you put the scraper folder and not use `$(pwd)`)

# Running script

```bash
usage: indeed-resume-scraper.py [-h] -q query --name name [-l location]
                                [-si start] [-ei end] [--processes processes]
                                [--override] [--driver {firefox,chrome}]
                                [--login] [--simulate-user] [--headless]

Scrape Indeed Resumes

optional arguments:
  -h, --help            show this help message and exit
  -l location           location scope for search (default: canada)
  -si start             starting index (multiples of 50) (default: 0)
  -ei end               ending index (multiples of 50) (default: 1050)
  --processes processes
                        # of processes to run (max 4) (default: 1)
  --override            override existing result if any (default: False)
  --driver {firefox,chrome}
  --login               Simulate logging in as a user (read README further for
                        details) (default: False)
  --simulate-user       Whether to simulate user clicks or not (slower)
                        (default: False)
  --headless            Run browsers in headless mode (default: False)

required arguments:
  -q query              search query to run on indeed e.g software engineer
                        (default: None)
  --name name           name of search (used to save files, lowercased and
                        spaces turned to "-") (default: None)
```

## Simulating logging in
It seems that Indeed blocks non-loggedin user to get resume results above a certain point
(so far the ceiling seems to be 1050 resumes). However logging in seems to circumvent this.

The `--login` option allows you to do this. You would need to set the environemnt variables
`INDEED_RESUME_USER` and `INDEED_RESUME_PASSWORD`. If not, the program will exit telling you
that you need to set those environment variables.

So you do the following
```bash
export INDEED_RESUME_USER=<your indeed login user>
export INDEED_RESUME_PASSWORD=<your indeed user password>
```

You can do it for the current terminal session, or put it somewhere so it persists over sessions
e.g your `.bashrc` or `.bash_profile` file.

Due to the restriction that Indeed imposes for non login scraping, `-si` and `-ei` options
are automatically constrained to a minimum `0` and maximum of `1050` respectively when `--login` option is not specified

## Simulating user behaviour
User behaviour can be simulated using the `--simulate-user` option. Using this, it seems that
throttling is severely mitigated, and overall helps for a smoother scraping experience

## Multiprocessing
By default the program runs with one process, but the `--processes` option can be given to indicate
the number of processes to use. The maximum number of processes allowed is `4`.

**NOTE**: If more than `1` process is to be used it is highly encouraged to turn on `--simulate-user` due to throttling
mechanisms. Higher number of processes also may incur further throttling so be careful.

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