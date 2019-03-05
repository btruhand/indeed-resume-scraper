from selenium.webdriver import firefox, chrome
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
import time
import json
from random import randint
from time import sleep
from math import ceil
import os
import argparse
from urllib.parse import quote_plus, urlencode
import traceback
import sys
import concurrent.futures
import platform
import logging
import glob

# SCRAPING NECESSITY
NUM_INDEED_RESUME_RESULTS = 50
INDEED_RESUME_BASE_URL = 'https://resumes.indeed.com/resume/%s'
INDEED_RESUME_SEARCH_BASE_URL = 'https://resumes.indeed.com/search?%s'
INDEED_LOGIN_URL = 'https://secure.indeed.com/account/login'
NO_LOGIN_SEARCH_UPPER_LIMIT = 1050
MAX_PROCESSORS = 4

# RESUME SUBSECTIONS TITLE (in normal setting)
WORK_EXPERIENCE = 'Work Experience'
EDUCATION = 'Education'
SKILLS = 'Skills'
CERTIFICATIONS = 'Certifications'
ADDITIONAL_INFORMATION = 'Additional Information'

# INDICES
SKILL_NAME_INDEX = 0
SKILL_EXP_INDEX = 1
INFO_CONTENT_DETAILS_INDEX = 0

# RESULT FILE BASE NAME
OUTPUT_BASE_NAME = 'resume_output_'

# DRIVERS
FIREFOX = 'firefox'
CHROME = 'chrome'

# LOGIC
MAX_RETRIES = 3
SLEEP_TIME = 5
MAX_WAIT = 3
CTRL_COMMAND = Keys.COMMAND if platform.platform() == 'Darwin' else Keys.CONTROL

# ENVIRONMENT
ENV_USER = 'INDEED_RESUME_USER'
ENV_PASS = 'INDEED_RESUME_PASSWORD'

class Resume:
	def __init__ (self, idd, **kwargs):
		self.id = idd
		self.summary = kwargs.get('summary')
		self.jobs = kwargs.get('jobs')
		self.schools = kwargs.get('schools')
		self.skills = kwargs.get('skills')
		self.additional = kwargs.get('additional')

	def toJSON(self):
		return json.dumps(self, default=lambda o: o.__dict__)

class Summary:
	def __init__(self, details):
		self.details = details

class Job:
	def __init__(self, title, company, work_dates, details):
		self.title = title
		self.company = company

		dates = work_dates.split(' to ')
		self.start_date = dates[0]
		self.end_date = '' if len(dates) == 1 else dates[1]

		self.details = details

class School:
	def __init__(self, degree, school_name, grad_date):
		self.degree = degree
		self.school_name = school_name
		self.start_date = ''
		self.end_date = ''

		if grad_date is not None:
			dates = grad_date.split(' to ')
			self.start_date = dates[0]
			self.end_date = '' if len(dates) == 1 else dates[1]

class Skill:
	def __init__(self, skill, experience):
		self.skill = skill
		self.experience = experience

class Info:
	def __init__(self, details):
		self.details = details

# create expected condition that returns True when all is True
class AllExpectedCondition:
	def __init__(self, *ecs):
		self.ecs = ecs

	def __call__(self, driver):
		for ec in self.ecs:
			# refer to https://stackoverflow.com/questions/16462177/selenium-expected-conditions-possible-to-use-or
			if not ec(driver):
				return False
		return True

def go_to_page(driver, url):
	attempts = 0
	sleep_for = SLEEP_TIME
	while attempts < MAX_RETRIES:
		try:
			driver.get(url)
			return True
		except TimeoutException:
			if attempts != MAX_RETRIES - 1:
				logging.error('Unable to get to %s in time, attempt #%d. Retry in %d seconds', url, attempts + 1, sleep_for)
				time.sleep(sleep_for)
			else:
				logging.error('Unable to get to %s in time and reached maximum tries, aborting...', url)
			attempts += 1
			# exponentially backoff
			sleep_for *= 2
	return False

def gen_resume_link_elements(driver):
	"""Generate IDDs of resume

	Assumes driver already in page with resume IDDs
	Returns list of WebElement
	"""
	resume_links = []
	try:
		resume_links = driver.find_elements_by_css_selector(
			'div.rezemp-ResumeSearchCard .icl-TextLink.icl-TextLink--primary.rezemp-u-h4'
		)
	except TimeoutException:
		# could not complete in time
		resume_links = []

	return resume_links

def produce_work_experience(worksection):
	work_experience = worksection.find_all('div', class_='rezemp-WorkExperience')
	jobs = []
	for experience in work_experience:
		job_title = experience.find('div', class_='rezemp-u-h4').get_text()
		company_and_dates = experience.find('div', class_='rezemp-WorkExperience-subtitle')

		company_name = company_and_dates.find('span', class_='icl-u-textBold').get_text()
		work_dates = company_and_dates.find('div', class_='icl-u-textColor--tertiary').get_text()
		job_details = []
		if len(experience.contents) == 3:
			# there are job details
			details = experience.contents[-1]
			job_details = [detail for detail in details.stripped_strings]

		jobs.append(Job(job_title, company_name, work_dates, job_details))
	return jobs

def produce_education(edusection):
	content = edusection.find('div', class_='rezemp-ResumeDisplaySection-content')
	schools = []
	for school in content.children:
		degree = school.find(class_ = "rezemp-ResumeDisplay-itemTitle")
		if degree is not None:
			degree = degree.get_text(' ', strip=True)
		university_details = school.find(class_="rezemp-ResumeDisplay-university")
		school_name = university_details.find('span', class_='icl-u-textBold')
		if school_name is not None:
			school_name = school_name.get_text()
		date = school.find(class_="rezemp-ResumeDisplay-date")
		if date is not None:
			date = date.get_text()
		schools.append(School(degree, school_name, date))
	return schools

def produce_skills(skillsection):
	content = skillsection.find('div', class_='rezemp-ResumeDisplaySection-content')
	skills = []
	for skill_details in content.children:
		if skill_details.string is None:
			# there is no string attribute,
			# so it must be nested and so must be an actual skill
			# find skill detail spans
			skill_spans = skill_details.span.find_all('span')
			skill = skill_spans[SKILL_NAME_INDEX].get_text()
			experience = ''
			if len(skill_spans) == 2:
				experience = skill_spans[SKILL_EXP_INDEX].get_text()
			skills.append(Skill(skill, experience))
	return skills

# in case if needed later on in the future
def produce_certifications_license():
	pass

def produce_additional(infosection):
	content = infosection.find('div', class_='rezemp-ResumeDisplaySection-content')
	# only one div in content
	info_details = content.contents[INFO_CONTENT_DETAILS_INDEX]
	return [detail for detail in info_details.stripped_strings]


def produce_summary(summarysection):
	summary_details = []
	if len(summarysection) == 4:
		summary_details = summarysection.contents[-1]
		summary_details = [detail for detail in summary_details.stripped_strings]

	return summary_details

def gen_resume(resume_link, driver):
	idd = resume_link[resume_link.rfind('/') + 1:resume_link.rfind('?')]
	logging.info('Processing resume ID %s', idd)
	try:
		WebDriverWait(driver, MAX_WAIT).until(
			AllExpectedCondition(
				EC.visibility_of_any_elements_located((By.CLASS_NAME, 'rezemp-ResumeDisplay-body')),
				EC.url_to_be(resume_link)
			)
		)
	except TimeoutException:
		logging.error('Unable to get resume for ID %s, abandoning fetch', idd)
		return None

	p_element = driver.page_source
	soup = BeautifulSoup(p_element, 'html.parser')
	resume_body = soup.find('div', attrs={"class":"rezemp-ResumeDisplay-body"})
	summary = resume_body.contents[0]
	resume_subsections = resume_body.find_all('div', attrs={"class":"rezemp-ResumeDisplaySection"})

	resume_details = {}
	resume_details['summary'] = produce_summary(summary)
	for subsection in resume_subsections:
		children = subsection.contents
		subsection_title = children[0].get_text()
		if subsection_title == WORK_EXPERIENCE:
			resume_details['jobs'] = produce_work_experience(subsection)
		elif subsection_title == EDUCATION:
			resume_details['schools'] = produce_education(subsection)
		elif subsection_title == SKILLS:
			resume_details['skills'] = produce_skills(subsection)
		elif subsection_title == CERTIFICATIONS:
			produce_certifications_license()
		elif subsection_title == ADDITIONAL_INFORMATION:
			resume_details['additional'] = produce_additional(subsection)
		else:
			logging.warn('ID %s - Subsection title is %s', idd, subsection_title)

	return Resume(idd, **resume_details)

def next_page_button(driver):
	try:
		return driver.find_element_by_class_name('rezemp-pagination-nextbutton')
	except NoSuchElementException:
		return None

def go_to_next_search_page(driver, simulate, next_button, url):
	if simulate:
		try:
			# not sure why but next_button.click() does not always work across firefox and chrome
			driver.execute_script("arguments[0].click();", next_button)
		except NoSuchElementException:
			logging.info('No more pages to go to')
			return False
		return True
	else:
		# if not user simulation then go to search page directly
		go_to_page(driver, url)

def simulate_login(args, driver, search_point):
	login_url = INDEED_LOGIN_URL + '?' + urlencode({'service': 'roz', 'continue': search_point}, safe='%')
	if not go_to_page(driver, login_url):
		raise TimeoutException('Not able to login in given timeframe')

	email = driver.find_element_by_id('login-email-input')
	password = driver.find_element_by_id('login-password-input')
	email.send_keys(args.user)
	password.send_keys(args.password)

	submission_button = driver.find_element_by_id('login-submit-button')
	submission_button.submit()

	# twice the wait due to how important it is
	WebDriverWait(driver, MAX_WAIT * 2).until(EC.url_to_be(search_point))

def simulation_algorithm(driver, link_elements, json_file, main_window):
	for link in link_elements:
		resume_link = link.get_attribute('href')

		# seems to not work for firefox (at least on MAC)
		# actions.reset_actions()
		# actions.key_down(CTRL_COMMAND, link).click(link).perform()
		link.send_keys(CTRL_COMMAND + Keys.SHIFT + Keys.RETURN) # without shift firefox seems to not work on Mac
		driver.switch_to.window(driver.window_handles[1])
		resume = gen_resume(resume_link, driver)
		driver.close()

		if resume is not None:
			json_file.write(resume.toJSON() + "\n")
		driver.switch_to.window(main_window)

def non_simulation_algorithm(driver, resume_links, json_file, return_url):
	for link in resume_links:
		if go_to_page(driver, link):
			resume = gen_resume(link, driver)
			if resume is not None:
				json_file.write(resume.toJSON() + "\n")
		else:
			logging.error('Not able to go to resume page in time')

	# return back to some return URL
	while not go_to_page(driver, return_url):
		# just pass
		pass

def mine(args, json_filename, search_range, search_URL):
	if args.driver == FIREFOX:
		fp = firefox.firefox_profile.FirefoxProfile()
		fp.set_preference("browser.tabs.remote.autostart", False)
		fp.set_preference("browser.tabs.remote.autostart.1", False)
		fp.set_preference("browser.tabs.remote.autostart.2", False)
		driver = firefox.webdriver.WebDriver(firefox_profile=fp)
	else:
		driver = chrome.webdriver.WebDriver()
	driver.implicitly_wait(MAX_WAIT)
	driver.set_page_load_timeout(MAX_WAIT)

	search = search_range[0]
	end = search_range[1]

	attempts = 0
	try:
		search_point = search_URL + '&' + urlencode({'start': search})
		json_file = open(json_filename, 'w' if args.override else 'a')

		if args.login:
			simulate_login(args, driver, search_point)
		else:
			if not go_to_page(driver, search_point):
				raise TimeoutException('Unable to get to initial search point %s in time' % search_point)

		continue_search = True
		main_window = driver.current_window_handle
		while search < end and continue_search:
			# implicitly also waits for alert box to show up
			link_elements = gen_resume_link_elements(driver)

			if len(link_elements) == 0:
				# alert box showed and it is a simulated run
				if attempts < MAX_RETRIES:
					# attempt retry
					logging.error('Unable to find any resumes at index %d. Retrying in %d seconds...', search, SLEEP_TIME)
					attempts += 1
					time.sleep(SLEEP_TIME)
					# refresh page assuming page is search page
					driver.refresh()
				else:
					logging.error('Unable to find any resumes at index %d. Reached max attempts, abandoning search...', search)
					continue_search = False
			else:
				next_button = next_page_button(driver)
				link_elements = link_elements[:min(len(link_elements), end - search)]
				search += len(link_elements)
				if args.simulate:
					simulation_algorithm(driver, link_elements, json_file, main_window)
				else:
					links = [link.get_attribute('href') for link in link_elements]
					non_simulation_algorithm(driver, links, json_file, driver.current_url)

				logging.info('Finished getting resumes up to %d index, going to sleep a bit', search)
				time.sleep(SLEEP_TIME)
				if next_button is None:
					logging.info('No more pages to go to')
					continue_search = False
				else:
					continue_search = True
					next_search_url = search_URL + '&' + urlencode({'start': search})
					go_to_next_search_page(driver, args.simulate, next_button, next_search_url)
	except (TimeoutException, Exception):
		traceback.print_exc()
		logging.error('Caught exception finishing mining soon')
	finally:
		logging.info('Driver shutting down')
		json_file.close()
		driver.close()

def mine_multi(args, main_result_file, search_URL):
	start = args.si
	end = args.ei
	steps = ceil((end - start) / args.processes)
	starting_points = list(range(start, end, steps))
	fs = []

	with concurrent.futures.ProcessPoolExecutor(max_workers=args.processes) as executor:
		for idx, search_start in enumerate(starting_points):
			# Instantiates the thread
			filename = results_json_filename(args.name, str(idx))
			search_range = (search_start, end if idx + 1 == len(starting_points) else starting_points[idx + 1])
			mine_args = (args, filename, search_range, search_URL)
			fs.append(executor.submit(mine, *mine_args))
		try:
			# wait for all to finish
			concurrent.futures.wait(fs)
		except KeyboardInterrupt:
			logging.warn('Mining interrupted by user, joining results and exiting soon...')
		finally:
			consolidate_files(args.name, main_result_file, override=args.override)

def consolidate_files(name, main_result_file, override=False):
	glob_results_file = results_json_filename(name, suffix='*')
	with open(main_result_file, 'a') as result_json_file:
		for results_file in glob.glob(glob_results_file):
			if main_result_file != results_file:
				with open(results_file, 'r') as f:
					result_json_file.write(f.read())
				os.remove(results_file)

def results_json_filename(name, suffix=''):
	return OUTPUT_BASE_NAME + name + suffix + '.json'

def main(args):
	t = time.perf_counter()
	# restrict search only to job titles skills and field of study
	query = {
		'q': args.q,
		'l': args.l,
		'searchFields': 'jt',
		'lmd': 'all'
	}
	query_string = urlencode(query)
	search_URL= INDEED_RESUME_SEARCH_BASE_URL % query_string

	main_result_file = results_json_filename(args.name)
	if args.override:
		open(main_result_file, 'w').close()

	if args.processes != 1:
		mine_multi(args, main_result_file, search_URL)
	else:
		mine(args, main_result_file, (args.si, args.ei), search_URL)

	logging.info('Finished scraping in %f seconds', time.perf_counter() - t)

class LoginAction(argparse.Action):
	def __init__(self, option_strings, dest, nargs=None, **kwargs):
		# enforce nargs to be 0
		nargs = 0
		super(LoginAction, self).__init__(option_strings, dest, nargs=nargs, **kwargs)

	def __call__(self, parser, namespace, values, option_string=None):
		if os.environ.get(ENV_USER) is None:
			raise argparse.ArgumentError(self, 'Environment variable %s is not set please set it first' % ENV_USER)
		if os.environ.get(ENV_PASS) is None:
			raise argparse.ArgumentError(self, 'Environment variable %s is not set please set it first' % ENV_PASS)
		setattr(namespace, self.dest, True)
		setattr(namespace, 'user', os.environ.get(ENV_USER))
		setattr(namespace, 'password', os.environ.get(ENV_PASS))

if __name__ == "__main__":
	parser = argparse.ArgumentParser(
		description='Scrape Indeed Resumes',
		formatter_class=argparse.ArgumentDefaultsHelpFormatter
	)
	required_arguments = parser.add_argument_group(title='required arguments')
	required_arguments.add_argument('-q', metavar='query', required=True, help='search query to run on indeed e.g software engineer')
	required_arguments.add_argument('--name', metavar='name', required=True, help='name of search (used to save files, lowercased and spaces turned to "-")')

	parser.add_argument('-l', default='Canada', metavar='location', help='location scope for search')
	parser.add_argument('-si', default=0, type=int, metavar='start', help='starting index (multiples of 50)')
	parser.add_argument('-ei', default=NO_LOGIN_SEARCH_UPPER_LIMIT, type=int, metavar='end', help='ending index (multiples of 50)')
	parser.add_argument('--processes', default=1, type=int, metavar='processes', help='# of processes to run (max %d)' % MAX_PROCESSORS)
	parser.add_argument('--override', default=False, action='store_true', help='override existing result if any')
	parser.add_argument('--driver', default=FIREFOX, choices=[FIREFOX, CHROME])
	parser.add_argument('--login', default=False, action=LoginAction, help='Simulate logging in as a user (read README further for details)')
	parser.add_argument('--simulate-user', default=False, dest='simulate', action='store_true', help='Whether to simulate user clicks or not (slower)')

	args = parser.parse_args()

	# in case of carrige returns
	args.q = args.q.strip()
	args.l = args.l.strip()

	# reformat
	args.name = args.name.strip()
	args.name = args.name.replace(' ', '-')

	# setup logging
	logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(processName)s:%(levelname)s] %(message)s')

	# constrain
	args.processes = max(min(args.processes, MAX_PROCESSORS), 1)
	if not args.login:
		logging.warn('Login not specified, limiting starting search point to 0 and ending point at %d', NO_LOGIN_SEARCH_UPPER_LIMIT)
		args.si = 0
		args.ei = min(args.ei, NO_LOGIN_SEARCH_UPPER_LIMIT)

	main(args)
